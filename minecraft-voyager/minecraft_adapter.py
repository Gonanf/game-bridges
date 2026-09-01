# minecraft_adapter.py – Minecraft Voyager adapter with freellmapi (fusion) LLM
# - Real mode: launches Voyager (NodeJS, MineDojo/Voyager) and bridges its
#   WebSocket events to the kateto bridge as POST /api/game/event.
# - Mock mode: simulates events without a Minecraft server (fallback).
# - LLM: freellmapi (fusion model) via OpenAI-compatible API. Optional; only
#   used to enrich simulated events when LLM_MODE=1.

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
from typing import Any

import httpx
import websockets

# ---------------------------------------------------------------------------
# Configuration
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://127.0.0.1:8080")
VOYAGER_WS = os.getenv("VOYAGER_WS", "ws://127.0.0.1:3000/events")
VOYAGER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Voyager")

# freellmapi (fusion) – OpenAI-compatible
FREELLMAPI_BASE_URL = os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")
FREELLMAPI_API_KEY = os.getenv("FREELLMAPI_API_KEY", "freellmapi-your-unified-key")
FREELLMAPI_MODEL = os.getenv("FREELLMAPI_MODEL", "auto")  # router picks; pin to "fusion" if exposed
LLM_MODE = os.getenv("LLM_MODE", "0") == "1"  # opt-in: enrich mock text via LLM

VOICES = ["jane", "doktor", "conquest"]
TASKS = [
    "explora cueva",
    "tala árbol",
    "craftea mesa",
    "busca diamante",
    "chatea con aldeano",
]

# ---------------------------------------------------------------------------
# LLM client (lazy + optional)
def _llm_client():
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        return None
    return OpenAI(base_url=FREELLMAPI_BASE_URL, api_key=FREELLMAPI_API_KEY)


def llm_complete(prompt: str, *, max_tokens: int = 60) -> str | None:
    """Call freellmapi (fusion) for a one-shot completion. Returns None on failure."""
    client = _llm_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=FREELLMAPI_MODEL,
            messages=[
                {"role": "system", "content": "You narrate short Minecraft events in Spanish, one sentence, max 12 words."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[adapter] LLM call failed: {e}", flush=True)
        return None


# ---------------------------------------------------------------------------
# POST helper
async def post_event(
    voice: str,
    text: str,
    *,
    phase: str = "argument",
    rms: float = 0.2,
    event_type: str = "game_event",
    state: Any | None = None,
    role: str = "agent",
) -> None:
    payload = {
        "game": "minecraft",
        "event_type": event_type,
        "voice_id": voice,
        "role": role,
        "text": text,
        "phase": phase,
        "rms": round(rms, 3),
        "state": state or {},
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(f"{BRIDGE_URL}/api/game/event", json=payload)
    except Exception as e:
        print(f"[adapter] failed to POST ({e})", flush=True)


# ---------------------------------------------------------------------------
# Mock loop – synthetic events, optionally enriched by freellmapi
async def mock_loop(steps: int = 6) -> None:
    for i in range(steps):
        voice = random.choice(VOICES)
        task = random.choice(TASKS)
        base_text = f"{voice} {task} (paso {i+1}/{steps})"
        text = base_text
        if LLM_MODE:
            enriched = llm_complete(f"Narrate: {task} from perspective of {voice}")
            if enriched:
                text = f"{voice}: {enriched}"
        await post_event(
            voice,
            text,
            rms=0.2 + random.random() * 0.2,
        )
        await asyncio.sleep(0.5)
    await post_event(
        "conquest",
        "Voyager: misión mock completada.",
        phase="verdict",
        rms=0.3,
        role="system",
    )


# ---------------------------------------------------------------------------
# Real loop – launch Voyager (NodeJS) and bridge its WebSocket
async def run_voyager() -> subprocess.Popen:
    if not os.path.isdir(VOYAGER_DIR):
        raise FileNotFoundError(
            f"Voyager directory not found at {VOYAGER_DIR}. "
            "Clone MineDojo/Voyager or use --mock."
        )
    return subprocess.Popen(
        ["npm", "start"],
        cwd=VOYAGER_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


async def real_loop() -> None:
    try:
        proc = await run_voyager()
    except FileNotFoundError as e:
        print(f"[adapter] {e} – falling back to mock", flush=True)
        await mock_loop()
        return
    except Exception as e:
        print(f"[adapter] Voyager failed to start ({e}) – falling back to mock", flush=True)
        await mock_loop()
        return

    # Give the server a moment to bind the WebSocket port.
    await asyncio.sleep(2)

    # Stream Voyager's stdout/stderr to our own stdout for visibility.
    stdout_task = asyncio.create_task(_pipe_output(proc))

    try:
        async with websockets.connect(VOYAGER_WS) as ws:
            async for message in ws:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    print(f"[adapter] non-JSON message: {message[:120]}", flush=True)
                    continue
                await post_event(
                    voice=data.get("voice", data.get("voice_id", "unknown")),
                    text=data.get("text", ""),
                    phase=data.get("phase", "argument"),
                    rms=float(data.get("rms", 0.2)),
                    event_type=data.get("event_type", "game_event"),
                    state=data.get("state"),
                    role=data.get("role", "agent"),
                )
    except Exception as e:
        print(f"[adapter] WebSocket loop ended ({e}) – falling back to mock", flush=True)
        await mock_loop()
    finally:
        stdout_task.cancel()
        try:
            proc.terminate()
        except Exception:
            pass


async def _pipe_output(proc: subprocess.Popen) -> None:
    if proc.stdout is None:
        return
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, proc.stdout.readline)
        if not line:
            return
        sys.stdout.write(f"[voyager] {line.decode(errors='replace')}")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minecraft Voyager adapter (real or mock)")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (no NodeJS server)")
    parser.add_argument("--steps", type=int, default=6, help="Number of mock steps")
    parser.add_argument("--bridge", default=BRIDGE_URL, help="Bridge HTTP URL")
    parser.add_argument("--ws", default=VOYAGER_WS, help="Voyager WebSocket URL")
    args = parser.parse_args()
    BRIDGE_URL = args.bridge
    VOYAGER_WS = args.ws
    if args.mock:
        asyncio.run(mock_loop(args.steps))
    else:
        asyncio.run(real_loop())