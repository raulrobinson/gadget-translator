import os
import asyncio
import subprocess
import websockets
import tempfile
import argparse
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="WS Audio Client")

    parser.add_argument("--ws", required=True, help="WebSocket URL (ej: ws://127.0.0.1:9001)")
    parser.add_argument("--capture", required=True, help="ALSA capture device (ej: hw:0,0)")
    parser.add_argument("--playback", required=True, help="ALSA playback device (ej: plughw:0,0)")
    parser.add_argument("--name", default="CHANNEL", help="Nombre del canal (SPA-ENG, ENG-SPA)")

    parser.add_argument("--rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--chunk-ms", type=int, default=20)
    parser.add_argument("--bytes-per-sample", type=int, default=2)

    return parser.parse_args()


async def main():
    args = parse_args()

    CHUNK_BYTES = int(args.rate * args.chunk_ms / 1000) * args.channels * args.bytes_per_sample

    ARECORD_CMD = [
        "arecord",
        "-D", args.capture,
        "-f", "S16_LE",
        "-r", str(args.rate),
        "-c", str(args.channels),
        "-t", "raw",
        "--buffer-size=64000",
        "--period-size=16000",
    ]

    print(f"[{args.name}] Connecting to:", args.ws)

    async with websockets.connect(args.ws, max_size=None) as ws:
        print(f"[{args.name}] WS connected")

        arec = subprocess.Popen(ARECORD_CMD, stdout=subprocess.PIPE)
        loop = asyncio.get_running_loop()

        async def uplink():
            while True:
                data = await loop.run_in_executor(None, arec.stdout.read, CHUNK_BYTES)
                if not data:
                    await asyncio.sleep(0.01)
                    continue
                await ws.send(data)

        async def downlink():
            async for msg in ws:

                if isinstance(msg, str):
                    print(f"[{args.name}] SERVER:", msg)
                    continue

                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(msg)
                    wav_path = f.name

                subprocess.Popen(
                    ["aplay", "-D", args.playback, wav_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                os.remove(wav_path)

        await asyncio.gather(uplink(), downlink())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)