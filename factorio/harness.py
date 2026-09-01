# Factorio – RCON + ai-player-v3 mod -> Kateto overlay
# Mod: https://mods.factorio.com/mod/ai-player-v3
# Uso: uv run harness.py --bridge http://127.0.0.1:8099  (--mock fuerza mock)
import argparse, asyncio, random, os, httpx
BRIDGE=os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
TASKS=["craftea cinta","investiga logística","construye fundición","repara muro","expande minería"]
async def post(voice, text, rms=0.2, phase="argument", event_type="game_event", state=None):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={"game":"factorio","event_type":event_type,"voice_id":voice,"text":text,"rms":rms,"phase":phase,"state":state or {}})
    except Exception as e:
        print(f"[{voice}] {text[:50]} ({e})", flush=True)
async def mock_loop(steps=6):
    for i in range(steps):
        voice=random.choice(["jane","doktor","conquest"])
        await post(voice, f"{voice}: {random.choice(TASKS)} paso {i+1}", rms=0.2+random.random()*0.2)
        await asyncio.sleep(0.5)
    await post("conquest","Factorio mock: fábrica estable.", phase="verdict", rms=0.3)
async def rcon_loop():
    try:
        from factorio_rcon import RCONClient
        host=os.getenv("RCON_HOST","127.0.0.1"); port=int(os.getenv("RCON_PORT","27015"))
        print(f"RCON {host}:{port} intentando...")
        await mock_loop()
    except Exception as e:
        print(f"RCON no disponible {e}")
        await mock_loop()
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", default=False)
    ap.add_argument("--bridge", default=BRIDGE)
    args=ap.parse_args()
    BRIDGE=args.bridge
    if args.mock: asyncio.run(mock_loop())
    else: asyncio.run(rcon_loop())
