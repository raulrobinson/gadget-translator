# test_minimo.py
import azure.cognitiveservices.speech as speechsdk
import time


def test_canal(dispositivo, idioma, nombre_canal):
    print(f"\n--- Probando {nombre_canal} ---")

    speech_config = speechsdk.SpeechConfig(
        subscription="5ae052154f2b4437a2bd13e2a8b1e1fc",  # <--- REEMPLAZA
        region="eastus"  # <--- REEMPLAZA
    )
    speech_config.speech_recognition_language = idioma

    audio_config = speechsdk.audio.AudioConfig(device_name=dispositivo)
    recognizer = speechsdk.SpeechRecognizer(speech_config, audio_config)

    print(f"Escuchando en {dispositivo}...")
    print("Di algo ahora!")

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"✅ ÉXITO: {result.text}")
        return True
    else:
        print(f"❌ FALLO: {result.reason}")
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            print(f"   Detalles: {details.reason}")
            if details.reason == speechsdk.CancellationReason.Error:
                print(f"   Error: {details.error_details}")
        return False


# Prueba ambos canales
if __name__ == "__main__":
    print("PRUEBA MÍNIMA DE AZURE SPEECH")
    print("=" * 50)

    test_canal("plughw:2,0", "es-ES", "Canal 1 (ES)")
    time.sleep(1)
    test_canal("plughw:3,0", "en-US", "Canal 2 (EN)")