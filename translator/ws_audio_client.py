import asyncio
import argparse
import subprocess
import sys
import websockets


def parse_args():
    p = argparse.ArgumentParser("WS Audio Client (enterprise)")
    p.add_argument("--ws", required=True)
    p.add_argument("--capture", required=True)
    p.add_argument("--playback", required=True)
    p.add_argument("--name", default="CHANNEL")

    p.add_argument("--rate", type=int, default=16000)
    p.add_argument("--channels", type=int, default=1)
    p.add_argument("--chunk-ms", type=int, default=20)
    p.add_argument("--bytes-per-sample", type=int, default=2)
    return p.parse_args()


async def main():
    args = parse_args()

    chunk_bytes = int(args.rate * args.chunk_ms / 1000) * args.channels * args.bytes_per_sample

    arecord_cmd = [
        "arecord",
        "-D", args.capture,
        "-f", "S16_LE",
        "-r", str(args.rate),
        "-c", str(args.channels),
        "-t", "raw",
        "--buffer-size=64000",
        "--period-size=16000",
    ]

    play_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=30)  # backpressure playback

    print(f"[{args.name}] Connecting to: {args.ws}")

    async with websockets.connect(
        args.ws,
        max_size=None,
        ping_interval=20,
        ping_timeout=20
    ) as ws:
        print(f"[{args.name}] WS connected")

        arec = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        loop = asyncio.get_running_loop()
        stopped = asyncio.Event()

        async def uplink():
            try:
                while True:
                    data = await loop.run_in_executor(None, arec.stdout.read, chunk_bytes)
                    if not data:
                        await asyncio.sleep(0.01)
                        continue
                    await ws.send(data)
            except Exception:
                stopped.set()

        async def downlink():
            try:
                async for msg in ws:
                    if isinstance(msg, str):
                        print(f"[{args.name}] SERVER:", msg)
                        continue
                    # wav bytes
                    await play_q.put(msg)
            except Exception:
                stopped.set()

        async def playback_worker():
            """Reproduce WAV secuencialmente sin bloquear el event loop."""
            try:
                while not stopped.is_set():
                    try:
                        wav_bytes = await asyncio.wait_for(play_q.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue

                    # aplay leyendo WAV desde stdin
                    def _play():
                        p = subprocess.Popen(
                            ["aplay", "-D", args.playback, "-t", "wav", "-"],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        try:
                            p.stdin.write(wav_bytes)
                            p.stdin.close()
                            p.wait(timeout=20)
                        except Exception:
                            try:
                                p.kill()
                            except Exception:
                                pass

                    await loop.run_in_executor(None, _play)
            except asyncio.CancelledError:
                pass

        tasks = [
            asyncio.create_task(uplink()),
            asyncio.create_task(downlink()),
            asyncio.create_task(playback_worker()),
        ]

        try:
            await stopped.wait()
        finally:
            for t in tasks:
                t.cancel()
            try:
                arec.terminate()
            except Exception:
                pass
            try:
                arec.wait(timeout=2)
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)