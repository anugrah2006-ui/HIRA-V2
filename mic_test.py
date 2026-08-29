import speech_recognition as sr
import time


def main():
    print("Starting microphone diagnostic test...")

    try:
        mic_names = sr.Microphone.list_microphone_names()
    except Exception as e:
        print(f"Failed to enumerate microphones: {e}")
        print("Check that PyAudio is installed and the microphone drivers are working.")
        return

    if not mic_names:
        print("No microphone devices were detected.")
        return

    print("Available microphones:")
    for index, name in enumerate(mic_names):
        print(f"  [{index}] {name}")

    default_index = 0
    print(f"\nOpening default microphone at index {default_index}...")

    try:
        with sr.Microphone(device_index=default_index) as source:
            recognizer = sr.Recognizer()
            print("Calibrating ambient noise for 1 second...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Recording 3 seconds of audio...")
            audio = recognizer.record(source, duration=3)
    except Exception as e:
        print(f"Microphone open or recording failed: {e}")
        print("Ensure no other application is using the microphone and try again.")
        return

    print("Audio capture completed successfully.")
    try:
        if audio.frame_data:
            print("Audio was captured and contains data.")
        else:
            print("Audio capture completed but no data was recorded.")
    except Exception as e:
        print(f"Unable to verify recorded audio data: {e}")


if __name__ == "__main__":
    main()
