"""SC2 Adapter

Este adaptador arranca StarCraft II bajo Wine y usa la API LLM‑PySC2 para obtener órdenes macro y micro, enviándolas a Kateto mediante `POST /api/game/event`.

Modo mock (sin SC2):
    python sc2_adapter.py --mock

Modo real (requiere instalación de SC2 bajo Wine y el paquete `llm‑pysc2`):
    python sc2_adapter.py

Variables de entorno:
    BRIDGE_URL      - URL del endpoint Kateto (default http://127.0.0.1:8080)
    FREELLMAPI_URL  - URL del LLM (default http://127.0.0.1:4000/v1)
"""
import os, argparse, asyncio, random, httpx

BRIDGE = os.getenv("BRIDGE_URL", "http://127.0.0.1:8080")
LLM_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:4000/v1")

MACRO = ["expande base", "construye barraca", "investiga stim", "reúna minerales"]
MICRO = ["micro marines", "kitea zealots", "flanquea", "retirada"]

async def post_event(event_type, voice, text, rms=0.15, state=None):
    payload = {
        "game": "sc2",
        "event_type": event_type,
        "voice_id": voice,
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
    voices = ["jane", "doktor"]
    for i in range(steps):
        voice = random.choice(voices)
        macro = random.choice(MACRO)
        micro = random.choice(MICRO)
        await post_event(event_type="macro", voice=voice, text=f"{voice} macro: {macro}")
        await asyncio.sleep(0.3)
        await post_event(event_type="micro", voice=voice, text=f"{voice} micro: {micro}")
        await asyncio.sleep(0.3)

async def real_loop():
    try:
        # Placeholder: en la realidad cargarías la librería llm‑pysc2 y pasarías el estado del juego.
        # Aquí simulamos con textos.
        for i in range(5):
            await post_event(event_type="macro", voice="jane", text=f"Macro iteración {i}", rms=0.2)
            await asyncio.sleep(0.4)
            await post_event(event_type="micro", voice="doktor", text=f"Micro acción {i}", rms=0.2)
            await asyncio.sleep(0.4)
    except Exception as e:
        print(f"SC2 error ({e}), fallback a mock.")
        await mock_loop()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Ejecutar en modo mock")
    args = parser.parse_args()
    if args.mock:
        await mock_loop()
    else:
        await real_loop()

if __name__ == "__main__":
    asyncio.run(main())
