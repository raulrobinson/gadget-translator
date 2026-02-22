# test_websocket_fixed.py
import asyncio
import websockets
import json
import pyaudio
import wave
import base64


async def test_azure_websocket(key, region):
    """Prueba básica de WebSocket con Azure - Versión corregida"""

    # Configuración
    url = f"wss://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=es-ES&format=detailed"

    print(f"Conectando a {url}...")

    try:
        # Crear conexión con headers en el protocolo
        async with websockets.connect(
                url,
                extra_headers={
                    "Ocp-Apim-Subscription-Key": key
                }
        ) as websocket:
            print("✅ Conectado!")

            # Configurar PyAudio
            p = pyaudio.PyAudio()

            # Grabar 3 segundos
            print("🎤 Grabando 3 segundos (di algo en español)...")
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=2,  # hw:2,0
                frames_per_buffer=1024
            )

            frames = []
            for i in range(0, int(16000 / 1024 * 3)):
                data = stream.read(1024)
                frames.append(data)
                print(f"  Grabando... {i + 1}/47", end='\r')

            stream.close()
            print("\n✅ Grabación completada")

            # Crear WAV en memoria
            import io
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wav_file.setframerate(16000)
                wav_file.writeframes(b''.join(frames))

            wav_buffer.seek(0)
            audio_data = wav_buffer.read()

            # Enviar configuración primero
            config = {
                "context": {
                    "system": {
                        "version": "1.0"
                    }
                }
            }

            # Enviar audio
            print("📤 Enviando audio...")
            await websocket.send(audio_data)

            # Recibir resultado
            print("📥 Esperando respuesta...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                result = json.loads(response)

                print(f"\n📊 Resultado completo:")
                print(json.dumps(result, indent=2, ensure_ascii=False))

                if result.get('RecognitionStatus') == 'Success':
                    texto = result.get('DisplayText', '')
                    print(f"\n✅ Texto reconocido: {texto}")
                else:
                    print(f"\n❌ Estado: {result.get('RecognitionStatus')}")

            except asyncio.TimeoutError:
                print("⏰ Timeout esperando respuesta")

            await websocket.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


# Versión usando API REST (más simple)
def test_azure_rest(key, region):
    """Prueba usando API REST (más estable)"""
    import requests

    print("\n" + "=" * 50)
    print("PRUEBA CON API REST")
    print("=" * 50)

    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"
    }

    params = {
        "language": "es-ES",
        "format": "detailed"
    }

    # Grabar audio
    print("🎤 Grabando 3 segundos...")
    p = pyaudio.PyAudio()

    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        input_device_index=2,
        frames_per_buffer=1024
    )

    frames = []
    for _ in range(0, int(16000 / 1024 * 3)):
        data = stream.read(1024)
        frames.append(data)

    stream.close()

    # Guardar temporalmente
    filename = "temp_test.wav"
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))

    p.terminate()

    # Enviar a Azure
    print("📤 Enviando a Azure...")
    with open(filename, 'rb') as audio_file:
        response = requests.post(
            url,
            headers=headers,
            params=params,
            data=audio_file
        )

    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Respuesta recibida:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result.get('RecognitionStatus') == 'Success':
            print(f"\n📝 Texto: {result.get('DisplayText')}")
        else:
            print(f"⚠️ Estado: {result.get('RecognitionStatus')}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

    # Limpiar
    import os
    os.remove(filename)


# Versión alternativa con websockets
async def test_websocket_alt(key, region):
    """Método alternativo con websockets"""
    import requests

    # Primero obtener token
    token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    token_headers = {
        "Ocp-Apim-Subscription-Key": key
    }

    print("🔑 Obteniendo token...")
    token_response = requests.post(token_url, headers=token_headers)

    if token_response.status_code == 200:
        token = token_response.text
        print("✅ Token obtenido")

        # Usar websocket con token
        url = f"wss://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=es-ES&format=detailed"

        async with websockets.connect(
                url,
                extra_headers={
                    "Authorization": f"Bearer {token}"
                }
        ) as websocket:
            print("✅ Conectado con token")

            # Grabar audio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=2,
                frames_per_buffer=1024
            )

            print("🎤 Grabando...")
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
            await websocket.send(wav_buffer.read())

            # Recibir respuesta
            response = await websocket.recv()
            result = json.loads(response)

            print(f"\n📊 Resultado: {json.dumps(result, indent=2, ensure_ascii=False)}")

            p.terminate()
    else:
        print(f"❌ Error obteniendo token: {token_response.status_code}")


if __name__ == "__main__":
    KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"  # <--- REEMPLAZA
    REGION = "eastus"

    print("🌐 PRUEBA DE AZURE SPEECH")
    print("=" * 60)

    print("Selecciona método de prueba:")
    print("1. API REST (recomendado)")
    print("2. WebSocket con token")
    print("3. WebSocket directo")

    opcion = input("Opción (1-3): ")

    if opcion == "1":
        test_azure_rest(KEY, REGION)
    elif opcion == "2":
        asyncio.run(test_websocket_alt(KEY, REGION))
    else:
        asyncio.run(test_azure_websocket(KEY, REGION))