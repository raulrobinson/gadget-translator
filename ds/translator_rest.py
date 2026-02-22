# translator_rest.py
import requests
import pyaudio
import wave
import threading
import time
import queue
import json
import os
import tempfile
from datetime import datetime


class TraductorREST:
    def __init__(self, subscription_key, region):
        self.subscription_key = subscription_key
        self.region = region

        # URLs de API
        self.stt_url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        self.tts_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self.token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"

        # Configuración de audio
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024
        self.segundos_grabacion = 3  # Grabamos en fragmentos de 3 segundos

        # Dispositivos (hardcodeado de tus pruebas)
        self.dispositivos = {
            'espanol': 2,  # hw:2,0
            'ingles': 3  # hw:3,0
        }

        # Inicializar PyAudio
        self.p = pyaudio.PyAudio()

        # Control de ejecución
        self.ejecutando = False

        # Estadísticas
        self.contador_es = 0
        self.contador_en = 0

        print("\n" + "=" * 70)
        print("🌐 TRADUCTOR REST - RASPBERRY PI 400".center(70))
        print("=" * 70)
        print(f"Región: {region}")
        print(f"Dispositivo Español: hw:{self.dispositivos['espanol']},0")
        print(f"Dispositivo Inglés: hw:{self.dispositivos['ingles']},0")
        print(f"Duración grabación: {self.segundos_grabacion} segundos")
        print("=" * 70)

    def get_token(self):
        """Obtiene token de autenticación"""
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key
        }

        response = requests.post(self.token_url, headers=headers)

        if response.status_code == 200:
            return response.text
        else:
            print(f"Error obteniendo token: {response.status_code}")
            return None

    def grabar_audio(self, device_index):
        """Graba audio desde un dispositivo"""
        frames = []

        try:
            stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk
            )

            total_frames = int(self.rate / self.chunk * self.segundos_grabacion)

            for i in range(total_frames):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

            stream.close()

            return b''.join(frames)

        except Exception as e:
            print(f"Error grabando: {e}")
            return None

    def guardar_wav_temp(self, audio_data):
        """Guarda audio como WAV temporal"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')

        with wave.open(temp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.p.get_sample_size(self.format))
            wav_file.setframerate(self.rate)
            wav_file.writeframes(audio_data)

        return temp_file.name

    def reconocer_audio(self, audio_data, idioma):
        """Reconoce audio usando STT REST API"""
        # Guardar temporalmente
        temp_file = self.guardar_wav_temp(audio_data)

        # Configurar headers
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"
        }

        params = {
            "language": idioma,
            "format": "detailed"
        }

        try:
            with open(temp_file, 'rb') as audio:
                response = requests.post(
                    self.stt_url,
                    headers=headers,
                    params=params,
                    data=audio,
                    timeout=10
                )

            if response.status_code == 200:
                result = response.json()
                if result.get('RecognitionStatus') == 'Success':
                    return result.get('DisplayText', '')
                else:
                    return None
            else:
                print(f"Error STT: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error en reconocimiento: {e}")
            return None

        finally:
            # Limpiar archivo temporal
            os.unlink(temp_file)

    def sintetizar_voz(self, texto, idioma):
        """Sintetiza texto a voz usando TTS REST API"""
        # Configurar voz según idioma
        if idioma == "en-US":
            voice = "en-US-JennyNeural"
        else:
            voice = "es-ES-ElviraNeural"

        # Crear SSML
        ssml = f"""<speak version='1.0' xml:lang='{idioma}'>
            <voice name='{voice}'>{texto}</voice>
        </speak>"""

        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"
        }

        try:
            response = requests.post(
                self.tts_url,
                headers=headers,
                data=ssml.encode('utf-8'),
                timeout=10
            )

            if response.status_code == 200:
                return response.content
            else:
                print(f"Error TTS: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error en síntesis: {e}")
            return None

    def reproducir_mp3(self, audio_data):
        """Reproduce audio MP3"""
        from pydub import AudioSegment
        from pydub.playback import play
        import io

        try:
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            play(audio)
        except Exception as e:
            print(f"Error reproduciendo: {e}")

    def canal_espanol(self):
        """Canal Español -> Inglés"""
        print("\n🎤 Canal ESPAÑOL activo (hw:2,0)")

        while self.ejecutando:
            try:
                # 1. Grabar audio
                audio = self.grabar_audio(self.dispositivos['espanol'])

                if audio:
                    # 2. Reconocer español
                    texto_es = self.reconocer_audio(audio, "es-ES")

                    if texto_es:
                        self.contador_es += 1
                        print(f"\n📝 [{self.contador_es}] ES: {texto_es}")

                        # 3. Traducir (placeholder - puedes integrar traductor aquí)
                        texto_en = f"Translation: {texto_es}"

                        # 4. Sintetizar inglés
                        audio_en = self.sintetizar_voz(texto_en, "en-US")

                        if audio_en:
                            print(f"   🔊 EN: {texto_en}")
                            self.reproducir_mp3(audio_en)

                # Pequeña pausa entre grabaciones
                time.sleep(0.5)

            except Exception as e:
                print(f"Error en canal español: {e}")

    def canal_ingles(self):
        """Canal Inglés -> Español"""
        print("🎤 Canal INGLÉS activo (hw:3,0)")

        while self.ejecutando:
            try:
                # 1. Grabar audio
                audio = self.grabar_audio(self.dispositivos['ingles'])

                if audio:
                    # 2. Reconocer inglés
                    texto_en = self.reconocer_audio(audio, "en-US")

                    if texto_en:
                        self.contador_en += 1
                        print(f"\n📝 [{self.contador_en}] EN: {texto_en}")

                        # 3. Traducir (placeholder)
                        texto_es = f"Traducción: {texto_en}"

                        # 4. Sintetizar español
                        audio_es = self.sintetizar_voz(texto_es, "es-ES")

                        if audio_es:
                            print(f"   🔊 ES: {texto_es}")
                            self.reproducir_mp3(audio_es)

                time.sleep(0.5)

            except Exception as e:
                print(f"Error en canal inglés: {e}")

    def iniciar(self):
        """Inicia ambos canales"""
        self.ejecutando = True

        # Crear hilos
        hilo_es = threading.Thread(target=self.canal_espanol)
        hilo_en = threading.Thread(target=self.canal_ingles)

        hilo_es.daemon = True
        hilo_en.daemon = True

        print("\n🚀 Iniciando sistema...")
        hilo_es.start()
        time.sleep(1)
        hilo_en.start()

        print("\n✅ SISTEMA ACTIVO")
        print("Habla en los micrófonos")
        print("Presiona Ctrl+C para detener")
        print("-" * 60)

        try:
            while self.ejecutando:
                time.sleep(0.1)

                # Mostrar estadísticas cada 30 segundos
                if int(time.time()) % 30 == 0:
                    print(f"\n📊 Estadísticas: ES:{self.contador_es} EN:{self.contador_en}")

        except KeyboardInterrupt:
            print("\n\n🛑 Deteniendo...")
            self.ejecutando = False
            time.sleep(2)
            self.p.terminate()
            print(f"\n📊 Total: ES:{self.contador_es} EN:{self.contador_en}")
            print("✅ Sistema detenido")


if __name__ == "__main__":
    # Configuración
    AZURE_SPEECH_KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"
    AZURE_REGION = "eastus"

    print("=" * 70)
    print("TRADUCTOR EN TIEMPO REAL CON API REST".center(70))
    print("=" * 70)

    if AZURE_SPEECH_KEY == "5ae052154f2b4437a2bd13e2a8b1e1fc":
        print("\n❌ ERROR: Configura tu API key de Azure Speech")
        print("Edita el archivo y reemplaza '5ae052154f2b4437a2bd13e2a8b1e1fc'")
        exit(1)

    # Verificar dependencias
    try:
        from pydub import AudioSegment
        from pydub.playback import play

        print("✅ Dependencias OK")
    except ImportError:
        print("\n📦 Instalando dependencias...")
        os.system("pip install pydub")

    # Crear y ejecutar traductor
    traductor = TraductorREST(AZURE_SPEECH_KEY, AZURE_REGION)
    traductor.iniciar()