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

async def real_loop():
    try:
        await post("conquest", "Modo Juego: sc2 – SC2 agent activado.", rms=0.2, phase="opening",
                   event_type="game_start", state={"game":"sc2","profile":"llm-pysc2","system_prompt":"Eres un agente de StarCraft 2. Terran. Herramientas: mempalace_query/mempalace_append/web_search. Objetivo: gestionar macro y micro."})
        step = 0
        while step < 30:
            step += 1
            game_state = {
                "minerals": 50+step*10,
                "gas": 30+step*5,
                "supply": {"used": 10+step//2, "cap": 200},
                "army": {"marines": 5+step//3, "tanks": step//10, "medivacs": step//15},
                "enemy_scouted": step > 5,
                "enemy_units": {"zealots": step//4, "stalkers": step//6} if step > 10 else {}
            }
            await post("jane", f"Mini {step}: {game_state['minerals']}m {game_state['gas']}g, supply {game_state['supply']['used']}/{game_state['supply']['cap']}", 
                       rms=0.15, phase="argument", event_type="state_update", state=game_state)
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(f"{BRIDGE}/api/game/state", params={"game":"sc2"})
                    if r.status_code == 200:
                        data = r.json()
                        history = data.get("history") or data.get("by_game",{}).get("sc2",{}).get("history") or []
                        for ev in reversed(history[-3:]):
                            st = ev.get("state") or {}
                            action = st.get("action") or st.get("command")
                            if action:
                                print(f"[bridge action] {action}")
                                break
            except:
                pass
            await asyncio.sleep(1.5)
        await post("conquest", "SC2: sesión real completada.", phase="verdict", rms=0.3)
    except Exception as e:
        print(f"Error real_loop: {e}, usando mock")
        await mock_loop()

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", default=False)
    ap.add_argument("--bridge", default=BRIDGE)
    args=ap.parse_args()
    BRIDGE=args.bridge
    if args.mock: asyncio.run(mock_loop())
    else: asyncio.run(real_loop())