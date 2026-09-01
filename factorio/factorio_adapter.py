"""Factorio Adapter

Este adaptador usa `factorio-rcon-py` para enviar comandos al servidor Factorio via RCON y publica eventos a Kateto.

Modo mock (sin RCON):
    python factorio_adapter.py --mock

Modo real (requiere RCON_HOST, RCON_PORT, RCON_PASSWORD):
    python factorio_adapter.py

Variables de entorno:
    BRIDGE_URL      - URL del endpoint Kateto (default http://127.0.0.1:8080)
    FREELLMAPI_URL  - URL del LLM (default http://127.0.0.1:4000/v1)
    RCON_HOST, RCON_PORT, RCON_PASSWORD - credenciales del server Factorio.
"""
import os, argparse, asyncio, random, httpx

BRIDGE = os.getenv("BRIDGE_URL", "http://127.0.0.1:8080")
LLM_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:4000/v1")

TASKS = ["craftea cinta", "investiga logística", "construye fundición", "repara muro", "expande minería"]

async def post_event(event_type, voice, text, rms=0.15, state=None):
    payload = {
        "game": "factorio",
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
    voices = ["jane", "doktor", "conquest"]
    for i in range(steps):
        voice = random.choice(voices)
        task = random.choice(TASKS)
        await post_event(event_type="task", voice=voice, text=f"{voice} ejecuta: {task}", rms=0.2)
        await asyncio.sleep(0.4)

async def real_loop():
    try:
        from factorio_rcon import RCONClient
        host = os.getenv("RCON_HOST", "127.0.0.1")
        port = int(os.getenv("RCON_PORT", "27015"))
        password = os.getenv("RCON_PASSWORD")
        async with RCONClient(host, port, password) as rcon:
            for i, task in enumerate(TASKS):
                # Simple example: send a free-form command
                await rcon.send(task)
                await post_event(event_type="task", voice="jane", text=f"RCON ejecuta: {task}", rms=0.2, state={"task_index": i})
                await asyncio.sleep(0.5)
    except Exception as e:
        print(f"RCON no disponible ({e}), usando mock.")
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
