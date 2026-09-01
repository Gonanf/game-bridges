"""PokéAI Adapter

Este módulo inicia PyBoy (emulador de Game Boy) y traduce frames y estados a Kateto mediante `POST /api/game/event`.

Uso mock (cuando no hay ROM):
    python pokeai_adapter.py --mock

Uso real (requiere ROM legal en `~/ROMs/pokemon_red.gb` o en `./roms/`):
    python pokeai_adapter.py

Variables de entorno:
    BRIDGE_URL     – URL del endpoint Kateto (default http://127.0.0.1:8080)
    FREELLMAPI_URL – URL del LLM (default http://127.0.0.1:4000/v1)
"""
import os, argparse, asyncio, random, httpx, pathlib

BRIDGE = os.getenv("BRIDGE_URL", "http://127.0.0.1:8080")
LLM_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:4000/v1")

VOICES = {"planning":"jane","execution":"doktor","critique":"conquest"}

ROM_CANDIDATES = [
    pathlib.Path.home() / "ROMs" / "pokemon_red.gb",
    pathlib.Path("roms/pokemon_red.gb"),
    pathlib.Path("/run/media/chaos/secundario/ROMs/pokemon_red.gb"),
]

def find_rom():
    for p in ROM_CANDIDATES:
        if p.exists():
            return p
    return None

async def post_event(event_type, role, text, rms=0.15, state=None):
    voice = VOICES.get(role, "jane")
    payload = {
        "game": "pokeai",
        "event_type": event_type,
        "voice_id": voice,
        "role": role,
        "text": text,
        "rms": rms,
        "state": state or {},
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(f"{BRIDGE}/api/game/event", json=payload)
    except Exception as e:
        print(f"[bridge error] {e}")

async def mock_loop(steps=6):
    for i in range(steps):
        await post_event(event_type="vision", role="planning", text=f"Planning step {i+1}: explorar zona", rms=0.2)
        await post_event(event_type="action", role="execution", text=f"Execution step {i+1}: pulsar A", rms=0.2)
        await post_event(event_type="critique", role="critique", text=f"Critique step {i+1}: evaluar resultado", rms=0.2)
        await asyncio.sleep(0.4)

async def real_loop(rom_path):
    # Minimal demo: no full vision pipeline, just feed placeholder frames.
    from pyboy import PyBoy
    pyboy = PyBoy(str(rom_path), window="null")
    for i in range(5):
        # In a real implementation we would screenshot and OCR, here we send a dummy state.
        await post_event(event_type="vision", role="planning", text=f"Frame {i} capturado", rms=0.2, state={"frame": i})
        await asyncio.sleep(0.5)
    pyboy.stop()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Ejecutar en modo mock")
    args = parser.parse_args()
    if args.mock:
        await mock_loop()
    else:
        rom = find_rom()
        if rom:
            await real_loop(rom)
        else:
            print("ROM no encontrada, ejecutando mock.")
            await mock_loop()

if __name__ == "__main__":
    asyncio.run(main())
