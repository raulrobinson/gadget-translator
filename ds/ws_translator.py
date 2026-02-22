# translator_websocket.py
import asyncio
import websockets
import json
import base64
import pyaudio
import threading
import time
import queue
import wave
import os
import signal
import sys
from datetime import datetime


class TraductorWebSocket:
    def __init__(self, subscription_key, region):
        self.subscription_key = subscription_key
        self.region = region

        # Configuración de audio
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024

        # URLs de WebSocket para Azure Speech
        self.wss_url = f"wss://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        self.tts_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

        # Dispositivos
        self.dispositivos = {
            'espanol': 2,  # hw:2,0
            'ingles': 3  # hw:3,0
        }

        # Inicializar PyAudio
        self.p = pyaudio.PyAudio()

        # Colas para audio
        self.cola_audio_es = queue.Queue()
        self.cola_audio_en = queue.Queue()

        # Control de ejecución
        self.ejecutando = False

        print("\n" + "=" * 60)
        print("🎯 TRADUCTOR WEBSOCKET - RASPBERRY PI 400")
        print("=" * 60)
        print(f"Región: {region}")
        print(f"Dispositivo Español: hw:{self.dispositivos['espanol']},0")
        print(f"Dispositivo Inglés: hw:{self.dispositivos['ingles']},0")
        print("=" * 60)

    def grabar_audio_dispositivo(self, device_index, duracion=5):
        """Graba audio desde un dispositivo específico"""
        frames = []

        stream = self.p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.chunk
        )

        print(f"  Grabando {duracion} segundos...")
        for _ in range(0, int(self.rate / self.chunk * duracion)):
            data = stream.read(self.chunk)
            frames.append(data)

        stream.close()
        return b''.join(frames)

    async def reconocer_audio(self, audio_data, idioma):
        """Envía audio a Azure STT via WebSocket"""
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"
        }

        # Crear WAV en memoria
        import io
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.p.get_sample_size(self.format))
            wav_file.setframerate(self.rate)
            wav_file.writeframes(audio_data)

        wav_buffer.seek(0)

        # Construir URL con parámetros
        url = f"{self.wss_url}?language={idioma}&format=detailed"

        try:
            async with websockets.connect(url, extra_headers=headers) as websocket:
                # Enviar audio
                await websocket.send(wav_buffer.read())

                # Recibir resultados
                response = await websocket.recv()
                result = json.loads(response)

                if result.get('RecognitionStatus') == 'Success':
                    return result.get('DisplayText', '')
                else:
                    return None

        except Exception as e:
            print(f"Error en reconocimiento: {e}")
            return None

    async def sintetizar_voz(self, texto, idioma):
        """Convierte texto a voz usando Azure TTS"""
        import aiohttp

        # Configurar voz según idioma
        if idioma == "en-US":
            voice = "en-US-JennyNeural"
        else:
            voice = "es-ES-ElviraNeural"

        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"
        }

        # Crear SSML
        ssml = f"""
        <speak version='1.0' xml:lang='{idioma}'>
            <voice name='{voice}'>{texto}</voice>
        </speak>
        """

        async with aiohttp.ClientSession() as session:
            async with session.post(self.tts_url, headers=headers, data=ssml) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    return audio_data
                else:
                    print(f"Error TTS: {response.status}")
                    return None

    def reproducir_audio(self, audio_data):
        """Reproduce audio MP3"""
        import io
        from pydub import AudioSegment
        from pydub.playback import play

        try:
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            play(audio)
        except Exception as e:
            print(f"Error reproduciendo: {e}")

    def canal_espanol(self):
        """Canal Español -> Inglés"""
        print("\n🎤 Canal Español activo (hw:2,0)")

        while self.ejecutando:
            try:
                # Grabar audio
                audio = self.grabar_audio_dispositivo(self.dispositivos['espanol'], duracion=3)

                # Crear evento loop para async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Reconocer español
                texto_es = loop.run_until_complete(
                    self.reconocer_audio(audio, "es-ES")
                )

                if texto_es:
                    print(f"\n📝 [ES] {texto_es}")

                    # Traducir (placeholder)
                    texto_en = f"[English] {texto_es}"
                    print(f"   ➡️ [EN] {texto_en}")

                    # Sintetizar inglés
                    audio_en = loop.run_until_complete(
                        self.sintetizar_voz(texto_en, "en-US")
                    )

                    if audio_en:
                        print("   🔊 Reproduciendo...")
                        self.reproducir_audio(audio_en)

                loop.close()

            except Exception as e:
                print(f"Error en canal español: {e}")

            time.sleep(0.5)

    def canal_ingles(self):
        """Canal Inglés -> Español"""
        print("🎤 Canal Inglés activo (hw:3,0)")

        while self.ejecutando:
            try:
                # Grabar audio
                audio = self.grabar_audio_dispositivo(self.dispositivos['ingles'], duracion=3)

                # Crear evento loop para async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Reconocer inglés
                texto_en = loop.run_until_complete(
                    self.reconocer_audio(audio, "en-US")
                )

                if texto_en:
                    print(f"\n📝 [EN] {texto_en}")

                    # Traducir (placeholder)
                    texto_es = f"[Español] {texto_en}"
                    print(f"   ➡️ [ES] {texto_es}")

                    # Sintetizar español
                    audio_es = loop.run_until_complete(
                        self.sintetizar_voz(texto_es, "es-ES")
                    )

                    if audio_es:
                        print("   🔊 Reproduciendo...")
                        self.reproducir_audio(audio_es)

                loop.close()

            except Exception as e:
                print(f"Error en canal inglés: {e}")

            time.sleep(0.5)

    def iniciar(self):
        """Inicia ambos canales en hilos separados"""
        self.ejecutando = True

        # Crear hilos para cada canal
        hilo_es = threading.Thread(target=self.canal_espanol)
        hilo_en = threading.Thread(target=self.canal_ingles)

        hilo_es.daemon = True
        hilo_en.daemon = True

        print("\n🚀 Iniciando canales...")
        hilo_es.start()
        time.sleep(1)
        hilo_en.start()

        print("\n✅ Sistema activo - Habla en los micrófonos")
        print("Presiona Ctrl+C para detener")
        print("-" * 60)

        try:
            while self.ejecutando:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n🛑 Deteniendo...")
            self.ejecutando = False
            self.p.terminate()
            print("✅ Sistema detenido")


# Versión simplificada usando API REST
class TraductorREST:
    def __init__(self, subscription_key, region):
        self.subscription_key = subscription_key
        self.region = region
        self.stt_url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        self.tts_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

    def reconocer_audio_rest(self, audio_file, idioma):
        """Reconocimiento usando API REST"""
        import requests

        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"
        }

        params = {
            "language": idioma,
            "format": "detailed"
        }

        with open(audio_file, 'rb') as audio:
            response = requests.post(
                self.stt_url,
                headers=headers,
                params=params,
                data=audio
            )

        if response.status_code == 200:
            result = response.json()
            if result.get('RecognitionStatus') == 'Success':
                return result.get('DisplayText', '')

        return None


# Script principal
def signal_handler(sig, frame):
    print("\n\n🛑 Deteniendo...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    # Configuración
    AZURE_SPEECH_KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"
    AZURE_REGION = "eastus"

    print("=" * 60)
    print("🌐 TRADUCTOR CON WEBSOCKETS")
    print("=" * 60)

    if AZURE_SPEECH_KEY != "5ae052154f2b4437a2bd13e2a8b1e1fc":
        print("\n❌ Configura tu API key de Azure Speech")
        exit(1)

    # Instalar dependencias necesarias
    print("\n📦 Verificando dependencias...")
    try:
        import websockets
        import aiohttp
        from pydub import AudioSegment
        from pydub.playback import play

        print("✅ Dependencias OK")
    except ImportError as e:
        print(f"❌ Falta dependencia: {e}")
        print("\nInstala las dependencias:")
        print("pip install websockets aiohttp pydub")
        exit(1)

    # Crear y ejecutar traductor
    traductor = TraductorWebSocket(AZURE_SPEECH_KEY, AZURE_REGION)
    traductor.iniciar()