# SC2 LLM-PySC2 – text API -> Kateto overlay (mock sin Wine)
# Paper: https://arxiv.org/html/2411.05348v1 LLM-PySC2
# Real requiere SC2 vía Wine + maps + LLM-PySC2
# Uso: uv run harness.py --bridge http://127.0.0.1:8099  (--mock fuerza mock)
import argparse, asyncio, random, os, httpx
BRIDGE=os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
MACRO=["expande base","construye barraca","investiga stim","reúne minerales"]
MICRO=["micro marines","kitea zealots","flanquea","retirada"]
async def post(voice, text, rms=0.2, phase="argument", event_type="game_event", state=None):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={"game":"sc2","event_type":event_type,"voice_id":voice,"text":text,"rms":rms,"phase":phase,"state":state or {}})
    except Exception as e:
        print(f"[{voice}] {text[:50]} ({e})", flush=True)
async def mock_loop(steps=6):
    for i in range(steps):
        base_voice=random.choice(["jane","doktor"])
        await post(base_voice, f"Macro: {random.choice(MACRO)} (min {i})", rms=0.25)
        await asyncio.sleep(0.3)
        await post("conquest", f"Micro: {random.choice(MICRO)}", rms=0.2)
        await asyncio.sleep(0.4)
    await post("conquest","SC2 mock partida terminada.", phase="verdict", rms=0.3)
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", default=False)
    ap.add_argument("--bridge", default=BRIDGE)
    args=ap.parse_args()
    BRIDGE=args.bridge
    asyncio.run(mock_loop())
