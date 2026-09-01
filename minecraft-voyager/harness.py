# Minecraft Voyager – harness stub + adaptador Kateto overlay
# Uso: uv run harness.py --bridge http://127.0.0.1:8099  (--mock fuerza mock)
import argparse, asyncio, random, os, httpx
BRIDGE=os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
VOICES=["jane","doktor","conquest"]
TASKS=["explora cueva","tala árbol","craftea mesa","busca diamante","chatea con aldeano"]
async def post(voice, text, phase="argument", rms=0.2, event_type="game_event", state=None):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={"game":"minecraft","event_type":event_type,"voice_id":voice,"text":text,"phase":phase,"rms":rms,"state":state or {}})
    except Exception as e:
        print(f"[{voice}] {text[:50]} ({e})", flush=True)
async def mock_loop(steps=6):
    for i in range(steps):
        voice=random.choice(VOICES)
        task=random.choice(TASKS)
        await post(voice, f"{voice} {task} (paso {i+1}/{steps})", rms=0.2+random.random()*0.2)
        await asyncio.sleep(0.5)
    await post("conquest", "Voyager: misión mock completada.", phase="verdict", rms=0.3)
async def real_loop():
    try:
        import sys
        sys.path.insert(0, "Voyager")
        from voyager import Voyager
        print("Voyager importado, iniciando agente real...")
        await mock_loop()
    except Exception as e:
        print(f"Voyager no disponible ({e}), usando mock")
        await mock_loop()
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", default=False)
    ap.add_argument("--bridge", default=BRIDGE)
    ap.add_argument("--steps", type=int, default=6)
    args=ap.parse_args()
    BRIDGE=args.bridge
    if args.mock: asyncio.run(mock_loop(args.steps))
    else: asyncio.run(real_loop())
