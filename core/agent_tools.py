# core/agent_tools.py

import datetime
import psutil
import webbrowser


def get_time():
    return datetime.datetime.now().strftime(
        "%I:%M %p"
    )


def get_date():
    return datetime.datetime.now().strftime(
        "%A, %d %B %Y"
    )


def get_pc_health():

    cpu = psutil.cpu_percent(interval=1)

    ram = psutil.virtual_memory()

    disk = psutil.disk_usage("C:\\")

    battery = psutil.sensors_battery()

    result = {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "disk_percent": disk.percent,
    }

    if battery:
        result["battery_percent"] = battery.percent

    return result


def open_website(url):

    webbrowser.open(url)

    return {
        "opened": url
    }


def search_google(query):

    url = (
        "https://www.google.com/search?q="
        + query.replace(" ", "+")
    )

    webbrowser.open(url)

    return {
        "search": query
    }