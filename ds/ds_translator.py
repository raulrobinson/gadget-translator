# translator_optimized.py
import azure.cognitiveservices.speech as speechsdk
import time
import threading
from queue import Queue
import signal
import sys


class TraductorOptimizado:
    def __init__(self, subscription_key, region):
        self.subscription_key = subscription_key
        self.region = region

        # Configuración de dispositivos (hardcodeado basado en tus pruebas)
        self.dispositivos = {
            'espanol': 'plughw:2,0',  # Canal 1 - Español
            'ingles': 'plughw:3,0'  # Canal 2 - Inglés
        }

        # Control de cuota
        self.contador_llamadas = 0
        self.limite_por_minuto = 20  # Ajusta según tu plan de Azure
        self.tiempo_inicio = time.time()

        # Colas para mensajes
        self.cola_salida = Queue()

        # Flag de ejecución
        self.ejecutando = False

        print("\n🎧 TRADUCTOR OPTIMIZADO - RASPBERRY PI 400")
        print("=" * 60)
        print(f"Dispositivo Español: {self.dispositivos['espanol']}")
        print(f"Dispositivo Inglés: {self.dispositivos['ingles']}")
        print("=" * 60)

    def verificar_cuota(self):
        """Verifica si podemos hacer otra llamada"""
        ahora = time.time()
        if ahora - self.tiempo_inicio > 60:  # Pasó un minuto
            self.contador_llamadas = 0
            self.tiempo_inicio = ahora

        if self.contador_llamadas >= self.limite_por_minuto:
            print(f"⚠️  Límite de cuota alcanzado. Espera un momento...")
            time.sleep(5)
            return False
        return True

    def canal_espanol_ingles(self):
        """Canal 1: Español a Inglés"""
        try:
            # Configuración de reconocimiento
            speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            speech_config.speech_recognition_language = "es-ES"
            speech_config.set_property(
                speechsdk.PropertyId.SpeechServiceConnection_EnableAudioProcessing,
                "false"
            )

            # Audio config específico
            audio_config = speechsdk.audio.AudioConfig(
                device_name=self.dispositivos['espanol']
            )

            # Crear reconocedor con configuración optimizada
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Configuración de síntesis
            tts_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            tts_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config)

            def handle_recognized(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto = evt.result.text
                    if texto.strip():
                        self.contador_llamadas += 1
                        print(f"\n🎤 [ES] {texto}")

                        if self.verificar_cuota():
                            # Traducción simulada (por ahora)
                            texto_en = f"Translation: {texto}"
                            print(f"🔊 [EN] {texto_en}")

                            try:
                                # Sintetizar
                                result = synthesizer.speak_text_async(texto_en).get()
                                if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                                    print(f"⚠️ Error síntesis: {result.reason}")
                            except Exception as e:
                                print(f"⚠️ Error síntesis: {e}")

            def handle_canceled(evt):
                details = evt.result.cancellation_details
                if details.reason == speechsdk.CancellationReason.Error:
                    if "Quota" in str(details.error_details):
                        print("⚠️ Cuota excedida. Esperando 10 segundos...")
                        time.sleep(10)
                    else:
                        print(f"⚠️ Error: {details.error_details}")

            recognizer.recognized.connect(handle_recognized)
            recognizer.canceled.connect(handle_canceled)

            return recognizer

        except Exception as e:
            print(f"Error en canal ES->EN: {e}")
            return None

    def canal_ingles_espanol(self):
        """Canal 2: Inglés a Español"""
        try:
            # Configuración de reconocimiento
            speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            speech_config.speech_recognition_language = "en-US"
            speech_config.set_property(
                speechsdk.PropertyId.SpeechServiceConnection_EnableAudioProcessing,
                "false"
            )

            # Audio config específico
            audio_config = speechsdk.audio.AudioConfig(
                device_name=self.dispositivos['ingles']
            )

            # Crear reconocedor
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Configuración de síntesis
            tts_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            tts_config.speech_synthesis_voice_name = "es-ES-ElviraNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config)

            def handle_recognized(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto = evt.result.text
                    if texto.strip():
                        self.contador_llamadas += 1
                        print(f"\n🎤 [EN] {texto}")

                        if self.verificar_cuota():
                            texto_es = f"Traducción: {texto}"
                            print(f"🔊 [ES] {texto_es}")

                            try:
                                result = synthesizer.speak_text_async(texto_es).get()
                                if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                                    print(f"⚠️ Error síntesis: {result.reason}")
                            except Exception as e:
                                print(f"⚠️ Error síntesis: {e}")

            def handle_canceled(evt):
                details = evt.result.cancellation_details
                if details.reason == speechsdk.CancellationReason.Error:
                    if "Quota" in str(details.error_details):
                        print("⚠️ Cuota excedida. Esperando...")
                        time.sleep(10)
                    else:
                        print(f"⚠️ Error: {details.error_details}")

            recognizer.recognized.connect(handle_recognized)
            recognizer.canceled.connect(handle_canceled)

            return recognizer

        except Exception as e:
            print(f"Error en canal EN->ES: {e}")
            return None

    def iniciar(self):
        """Inicia ambos canales con manejo de cuota"""
        print("\n🚀 Iniciando sistema de traducción...")

        # Inicializar canales
        recognizer_es = self.canal_espanol_ingles()
        time.sleep(1)
        recognizer_en = self.canal_ingles_espanol()

        if not recognizer_es and not recognizer_en:
            print("❌ No se pudo iniciar ningún canal")
            return

        # Iniciar reconocimiento
        if recognizer_es:
            recognizer_es.start_continuous_recognition()
            print("✅ Canal ES->EN activo")

        if recognizer_en:
            recognizer_en.start_continuous_recognition()
            print("✅ Canal EN->ES activo")

        self.ejecutando = True
        print("\n" + "=" * 60)
        print("🎯 SISTEMA ACTIVO - Habla en los micrófonos")
        print("Presiona Ctrl+C para detener")
        print("=" * 60)

        # Monitor de cuota
        def monitor_cuota():
            while self.ejecutando:
                time.sleep(30)  # Cada 30 segundos
                if self.contador_llamadas > 0:
                    print(f"\n📊 Estadísticas:")
                    print(f"   Llamadas este minuto: {self.contador_llamadas}/{self.limite_por_minuto}")

        monitor_thread = threading.Thread(target=monitor_cuota, daemon=True)
        monitor_thread.start()

        try:
            while self.ejecutando:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n🛑 Deteniendo...")
            self.ejecutando = False

            if recognizer_es:
                recognizer_es.stop_continuous_recognition()
            if recognizer_en:
                recognizer_en.stop_continuous_recognition()

            print("✅ Sistema detenido")


# Versión con traducción real usando API gratuita
class TraductorConTraduccionReal(TraductorOptimizado):
    def __init__(self, subscription_key, region):
        super().__init__(subscription_key, region)
        self.ultima_traduccion = {}

    def traducir_texto(self, texto, idioma_origen, idioma_destino):
        """Traducción simple usando diccionario (gratuito)"""
        # Por ahora solo un placeholder - puedes integrar Google Translate API o similar
        traducciones = {
            "hola": "hello",
            "hello": "hola",
            "gracias": "thank you",
            "thank you": "gracias",
            "adiós": "goodbye",
            "goodbye": "adiós",
            "por favor": "please",
            "please": "por favor",
            "sí": "yes",
            "yes": "sí",
            "no": "no",
        }

        texto_lower = texto.lower().strip()
        if texto_lower in traducciones:
            return traducciones[texto_lower]
        else:
            # Si no está en el diccionario, devolver el texto original
            return f"[{idioma_destino}] {texto}"

    def canal_espanol_ingles(self):
        """Canal 1 con traducción simple"""
        try:
            speech_config = speechsdk.SpeechConfig(self.subscription_key, self.region)
            speech_config.speech_recognition_language = "es-ES"

            audio_config = speechsdk.audio.AudioConfig(device_name=self.dispositivos['espanol'])
            recognizer = speechsdk.SpeechRecognizer(speech_config, audio_config)

            tts_config = speechsdk.SpeechConfig(self.subscription_key, self.region)
            tts_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config)

            def handle_recognized(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto = evt.result.text
                    if texto.strip():
                        print(f"\n🎤 [ES] {texto}")

                        # Traducir
                        texto_en = self.traducir_texto(texto, "es", "en")
                        print(f"🔄 [EN] {texto_en}")

                        # Sintetizar
                        try:
                            result = synthesizer.speak_text_async(texto_en).get()
                        except Exception as e:
                            print(f"⚠️ Error síntesis: {e}")

            recognizer.recognized.connect(handle_recognized)
            return recognizer

        except Exception as e:
            print(f"Error: {e}")
            return None


# Script principal con manejo de señal
def signal_handler(sig, frame):
    print("\n\n🛑 Recibida señal de terminación")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    # Configuración - ¡REEMPLAZA CON TUS KEYS!
    AZURE_SPEECH_KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"
    AZURE_REGION = "eastus"

    print("=" * 60)
    print("🎯 TRADUCTOR BIDIRECCIONAL - RASPBERRY PI 400")
    print("=" * 60)

    if AZURE_SPEECH_KEY == "5ae052154f2b4437a2bd13e2a8b1e1fc":
        print("\n⚠️  Configura tu API key de Azure Speech")
        print("Edita el archivo y reemplaza '5ae052154f2b4437a2bd13e2a8b1e1fc'")
        exit(1)

    # Seleccionar modo
    print("\nModos disponibles:")
    print("1. Modo optimizado (recomendado)")
    print("2. Modo con traducción simple")
    print("3. Modo prueba (solo reconocimiento)")

    modo = input("Selecciona modo (1-3): ")

    if modo == "2":
        traductor = TraductorConTraduccionReal(AZURE_SPEECH_KEY, AZURE_REGION)
    elif modo == "3":
        print("\n🔧 MODO PRUEBA - Solo reconocimiento")
        traductor = TraductorOptimizado(AZURE_SPEECH_KEY, AZURE_REGION)
        traductor.limite_por_minuto = 100  # Límite más alto para prueba
    else:
        traductor = TraductorOptimizado(AZURE_SPEECH_KEY, AZURE_REGION)

    # Ajustar límite según tu plan de Azure
    print(f"\n📊 Límite configurado: {traductor.limite_por_minuto} llamadas/minuto")

    traductor.iniciar()