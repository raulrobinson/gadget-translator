import asyncio
import azure.cognitiveservices.speech as speechsdk
import queue
import threading
import numpy as np
import sounddevice as sd
import time


class TraductorTiempoReal:
    def __init__(self, subscription_key, region):
        """
        Inicializa el traductor con dos canales independientes

        Args:
            subscription_key: Azure Speech Services API key
            region: Región de Azure (ej: 'eastus', 'westus')
        """
        self.subscription_key = subscription_key
        self.region = region

        # Configuración de audio
        self.sample_rate = 16000
        self.chunk_size = 1024

        # Queues para los canales
        self.canal1_queue = queue.Queue()  # Spanish -> English
        self.canal2_queue = queue.Queue()  # English -> Spanish

        # Configuración de dispositivos (asume 2 micrófonos USB)
        self.devices = self._encontrar_dispositivos_audio()

    def _encontrar_dispositivos_audio(self):
        """Encuentra los dispositivos de audio disponibles"""
        devices = sd.query_devices()
        mic_indices = []

        print("Dispositivos de audio encontrados:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"[{i}] {device['name']} - Canales entrada: {device['max_input_channels']}")
                mic_indices.append(i)

        return mic_indices[:2]  # Tomamos los primeros 2 micrófonos

    def _crear_configuracion_reconocimiento(self, idioma_origen, device_index=None):
        """Crea configuración para reconocimiento de voz"""
        speech_config = speechsdk.SpeechConfig(
            subscription=self.subscription_key,
            region=self.region
        )
        speech_config.speech_recognition_language = idioma_origen

        if device_index is not None:
            audio_config = speechsdk.audio.AudioConfig(
                device_name=f"plughw:{device_index},0"
            )
        else:
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

        return speech_config, audio_config

    def _crear_configuracion_sintesis(self, idioma_destino, voz=None):
        """Crea configuración para síntesis de voz"""
        speech_config = speechsdk.SpeechConfig(
            subscription=self.subscription_key,
            region=self.region
        )

        # Configurar voz según idioma
        if idioma_destino == "es-ES":
            speech_config.speech_synthesis_voice_name = voz or "es-ES-ElviraNeural"
        elif idioma_destino == "en-US":
            speech_config.speech_synthesis_voice_name = voz or "en-US-JennyNeural"

        return speech_config

    def canal_espanol_ingles(self):
        """Canal 1: Español a Inglés"""
        try:
            # Configurar reconocimiento (Español)
            speech_config, audio_config = self._crear_configuracion_reconocimiento(
                "es-ES",
                device_index=self.devices[0] if len(self.devices) > 0 else None
            )

            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Configurar síntesis (Inglés)
            tts_config = self._crear_configuracion_sintesis("en-US")
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config)

            print("Canal 1 (ES->EN): Escuchando...")

            def handle_final_result(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto_espanol = evt.result.text
                    print(f"[ES->EN] Original: {texto_espanol}")

                    # Aquí iría la traducción (implementaremos después)
                    # Por ahora simulamos traducción
                    texto_ingles = f"[Translated]: {texto_espanol}"

                    # Sintetizar en inglés
                    result = synthesizer.speak_text_async(texto_ingles).get()
                    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        print(f"[ES->EN] Traducido: {texto_ingles}")
                    elif result.reason == speechsdk.ResultReason.Canceled:
                        print(f"[ES->EN] Error síntesis: {result.cancellation_details.reason}")

            recognizer.recognized.connect(handle_final_result)
            recognizer.start_continuous_recognition()

            return recognizer

        except Exception as e:
            print(f"Error en canal ES->EN: {e}")
            return None

    def canal_ingles_espanol(self):
        """Canal 2: Inglés a Español"""
        try:
            # Configurar reconocimiento (Inglés)
            speech_config, audio_config = self._crear_configuracion_reconocimiento(
                "en-US",
                device_index=self.devices[1] if len(self.devices) > 1 else None
            )

            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Configurar síntesis (Español)
            tts_config = self._crear_configuracion_sintesis("es-ES")
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config)

            print("Canal 2 (EN->ES): Escuchando...")

            def handle_final_result(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto_ingles = evt.result.text
                    print(f"[EN->ES] Original: {texto_ingles}")

                    # Aquí iría la traducción (implementaremos después)
                    texto_espanol = f"[Translated]: {texto_ingles}"

                    # Sintetizar en español
                    result = synthesizer.speak_text_async(texto_espanol).get()
                    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        print(f"[EN->ES] Traducido: {texto_espanol}")
                    elif result.reason == speechsdk.ResultReason.Canceled:
                        print(f"[EN->ES] Error síntesis: {result.cancellation_details.reason}")

            recognizer.recognized.connect(handle_final_result)
            recognizer.start_continuous_recognition()

            return recognizer

        except Exception as e:
            print(f"Error en canal EN->ES: {e}")
            return None

    def iniciar(self):
        """Inicia ambos canales de traducción"""
        print("Iniciando sistema de traducción en tiempo real...")
        print("=" * 50)

        # Iniciar canales
        recognizer1 = self.canal_espanol_ingles()
        recognizer2 = self.canal_ingles_espanol()

        if not recognizer1 and not recognizer2:
            print("Error: No se pudo iniciar ningún canal")
            return

        print("\nSistema funcionando. Presiona Ctrl+C para detener.")
        print("=" * 50)

        try:
            # Mantener el programa corriendo
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nDeteniendo traductores...")
            if recognizer1:
                recognizer1.stop_continuous_recognition()
            if recognizer2:
                recognizer2.stop_continuous_recognition()
            print("Traductores detenidos.")


# Versión mejorada con traducción real usando Azure Translator
class TraductorAzureCompleto(TraductorTiempoReal):
    def __init__(self, subscription_key, region, translator_key, translator_region):
        super().__init__(subscription_key, region)
        self.translator_key = translator_key
        self.translator_region = translator_region
        self.translator_endpoint = "https://api.cognitive.microsofttranslator.com"

    async def traducir_texto(self, texto, desde_idioma, hasta_idioma):
        """Traduce texto usando Azure Translator"""
        import aiohttp

        path = '/translate'
        constructed_url = self.translator_endpoint + path

        params = {
            'api-version': '3.0',
            'from': desde_idioma,
            'to': [hasta_idioma]
        }

        headers = {
            'Ocp-Apim-Subscription-Key': self.translator_key,
            'Ocp-Apim-Subscription-Region': self.translator_region,
            'Content-type': 'application/json'
        }

        body = [{'text': texto}]

        async with aiohttp.ClientSession() as session:
            async with session.post(constructed_url, params=params, headers=headers, json=body) as response:
                result = await response.json()
                return result[0]['translations'][0]['text']

    def canal_espanol_ingles(self):
        """Canal 1 con traducción real"""
        try:
            speech_config, audio_config = self._crear_configuracion_reconocimiento(
                "es-ES",
                device_index=self.devices[0] if len(self.devices) > 0 else None
            )

            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            tts_config = self._crear_configuracion_sintesis("en-US")
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config)

            print("Canal 1 (ES->EN): Escuchando...")

            def handle_final_result(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto_espanol = evt.result.text
                    print(f"[ES->EN] Original: {texto_espanol}")

                    # Traducir
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    texto_ingles = loop.run_until_complete(
                        self.traducir_texto(texto_espanol, "es", "en")
                    )

                    # Sintetizar
                    result = synthesizer.speak_text_async(texto_ingles).get()
                    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        print(f"[ES->EN] Traducido: {texto_ingles}")

            recognizer.recognized.connect(handle_final_result)
            recognizer.start_continuous_recognition()

            return recognizer

        except Exception as e:
            print(f"Error en canal ES->EN: {e}")
            return None

    def canal_ingles_espanol(self):
        """Canal 2 con traducción real"""
        try:
            speech_config, audio_config = self._crear_configuracion_reconocimiento(
                "en-US",
                device_index=self.devices[1] if len(self.devices) > 1 else None
            )

            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            tts_config = self._crear_configuracion_sintesis("es-ES")
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=tts_config)

            print("Canal 2 (EN->ES): Escuchando...")

            def handle_final_result(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    texto_ingles = evt.result.text
                    print(f"[EN->ES] Original: {texto_ingles}")

                    # Traducir
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    texto_espanol = loop.run_until_complete(
                        self.traducir_texto(texto_ingles, "en", "es")
                    )

                    # Sintetizar
                    result = synthesizer.speak_text_async(texto_espanol).get()
                    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        print(f"[EN->ES] Traducido: {texto_espanol}")

            recognizer.recognized.connect(handle_final_result)
            recognizer.start_continuous_recognition()

            return recognizer

        except Exception as e:
            print(f"Error en canal EN->ES: {e}")
            return None


# Script principal
if __name__ == "__main__":
    # Configura tus API keys aquí
    AZURE_SPEECH_KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"
    AZURE_REGION = "eastus"  # o la región donde tengas el servicio
    AZURE_TRANSLATOR_KEY = "eadeeea0de1b4f718ac400db2023d4ad"
    AZURE_TRANSLATOR_REGION = "eastus"

    print("Iniciando Traductor en Tiempo Real para Raspberry Pi 400")
    print("=" * 60)

    # Elegir versión (simplificada o completa)
    use_complete = True

    if use_complete and AZURE_TRANSLATOR_KEY != "eadeeea0de1b4f718ac400db2023d4ad":
        traductor = TraductorAzureCompleto(
            AZURE_SPEECH_KEY,
            AZURE_REGION,
            AZURE_TRANSLATOR_KEY,
            AZURE_TRANSLATOR_REGION
        )
    else:
        traductor = TraductorTiempoReal(AZURE_SPEECH_KEY, AZURE_REGION)
        if use_complete:
            print("ADVERTENCIA: Usando versión simplificada. Configura Translator Key para traducción real.")

    traductor.iniciar()