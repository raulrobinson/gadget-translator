# diagnostic_audio.py
import subprocess
import pyaudio
import sounddevice as sd


def diagnosticar():
    print("=== DIAGNÓSTICO COMPLETO DE AUDIO ===\n")

    # 1. Verificar dispositivos ALSA
    print("1. DISPOSITIVOS ALSA:")
    result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
    print(result.stdout)

    # 2. Verificar permisos
    print("\n2. PERMISOS DE AUDIO:")
    result = subprocess.run(['groups'], capture_output=True, text=True)
    print(f"Grupos: {result.stdout}")

    if 'audio' not in result.stdout:
        print("⚠️  El usuario no está en el grupo 'audio'")
        print("Ejecuta: sudo usermod -a -G audio $USER")

    # 3. Probar con PyAudio
    print("\n3. PRUEBA CON PYAUDIO:")
    p = pyaudio.PyAudio()

    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"\n[{i}] {info['name']}")
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=i,
                    frames_per_buffer=1024
                )
                print("  ✅ Stream abierto correctamente")
                stream.close()
            except Exception as e:
                print(f"  ❌ Error: {e}")

    p.terminate()

    # 4. Verificar Azure SDK
    print("\n4. VERIFICAR AZURE SPEECH SDK:")
    try:
        import azure.cognitiveservices.speech as speechsdk
        print(f"✅ Azure Speech SDK versión: {speechsdk.__version__}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    diagnosticar()