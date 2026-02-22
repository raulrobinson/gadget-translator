# ws_client.py
import asyncio
import websockets
import json
import pyaudio
import threading
import time
import signal
import sys
from collections import deque


class WSClientDiademas:
    def __init__(self, server_host, server_port_es, server_port_en, speech_key, speech_region):
        """
        Cliente WebSocket para dos diademas
        server_host: IP del servidor (ej: 'localhost' o '192.168.1.x')
        server_port_es: Puerto para canal Español->Inglés
        server_port_en: Puerto para canal Inglés->Español
        """
        self.server_host = server_host
        self.server_port_es = server_port_es
        self.server_port_en = server_port_en

        self.speech_key = speech_key
        self.speech_region = speech_region

        # Configuración de audio
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024

        # Dispositivos (ajusta según tu sistema)
        self.dispositivos = {
            'espanol': 2,  # hw:2,0 - Logitech 1
            'ingles': 3  # hw:3,0 - Logitech 2
        }

        # Inicializar PyAudio
        self.p = pyaudio.PyAudio()

        # Control de ejecución
        self.ejecutando = False

        # Buffers para audio
        self.buffer_es = deque(maxlen=50)
        self.buffer_en = deque(maxlen=50)

        print("\n" + "=" * 70)
        print("🎯 CLIENTE WEBSOCKET PARA DIADEMAS LOGITECH".center(70))
        print("=" * 70)
        print(f"Servidor: {server_host}")
        print(f"Puerto ES->EN: {server_port_es}")
        print(f"Puerto EN->ES: {server_port_en}")
        print(f"Dispositivo Español: hw:{self.dispositivos['espanol']},0")
        print(f"Dispositivo Inglés: hw:{self.dispositivos['ingles']},0")
        print("=" * 70)

    async def canal_espanol(self):
        """Canal Español -> Inglés"""
        uri = f"ws://{self.server_host}:{self.server_port_es}"

        print(f"\n🎤 Conectando canal ES->EN a {uri}...")

        try:
            async with websockets.connect(
                    uri,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=10_000_000
            ) as websocket:
                print("✅ Canal ES->EN conectado")

                # Abrir stream de audio
                stream = self.p.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=self.dispositivos['espanol'],
                    frames_per_buffer=self.chunk
                )

                # Tarea para enviar audio
                async def enviar_audio():
                    while self.ejecutando:
                        try:
                            # Leer audio del micrófono
                            data = stream.read(self.chunk, exception_on_overflow=False)
                            await websocket.send(data)
                            await asyncio.sleep(0.01)  # Pequeña pausa
                        except Exception as e:
                            print(f"Error enviando audio ES: {e}")
                            break

                # Tarea para recibir respuestas
                async def recibir_respuestas():
                    while self.ejecutando:
                        try:
                            msg = await websocket.recv()

                            if isinstance(msg, bytes):
                                # Es audio TTS
                                print(f"   🔊 [ES->EN] Reproduciendo audio...")
                                # Aquí reproducirías el audio recibido
                                # Por ahora solo indicamos que llega
                                pass
                            else:
                                # Es mensaje JSON
                                data = json.loads(msg)
                                if data.get('type') == 'stt':
                                    print(f"\n📝 [ES] {data['text']}")
                                elif data.get('type') == 'translate':
                                    print(f"   ➡️ [EN] {data['text']}")
                                elif data.get('type') == 'error':
                                    print(f"   ⚠️ Error: {data['error']}")
                                elif data.get('type') == 'ready':
                                    print(f"   ✅ Servidor listo: {data['channel']}")

                        except Exception as e:
                            if self.ejecutando:
                                print(f"Error recibiendo ES: {e}")
                            break

                # Ejecutar ambas tareas
                await asyncio.gather(
                    enviar_audio(),
                    recibir_respuestas()
                )

        except Exception as e:
            print(f"❌ Error en canal ES->EN: {e}")
        finally:
            if 'stream' in locals():
                stream.close()

    async def canal_ingles(self):
        """Canal Inglés -> Español"""
        uri = f"ws://{self.server_host}:{self.server_port_en}"

        print(f"\n🎤 Conectando canal EN->ES a {uri}...")

        try:
            async with websockets.connect(
                    uri,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=10_000_000
            ) as websocket:
                print("✅ Canal EN->ES conectado")

                # Abrir stream de audio
                stream = self.p.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=self.dispositivos['ingles'],
                    frames_per_buffer=self.chunk
                )

                async def enviar_audio():
                    while self.ejecutando:
                        try:
                            data = stream.read(self.chunk, exception_on_overflow=False)
                            await websocket.send(data)
                            await asyncio.sleep(0.01)
                        except Exception as e:
                            print(f"Error enviando audio EN: {e}")
                            break

                async def recibir_respuestas():
                    while self.ejecutando:
                        try:
                            msg = await websocket.recv()

                            if isinstance(msg, bytes):
                                print(f"   🔊 [EN->ES] Reproduciendo audio...")
                            else:
                                data = json.loads(msg)
                                if data.get('type') == 'stt':
                                    print(f"\n📝 [EN] {data['text']}")
                                elif data.get('type') == 'translate':
                                    print(f"   ➡️ [ES] {data['text']}")
                                elif data.get('type') == 'error':
                                    print(f"   ⚠️ Error: {data['error']}")
                                elif data.get('type') == 'ready':
                                    print(f"   ✅ Servidor listo: {data['channel']}")

                        except Exception as e:
                            if self.ejecutando:
                                print(f"Error recibiendo EN: {e}")
                            break

                await asyncio.gather(
                    enviar_audio(),
                    recibir_respuestas()
                )

        except Exception as e:
            print(f"❌ Error en canal EN->ES: {e}")
        finally:
            if 'stream' in locals():
                stream.close()

    async def iniciar(self):
        """Inicia ambos canales concurrentemente"""
        self.ejecutando = True

        print("\n🚀 Iniciando canales...")

        # Ejecutar ambos canales concurrentemente
        await asyncio.gather(
            self.canal_espanol(),
            self.canal_ingles(),
            return_exceptions=True
        )


def signal_handler(sig, frame):
    print("\n\n🛑 Deteniendo cliente...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    # Configuración - AJUSTA SEGÚN TUS DATOS
    SERVER_HOST = "localhost"  # IP del servidor
    SERVER_PORT_ES = 9001  # Puerto para Español->Inglés
    SERVER_PORT_EN = 9002  # Puerto para Inglés->Español

    # Tus keys de Azure (para el servidor)
    SPEECH_KEY = "5ae052154f2b4437a2bd13e2a8b1e1fc"
    SPEECH_REGION = "eastus"

    print("=" * 70)
    print("CLIENTE WEBSOCKET PARA TRADUCCIÓN BIDIRECCIONAL".center(70))
    print("=" * 70)

    # Verificar dependencias
    try:
        import websockets

        print("✅ Dependencias OK")
    except ImportError:
        print("\n📦 Instalando dependencias...")
        import os

        os.system("pip install websockets")

    # Crear y ejecutar cliente
    cliente = WSClientDiademas(
        SERVER_HOST,
        SERVER_PORT_ES,
        SERVER_PORT_EN,
        SPEECH_KEY,
        SPEECH_REGION
    )

    # Ejecutar
    asyncio.run(cliente.iniciar())