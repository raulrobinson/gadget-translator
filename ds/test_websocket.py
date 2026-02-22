# test_websocket.py
import asyncio
import websockets
import json
import pyaudio
import wave


async def test_azure_websocket(key, region):
    """Prueba básica de WebSocket con Azure"""

    # Configuración
    url = f"wss://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    params = "?language=es-ES&format=simple"

    headers = {
        "Ocp-Apim-Subscription-Key": key
    }

    print(f"Conectando a {url}...")

    try:
        async with websockets.connect(url + params, extra_headers=headers) as ws:
            print("✅ Conectado!")

            # Crear audio de prueba
            p = pyaudio.PyAudio()

            # Grabar 3 segundos
            print("🎤 Grabando 3 segundos...")
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=2,  # hw:2,0
                frames_per_buffer=1024
            )

            frames = []
            for _ in range(0, int(16000 / 1024 * 3)):
                data = stream.read(1024)
                frames.append(data)

            stream.close()

            # Crear WAV
            import io
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wav_file.setframerate(16000)
                wav_file.writeframes(b''.join(frames))

            wav_buffer.seek(0)

            # Enviar audio
            print("📤 Enviando audio...")
            await ws.send(wav_buffer.read())

            # Recibir resultado
            print("📥 Esperando respuesta...")
            response = await ws.recv()
            result = json.loads(response)

            print(f"\nResultado: {json.dumps(result, indent=2)}")

            if result.get('RecognitionStatus') == 'Success':
                print(f"\n✅ Texto reconocido: {result.get('DisplayText')}")

    except Exception as e:
        print(f"❌ Error: {e}")


# Ejecutar prueba
if __name__ == "__main__":
    KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"
    REGION = "eastus"

    asyncio.run(test_azure_websocket(KEY, REGION))