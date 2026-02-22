import os
import json
import asyncio
import argparse
import websockets
import aiohttp
import azure.cognitiveservices.speech as speechsdk


# ==========================
# ARGUMENTOS
# ==========================

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


# ==========================
# TRANSLATE
# ==========================

async def translate_text(session, key, region, tgt_lang, text):
    url = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={tgt_lang}"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
    }

    async with session.post(
        url,
        headers=headers,
        json=[{"Text": text}],
        timeout=aiohttp.ClientTimeout(total=10)
    ) as resp:
        data = await resp.json()
        return data[0]["translations"][0]["text"]


# ==========================
# TTS BUILDER
# ==========================

def build_synthesizer(speech_key, speech_region, tts_voice):
    config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    config.speech_synthesis_voice_name = tts_voice
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
    )
    return speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)


# ==========================
# CLIENT HANDLER
# ==========================

async def handle_client(ws, args):
    loop = asyncio.get_running_loop()

    await ws.send(json.dumps({"type": "ready", "channel": args.name}, ensure_ascii=False))

    audio_q = asyncio.Queue(maxsize=200)
    text_q = asyncio.Queue(maxsize=50)

    speaking = False
    closed = asyncio.Event()

    # ===== Azure Recognizer =====

    speech_config = speechsdk.SpeechConfig(
        subscription=args.speech_key,
        region=args.speech_region
    )
    speech_config.speech_recognition_language = args.src_locale

    stream_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=args.sample_rate,
        bits_per_sample=16,
        channels=args.channels
    )

    push_stream = speechsdk.audio.PushAudioInputStream(stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )

    def on_recognized(evt):
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

    # ==========================
    # WS READER
    # ==========================

    async def ws_reader():
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    await audio_q.put(msg)
        finally:
            closed.set()

    # ==========================
    # AUDIO WRITER
    # ==========================

    async def audio_writer():
        try:
            while not closed.is_set():
                try:
                    chunk = await asyncio.wait_for(audio_q.get(), timeout=1)
                except asyncio.TimeoutError:
                    continue

                push_stream.write(chunk)
        finally:
            try:
                push_stream.close()
            except Exception:
                pass

    # ==========================
    # TTS WORKER
    # ==========================

    async def tts_worker():
        nonlocal speaking

        async with aiohttp.ClientSession() as session:

            while not closed.is_set():

                try:
                    text = await asyncio.wait_for(text_q.get(), timeout=1)
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

                    # ===== TTS seguro =====

                    synth = build_synthesizer(
                        args.speech_key,
                        args.speech_region,
                        args.tts_voice
                    )

                    result = await loop.run_in_executor(
                        None,
                        lambda: synth.speak_text_async(translated).get()
                    )

                    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                        raise RuntimeError("TTS failed")

                    wav_bytes = result.audio_data

                    del synth  # compatible ARM

                    await ws.send(wav_bytes)

                except Exception as e:
                    await ws.send(json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False))

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


# ==========================
# MAIN
# ==========================

async def main():
    args = parse_args()

    print(f"[{args.name}] running on ws://{args.host}:{args.port}")

    async with websockets.serve(
        lambda ws: handle_client(ws, args),
        args.host,
        args.port,
        max_size=10_000_000,
        ping_interval=20,
        ping_timeout=20
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())