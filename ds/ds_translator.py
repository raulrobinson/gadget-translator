# translator_fixed.py
import azure.cognitiveservices.speech as speechsdk
import pyaudio
import wave
import threading
import queue
import time
import numpy as np
import os
import subprocess


class TraductorRaspberryPi:
    def __init__(self, subscription_key, region):
        """
        Traductor optimizado para Raspberry Pi 400 con dos diademas Logitech
        """
        self.subscription_key = subscription_key
        self.region = region

        # Configuración de audio
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024

        # Identificar dispositivos Logitech específicamente
        self.dispositivos = self.identificar_dispositivos_logitech()

        # Inicializar PyAudio
        self.p = pyaudio.PyAudio()

        # Colas para los canales
        self.cola_es_en = queue.Queue()
        self.cola_en_es = queue.Queue()

        # Flags de ejecución
        self.ejecutando = False

    def identificar_dispositivos_logitech(self):
        """Identifica específicamente los dispositivos Logitech"""
        dispositivos = []

        print("\n🔍 Buscando dispositivos Logitech...")

        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                nombre = info['name']
                if 'Logitech' in nombre or 'USB Headset' in nombre:
                    print(f"  ✅ Encontrado: {nombre}")
                    dispositivos.append({
                        'index': i,
                        'name': nombre,
                        'channels': int(info['maxInputChannels']),
                        'rate': int(info['defaultSampleRate'])
                    })

        if len(dispositivos) >= 2:
            print(f"\n✅ 2 dispositivos Logitech encontrados")
            return dispositivos[:2]
        else:
            print(f"\n⚠️  Solo {len(dispositivos)} dispositivos Logitech encontrados")
            return dispositivos

    def get_device_alsa_id(self, device_index):
        """Obtiene el ID ALSA correcto para el dispositivo"""
        device_info = self.dispositivos[device_index]
        nombre = device_info['name']

        # Extraer el número de tarjeta del nombre (ej: "hw:2,0")
        import re
        match = re.search(r'hw:(\d+),(\d+)', nombre)
        if match:
            card = match.group(1)
            device = match.group(2)
            return f"plughw:{card},{device}"

        return None

    def canal_espanol_ingles(self):
        """Canal 1: Español a Inglés usando método de archivos temporales"""
        try:
            # Configuración de reconocimiento (Español)
            speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            speech_config.speech_recognition_language = "es-ES"

            # Obtener ID ALSA del primer dispositivo
            alsa_id = self.get_device_alsa_id(0)

            # Configuración de audio usando el dispositivo específico
            audio_config = speechsdk.audio.AudioConfig(
                device_name=alsa_id if alsa_id else "default"
            )

            # Crear reconocedor
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Configuración de síntesis (Inglés)
            tts_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            tts_config.speech_synthesis_voice_name = "en-US-JennyNeural"

            # Configuración de audio para síntesis (salida por defecto)
            audio_output_config = speechsdk.audio.AudioOutputConfig(
                use_default_speaker=True
            )

            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=tts_config,
                audio_config=audio_output_config
            )

            print("\n🎤 Canal ES->EN: Escuchando (diadema 1)...")

            def handle_recognized(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto = evt.result.text
                    if texto.strip():
                        print(f"\n📝 [ES] {texto}")
                        # Traducción simple (placeholder)
                        texto_en = f"Translation: {texto}"
                        print(f"   ➡️ [EN] {texto_en}")

                        # Sintetizar
                        try:
                            result = synthesizer.speak_text_async(texto_en).get()
                        except Exception as e:
                            print(f"Error en síntesis: {e}")

            recognizer.recognized.connect(handle_recognized)

            # Conectar manejador de eventos para diagnóstico
            def handle_canceled(evt):
                print(f"Evento cancelado: {evt.result.cancellation_details.reason}")

            recognizer.canceled.connect(handle_canceled)

            return recognizer

        except Exception as e:
            print(f"Error en canal ES->EN: {e}")
            return None

    def canal_ingles_espanol(self):
        """Canal 2: Inglés a Español"""
        try:
            # Configuración de reconocimiento (Inglés)
            speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            speech_config.speech_recognition_language = "en-US"

            # Obtener ID ALSA del segundo dispositivo
            if len(self.dispositivos) > 1:
                alsa_id = self.get_device_alsa_id(1)
            else:
                alsa_id = None

            # Configuración de audio
            audio_config = speechsdk.audio.AudioConfig(
                device_name=alsa_id if alsa_id else "default"
            )

            # Crear reconocedor
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Configuración de síntesis (Español)
            tts_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            tts_config.speech_synthesis_voice_name = "es-ES-ElviraNeural"

            audio_output_config = speechsdk.audio.AudioOutputConfig(
                use_default_speaker=True
            )

            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=tts_config,
                audio_config=audio_output_config
            )

            print("🎤 Canal EN->ES: Escuchando (diadema 2)...")

            def handle_recognized(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto = evt.result.text
                    if texto.strip():
                        print(f"\n📝 [EN] {texto}")
                        # Traducción simple (placeholder)
                        texto_es = f"Traducción: {texto}"
                        print(f"   ➡️ [ES] {texto_es}")

                        # Sintetizar
                        try:
                            result = synthesizer.speak_text_async(texto_es).get()
                        except Exception as e:
                            print(f"Error en síntesis: {e}")

            recognizer.recognized.connect(handle_recognized)

            return recognizer

        except Exception as e:
            print(f"Error en canal EN->ES: {e}")
            return None

    def iniciar(self):
        """Inicia ambos canales"""
        print("\n" + "=" * 60)
        print("TRADUCTOR EN TIEMPO REAL - RASPBERRY PI 400")
        print("=" * 60)

        if len(self.dispositivos) < 2:
            print(f"⚠️  ADVERTENCIA: Solo {len(self.dispositivos)} diademas detectadas")
            print("Se necesitan 2 diademas Logitech para traducción bidireccional")
            respuesta = input("¿Continuar de todos modos? (s/n): ")
            if respuesta.lower() != 's':
                return

        # Configurar variable de entorno para ALSA
        os.environ['ALSA_CARD'] = '2'  # Usar la primera diadema por defecto

        # Iniciar canales
        recognizer1 = self.canal_espanol_ingles()
        time.sleep(1)  # Pequeña pausa entre inicializaciones
        recognizer2 = self.canal_ingles_espanol()

        if not recognizer1 and not recognizer2:
            print("❌ Error: No se pudo iniciar ningún canal")
            return

        print("\n✅ Sistema iniciado correctamente")
        print("Presiona Ctrl+C para detener")
        print("-" * 60)

        self.ejecutando = True

        try:
            while self.ejecutando:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n🛑 Deteniendo traductores...")
            if recognizer1:
                recognizer1.stop_continuous_recognition()
            if recognizer2:
                recognizer2.stop_continuous_recognition()
            self.p.terminate()
            print("✅ Sistema detenido")


# Versión alternativa usando método de archivos WAV temporales
class TraductorArchivosTemporales:
    def __init__(self, subscription_key, region):
        self.subscription_key = subscription_key
        self.region = region
        self.dispositivos = self.identificar_dispositivos()

    def identificar_dispositivos(self):
        """Identifica dispositivos de audio"""
        dispositivos = []
        try:
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Logitech' in line:
                    print(f"Encontrado: {line}")
                    dispositivos.append(line)
        except:
            pass
        return dispositivos

    def grabar_audio(self, duracion=5, dispositivo=2):
        """Graba audio desde un dispositivo específico"""
        filename = f"temp_audio_{dispositivo}.wav"
        cmd = f"arecord -D plughw:{dispositivo},0 -d {duracion} -f S16_LE -r 16000 -c 1 {filename}"
        subprocess.run(cmd, shell=True, capture_output=True)
        return filename

    def traducir_archivo(self, filename, idioma_origen, idioma_destino):
        """Traduce un archivo de audio"""
        speech_config = speechsdk.SpeechConfig(
            subscription=self.subscription_key,
            region=self.region
        )
        speech_config.speech_recognition_language = idioma_origen

        audio_input = speechsdk.audio.AudioConfig(filename=filename)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_input
        )

        result = recognizer.recognize_once()
        return result.text if result.reason == speechsdk.ResultReason.RecognizedSpeech else ""


# Script principal
if __name__ == "__main__":
    # Configuración
    AZURE_SPEECH_KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"
    AZURE_REGION = "eastus"

    print("🎧 TRADUCTOR BIDIRECCIONAL CON DIADEMAS LOGITECH")
    print("=" * 60)

    # Probar diferentes métodos
    print("\nSelecciona método de traducción:")
    print("1. Tiempo real (recomendado)")
    print("2. Por lotes (más estable)")

    metodo = input("Opción (1/2): ")

    if metodo == "2":
        print("\nModo por lotes - No implementado completamente")
        print("Usando modo tiempo real...")
        metodo = "1"

    if metodo == "1":
        traductor = TraductorRaspberryPi(AZURE_SPEECH_KEY, AZURE_REGION)
        traductor.iniciar()