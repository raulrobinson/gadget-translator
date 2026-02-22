# test_azure_mic.py
import azure.cognitiveservices.speech as speechsdk
import time


def test_mic(device_name, language):
    print(f"\nProbando dispositivo: {device_name}")
    print(f"Idioma: {language}")

    speech_config = speechsdk.SpeechConfig(
        subscription="5ae052154f2b4437a2bd13e2a8b1e1fc",
        region="eastus"
    )
    speech_config.speech_recognition_language = language

    audio_config = speechsdk.audio.AudioConfig(device_name=device_name)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )

    print("Di algo... (escuchando por 5 segundos)")

    done = False

    def recognized_cb(evt):
        print(f"Reconocido: {evt.result.text}")

    def canceled_cb(evt):
        print(f"Cancelado: {evt.result.cancellation_details.reason}")
        nonlocal done
        done = True

    recognizer.recognized.connect(recognized_cb)
    recognizer.canceled.connect(canceled_cb)

    recognizer.start_continuous_recognition()

    time.sleep(5)

    recognizer.stop_continuous_recognition()


# Probar
test_mic("plughw:2,0", "es-ES")
test_mic("plughw:3,0", "en-US")