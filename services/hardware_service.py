import shutil
import subprocess

from core.config import api_logger

try:
    import wmi
except Exception:
    wmi = None


TEMPERATURE_KEYS = ("CPU", "GPU", "SSD")


def _empty_temperatures():
    return {key: None for key in TEMPERATURE_KEYS}


def _as_float(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _set_if_empty(data, key, value):
    temperature = _as_float(value)
    if temperature is not None and data.get(key) is None:
        data[key] = temperature


def _classify_sensor(sensor):
    text = " ".join(
        str(getattr(sensor, attr, "") or "")
        for attr in ("Name", "Identifier", "Parent", "HardwareType")
    ).lower()

    if any(token in text for token in ("gpu", "nvidia", "radeon", "graphics")):
        return "GPU"
    if any(token in text for token in ("ssd", "nvme", "hdd", "storage", "disk")):
        return "SSD"
    if any(token in text for token in ("cpu", "processor", "package", "core")):
        return "CPU"
    return None


def _read_monitor_namespace(namespace, data):
    if wmi is None:
        return False

    try:
        connection = wmi.WMI(namespace=namespace)
        found = False
        for sensor in connection.Sensor():
            if str(getattr(sensor, "SensorType", "")).lower() != "temperature":
                continue
            key = _classify_sensor(sensor)
            if key:
                _set_if_empty(data, key, getattr(sensor, "Value", None))
                found = True
        return found
    except Exception as exc:
        api_logger.info(f"Temperature namespace unavailable ({namespace}): {exc}")
        return False


def _read_acpi_cpu(data):
    if wmi is None or data.get("CPU") is not None:
        return False

    try:
        connection = wmi.WMI(namespace="root\\wmi")
        zones = connection.MSAcpi_ThermalZoneTemperature()
        for zone in zones:
            raw = _as_float(getattr(zone, "CurrentTemperature", None))
            if raw is None:
                continue
            celsius = round((raw / 10.0) - 273.15, 1)
            if -20 <= celsius <= 125:
                data["CPU"] = celsius
                return True
    except Exception as exc:
        api_logger.info(f"ACPI temperature unavailable: {exc}")
    return False


def _read_nvidia_gpu(data):
    if data.get("GPU") is not None:
        return False

    executable = shutil.which("nvidia-smi")
    if not executable:
        return False

    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if completed.returncode != 0:
            return False
        for line in completed.stdout.splitlines():
            _set_if_empty(data, "GPU", line.strip())
            if data.get("GPU") is not None:
                return True
    except Exception as exc:
        api_logger.info(f"nvidia-smi temperature unavailable: {exc}")
    return False


def _read_storage_temperature(data):
    if wmi is None or data.get("SSD") is not None:
        return False

    try:
        connection = wmi.WMI(namespace="root\\Microsoft\\Windows\\Storage")
        for disk in connection.MSFT_PhysicalDisk():
            temperature = getattr(disk, "Temperature", None)
            if temperature in (None, 0):
                continue
            _set_if_empty(data, "SSD", temperature)
            if data.get("SSD") is not None:
                return True
    except Exception as exc:
        api_logger.info(f"Storage temperature unavailable: {exc}")
    return False


def get_pc_temperature():
    """Return structured local hardware temperatures where sensors are available."""
    data = _empty_temperatures()
    sources = []
    errors = []

    if wmi is None:
        errors.append("WMI package is not installed.")
    else:
        for namespace in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
            if _read_monitor_namespace(namespace, data):
                sources.append(namespace)
        if _read_acpi_cpu(data):
            sources.append("root\\wmi")
        if _read_storage_temperature(data):
            sources.append("root\\Microsoft\\Windows\\Storage")

    if _read_nvidia_gpu(data):
        sources.append("nvidia-smi")

    return {
        "success": True,
        "data": data,
        "sources": sources,
        "errors": errors,
    }


def format_pc_temperature_result(result):
    data = result.get("data") or {}
    lines = []
    for key in TEMPERATURE_KEYS:
        value = data.get(key)
        if value is None:
            lines.append(f"{key}: unavailable")
        else:
            lines.append(f"{key}: {value:.1f} C")

    if result.get("errors"):
        lines.append("Sensor note: " + "; ".join(result["errors"]))
    if not result.get("sources"):
        lines.append("No supported hardware temperature sensors were exposed to HIRA.")
    return "\n".join(lines)
