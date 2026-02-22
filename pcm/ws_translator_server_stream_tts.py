import json
import asyncio
import argparse
import aiohttp
import websockets
import azure.cognitiveservices.speech as speechsdk


def parse_args():
    p = argparse.ArgumentParser("WS Translator Server (TTS streaming)")

    p.add_argument("--name", default=os.getenv("NAME", "CHANNEL"))
    p.add_argument("--port", type=int, default=int(os.getenv("PORT")))

    p.add_argument("--speech-key", default=os.getenv("SPEECH_KEY"))
    p.add_argument("--speech-region", default=os.getenv("SPEECH_REGION"))

    p.add_argument("--translator-key", default=os.getenv("TRANSLATOR_KEY"))
    p.add_argument("--translator-region", default=os.getenv("TRANSLATOR_REGION"))

    p.add_argument("--src-locale", default=os.getenv("SRC_LOCALE"))
    p.add_argument("--tgt-lang", default=os.getenv("TGT_LANG"))
    p.add_argument("--tts-voice", default=os.getenv("TTS_VOICE"))

    p.add_argument("--sample-rate", type=int, default=os.getenv("RATE", 16000))
    p.add_argument("--channels", type=int, default=os.getenv("CHANNELS", 1))

    return p.parse_args()


async def translate_text(session: aiohttp.ClientSession, key: str, region: str, tgt_lang: str, text: str) -> str:
    url = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={tgt_lang}"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
    }
    async with session.post(url, headers=headers, json=[{"Text": text}], timeout=aiohttp.ClientTimeout(total=10)) as resp:
        data = await resp.json()
        return data[0]["translations"][0]["text"]


class TtsPushCallback(speechsdk.audio.PushAudioOutputStreamCallback):
    """
    Azure TTS irá llamando write(audio_buffer) mientras va sintetizando.
    Nosotros empujamos esos bytes a una asyncio.Queue para mandarlos por WS.
    """
    def __init__(self, loop: asyncio.AbstractEventLoop, q: asyncio.Queue):
        super().__init__()
        self.loop = loop
        self.q = q
        self.closed = False

    def write(self, audio_buffer: memoryview) -> int:
        if self.closed:
            return 0
        data = bytes(audio_buffer)
        # thread-safe -> cola asyncio
        self.loop.call_soon_threadsafe(self.q.put_nowait, data)
        return len(data)

    def close(self) -> None:
        self.closed = True
        # sentinel: None indica fin de stream
        self.loop.call_soon_threadsafe(self.q.put_nowait, None)


def build_streaming_synth(loop, q, speech_key, speech_region, tts_voice):
    cfg = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    cfg.speech_synthesis_voice_name = tts_voice

    # CRÍTICO: salida RAW PCM (no RIFF/WAV) para stream real
    cfg.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
    )

    cb = TtsPushCallback(loop, q)
    push_stream = speechsdk.audio.PushAudioOutputStream(cb)
    audio_out = speechsdk.audio.AudioConfig(stream=push_stream)

    synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_out)
    return synth


async def handle_client(ws: websockets.WebSocketServerProtocol, args):
    loop = asyncio.get_running_loop()

    # --- Señal listo ---
    await ws.send(json.dumps({"type": "ready", "channel": args.name}, ensure_ascii=False))

    # --- Colas ---
    audio_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=300)   # audio crudo hacia STT
    text_q: asyncio.Queue[str] = asyncio.Queue(maxsize=50)       # frases finales
    closed = asyncio.Event()

    speaking = False  # evita re-entradas mientras TTS está sonando

    # --- Azure STT (streaming entrada) ---
    speech_cfg = speechsdk.SpeechConfig(subscription=args.speech_key, region=args.speech_region)
    speech_cfg.speech_recognition_language = args.src_locale

    fmt = speechsdk.audio.AudioStreamFormat(samples_per_second=args.sample_rate, bits_per_sample=16, channels=args.channels)
    push_in = speechsdk.audio.PushAudioInputStream(fmt)
    audio_in_cfg = speechsdk.audio.AudioConfig(stream=push_in)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_cfg, audio_config=audio_in_cfg)

    def on_recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        nonlocal speaking
        try:
            if speaking:
                return
            if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech:
                return
            text = (evt.result.text or "").strip()
            if not text:
                return
            loop.call_soon_threadsafe(text_q.put_nowait, text)
        except Exception:
            pass

    recognizer.recognized.connect(on_recognized)
    recognizer.start_continuous_recognition()

    async def ws_reader():
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    await audio_q.put(msg)  # backpressure
        finally:
            closed.set()

    async def stt_audio_writer():
        try:
            while not closed.is_set():
                try:
                    chunk = await asyncio.wait_for(audio_q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                push_in.write(chunk)
        finally:
            try:
                push_in.close()
            except Exception:
                pass

    async def tts_sender(pcm_q: asyncio.Queue):
        """
        Lee PCM raw chunks desde pcm_q y los manda por WS.
        pcm_q recibe bytes y un None al final.
        """
        while True:
            chunk = await pcm_q.get()
            if chunk is None:
                break
            await ws.send(chunk)  # binario PCM

    async def pipeline_worker():
        nonlocal speaking
        async with aiohttp.ClientSession() as session:
            while not closed.is_set():
                try:
                    text = await asyncio.wait_for(text_q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                try:
                    speaking = True
                    await ws.send(json.dumps({"type": "stt", "text": text}, ensure_ascii=False))

                    translated = await translate_text(
                        session,
                        args.translator_key,
                        args.translator_region,
                        args.tgt_lang,
                        text
                    )
                    await ws.send(json.dumps({"type": "translate", "text": translated}, ensure_ascii=False))
                    await ws.send(json.dumps({"type": "tts_start"}, ensure_ascii=False))

                    # --- TTS Streaming ---
                    pcm_q: asyncio.Queue = asyncio.Queue(maxsize=2000)

                    synth = build_streaming_synth(
                        loop, pcm_q,
                        args.speech_key, args.speech_region, args.tts_voice
                    )

                    # Lanzamos sender que va mandando chunks mientras se sintetiza
                    sender_task = asyncio.create_task(tts_sender(pcm_q))

                    # speak_text_async().get() bloquea, así que lo hacemos en executor
                    def _do_speak():
                        res = synth.speak_text_async(translated).get()
                        return res.reason

                    reason = await loop.run_in_executor(None, _do_speak)

                    # cuando termina, el callback close() ya habrá metido None en la cola
                    await sender_task

                    if reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                        await ws.send(json.dumps({"type": "error", "error": f"TTS failed: {reason}"}, ensure_ascii=False))

                    await ws.send(json.dumps({"type": "tts_end"}, ensure_ascii=False))

                    # NO usamos synth.close() (no existe en tu build)
                    del synth

                except Exception as e:
                    try:
                        await ws.send(json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False))
                    except Exception:
                        pass
                finally:
                    speaking = False

    tasks = [
        asyncio.create_task(ws_reader()),
        asyncio.create_task(stt_audio_writer()),
        asyncio.create_task(pipeline_worker()),
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


async def main():
    args = parse_args()
    print(f"[{args.name}] WS Translator running on ws://{args.host}:{args.port}")

    async with websockets.serve(
        lambda ws: handle_client(ws, args),
        args.host,
        args.port,
        max_size=50_000_000,
        ping_interval=20,
        ping_timeout=20,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())