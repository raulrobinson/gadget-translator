import os
import asyncio
import argparse
import aiohttp
import azure.cognitiveservices.speech as speechsdk
import websockets


# ===============================
# CLI ARGUMENTS
# ===============================

def parse_args():
    parser = argparse.ArgumentParser(description="WS Translator Server")

    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 9001)))

    parser.add_argument("--speech-key", default=os.getenv("SPEECH_KEY"))
    parser.add_argument("--speech-region", default=os.getenv("SPEECH_REGION"))

    parser.add_argument("--translator-key", default=os.getenv("TRANSLATOR_KEY"))
    parser.add_argument("--translator-region", default=os.getenv("TRANSLATOR_REGION"))

    parser.add_argument("--src-locale", default=os.getenv("SRC_LOCALE"))
    parser.add_argument("--tgt-lang", default=os.getenv("TGT_LANG"))
    parser.add_argument("--tts-voice", default=os.getenv("TTS_VOICE"))

    parser.add_argument("--sample-rate", type=int, default=int(os.getenv("SAMPLE_RATE", 16000)))
    parser.add_argument("--channels", type=int, default=int(os.getenv("CHANNELS", 1)))

    parser.add_argument("--name", default=os.getenv("NAME", "CHANNEL"))

    args = parser.parse_args()

    # Validación manual (opcional pero recomendable)
    required = [
        args.speech_key,
        args.speech_region,
        args.translator_key,
        args.translator_region,
        args.src_locale,
        args.tgt_lang,
        args.tts_voice
    ]

    if not all(required):
        raise RuntimeError("Missing required environment variables")

    return args


# ===============================
# TRANSLATION
# ===============================

async def translate_text(text, source_lang, target_lang, key, region):
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
    }

    url = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&from={source_lang}&to={target_lang}"
    body = [{"Text": text}]

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=body) as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            data = await resp.json()
            return data[0]["translations"][0]["text"]


# ===============================
# TTS
# ===============================

def tts_wav_bytes(text, speech_key, speech_region, voice):
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region
    )
    speech_config.speech_synthesis_voice_name = voice
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
    )

    synth = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None
    )

    result = synth.speak_text_async(text).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError("TTS failed")

    return result.audio_data


# ===============================
# CLIENT HANDLER
# ===============================

async def handle_client(ws, args):

    loop = asyncio.get_running_loop()
    text_queue = asyncio.Queue()

    speech_config = speechsdk.SpeechConfig(
        subscription=args.speech_key,
        region=args.speech_region
    )
    speech_config.speech_recognition_language = args.src_locale

    stream_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=args.sample_rate,
        bits_per_sample=16,
        channels=args.channels,
    )

    push_stream = speechsdk.audio.PushAudioInputStream(stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )

    speaking = False

    def on_recognized(evt):
        nonlocal speaking
        if speaking:
            return

        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            txt = (evt.result.text or "").strip()
            if txt:
                loop.call_soon_threadsafe(text_queue.put_nowait, txt)

    recognizer.recognized.connect(on_recognized)
    recognizer.start_continuous_recognition()

    await ws.send(f'{{"type":"ready","channel":"{args.name}"}}')

    async def recv_audio():
        async for msg in ws:
            if isinstance(msg, (bytes, bytearray)):
                push_stream.write(bytes(msg))

    async def process():
        nonlocal speaking
        while True:
            txt = await text_queue.get()

            await ws.send(f'{{"type":"stt","text":{txt!r}}}')

            translated = await translate_text(
                txt,
                args.src_locale.split("-")[0],
                args.tgt_lang,
                args.translator_key,
                args.translator_region
            )

            await ws.send(f'{{"type":"translate","text":{translated!r}}}')

            speaking = True
            recognizer.stop_continuous_recognition()

            wav = await loop.run_in_executor(
                None,
                tts_wav_bytes,
                translated,
                args.speech_key,
                args.speech_region,
                args.tts_voice
            )

            await ws.send(wav)

            speaking = False
            recognizer.start_continuous_recognition()

    await asyncio.gather(recv_audio(), process())


# ===============================
# MAIN
# ===============================

async def main():
    args = parse_args()

    print(f"[{args.name}] Running on ws://{args.host}:{args.port}")

    async with websockets.serve(
        lambda ws: handle_client(ws, args),
        args.host,
        args.port,
        max_size=None
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())