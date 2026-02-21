import os
import json
import asyncio
import argparse
import websockets
import aiohttp
import azure.cognitiveservices.speech as speechsdk


def parse_args():
    p = argparse.ArgumentParser("WS Translator Server (enterprise)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, required=True)

    p.add_argument("--speech-key", required=True)
    p.add_argument("--speech-region", required=True)

    p.add_argument("--translator-key", required=True)
    p.add_argument("--translator-region", required=True)

    p.add_argument("--src-locale", required=True)
    p.add_argument("--tgt-lang", required=True)
    p.add_argument("--tts-voice", required=True)

    p.add_argument("--name", default="CHANNEL")
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    return p.parse_args()


async def translate_text(session: aiohttp.ClientSession, key: str, region: str, tgt_lang: str, text: str) -> str:
    url = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={tgt_lang}"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
    }
    payload = [{"Text": text}]
    async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        data = await resp.json()
        return data[0]["translations"][0]["text"]


def build_wav_synthesizer(speech_key: str, speech_region: str, tts_voice: str):
    tts_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    tts_config.speech_synthesis_voice_name = tts_voice
    # WAV RIFF PCM 16k mono 16-bit (fácil de reproducir)
    tts_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
    )
    return speechsdk.SpeechSynthesizer(speech_config=tts_config, audio_config=None)


async def handle_client(ws: websockets.WebSocketServerProtocol, args):
    loop = asyncio.get_running_loop()

    # Aviso listo
    await ws.send(json.dumps({"type": "ready", "channel": args.name}))

    # Cola de audio crudo (desde cliente hacia Azure)
    audio_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)  # backpressure

    # Cola de textos reconocidos para procesar secuencial
    text_q: asyncio.Queue[str] = asyncio.Queue(maxsize=50)

    speaking = False
    closed = asyncio.Event()

    # ---- Azure Speech Recognizer (streaming continuo) ----
    speech_config = speechsdk.SpeechConfig(subscription=args.speech_key, region=args.speech_region)
    speech_config.speech_recognition_language = args.src_locale

    stream_format = speechsdk.audio.AudioStreamFormat(samples_per_second=args.sample_rate,
                                                     bits_per_sample=16,
                                                     channels=args.channels)
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    def on_recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        nonlocal speaking
        try:
            res = evt.result
            if res.reason != speechsdk.ResultReason.RecognizedSpeech:
                return
            text = (res.text or "").strip()
            if not text:
                return
            # Evitar re-entradas mientras estamos sintetizando/enviando
            if speaking:
                return
            loop.call_soon_threadsafe(text_q.put_nowait, text)
        except Exception:
            # No tumbar el server por un callback
            pass

    def on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        try:
            loop.call_soon_threadsafe(
                asyncio.create_task,
                ws.send(json.dumps({"type": "stt_canceled", "details": str(evt)}))
            )
        except Exception:
            pass

    def on_session_stopped(_evt):
        # Sesión parada: suele ocurrir por error o desconexión
        try:
            loop.call_soon_threadsafe(
                asyncio.create_task,
                ws.send(json.dumps({"type": "stt_session_stopped"}))
            )
        except Exception:
            pass

    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_stopped.connect(on_session_stopped)

    recognizer.start_continuous_recognition()

    async def ws_reader():
        """Lee audio del WS y lo pone en la cola con backpressure."""
        try:
            async for msg in ws:
                if isinstance(msg, str):
                    # opcional: comandos/control
                    continue
                # Backpressure: si se llena, esperamos (no reventar RAM)
                await audio_q.put(msg)
        finally:
            closed.set()

    async def audio_writer():
        """Saca de la cola y escribe al PushStream de Azure."""
        try:
            while not closed.is_set():
                try:
                    chunk = await asyncio.wait_for(audio_q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                # PushStream es sync; esto es rápido (memcpy)
                push_stream.write(chunk)
        finally:
            try:
                push_stream.close()
            except Exception:
                pass

    async def tts_worker():
        """Procesa textos uno por uno: translate + TTS + envío WAV."""
        nonlocal speaking
        async with aiohttp.ClientSession() as session:
            while not closed.is_set():
                try:
                    text = await asyncio.wait_for(text_q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                try:
                    speaking = True
                    await ws.send(json.dumps({"type": "stt", "text": text}))

                    translated = await translate_text(
                        session,
                        args.translator_key,
                        args.translator_region,
                        args.tgt_lang,
                        text
                    )
                    await ws.send(json.dumps({"type": "translate", "text": translated}))

                    # TTS (sync callback)
                    synth = build_wav_synthesizer(args.speech_key, args.speech_region, args.tts_voice)

                    done = asyncio.Event()
                    audio_bytes_holder = {"data": None, "err": None}

                    def on_success(result: speechsdk.SpeechSynthesisResult):
                        audio_bytes_holder["data"] = result.audio_data
                        loop.call_soon_threadsafe(done.set)

                    def on_error(err):
                        audio_bytes_holder["err"] = str(err)
                        loop.call_soon_threadsafe(done.set)

                    synth.speak_text_async(translated, on_success, on_error)
                    await asyncio.wait_for(done.wait(), timeout=15.0)
                    synth.close()

                    if audio_bytes_holder["err"]:
                        await ws.send(json.dumps({"type": "tts_error", "error": audio_bytes_holder["err"]}))
                    else:
                        # WAV completo (RIFF) hacia cliente
                        await ws.send(audio_bytes_holder["data"])

                except Exception as e:
                    try:
                        await ws.send(json.dumps({"type": "error", "error": str(e)}))
                    except Exception:
                        pass
                finally:
                    speaking = False

    tasks = [
        asyncio.create_task(ws_reader()),
        asyncio.create_task(audio_writer()),
        asyncio.create_task(tts_worker()),
    ]

    try:
        await closed.wait()
    finally:
        for t in tasks:
            t.cancel()

        try:
            recognizer.stop_continuous_recognition()
        except Exception:
            pass

        try:
            recognizer.recognized.disconnect(on_recognized)
        except Exception:
            pass


async def main():
    args = parse_args()
    print(f"[{args.name}] running on ws://{args.host}:{args.port}")

    async with websockets.serve(
        lambda ws: handle_client(ws, args),
        args.host,
        args.port,
        max_size=10_000_000,
        ping_interval=20,
        ping_timeout=20,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())