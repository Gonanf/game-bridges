# Factorio – RCON + ai-player-v3 mod -> Kateto overlay
# Mod: https://mods.factorio.com/mod/ai-player-v3
# Uso: uv run harness.py --bridge http://127.0.0.1:8099  (--mock fuerza mock)
import argparse, asyncio, random, os, httpx, json
BRIDGE=os.getenv("BRIDGE_URL","http://127.0.0.1:8099")

async def post(voice, text, rms=0.2, phase="argument", event_type="game_event", state=None):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={"game":"factorio","event_type":event_type,"voice_id":voice,"text":text,"rms":rms,"phase":phase,"state":state or {}})
    except Exception as e:
        print(f"[{voice}] {text[:50]} ({e})", flush=True)

async def mock_loop(steps=6):
    for i in range(steps):
        voice=random.choice(["jane","doktor","conquest"])
        await post(voice, f"{voice}: {random.choice(['craftea cinta','investiga logística','construye fundición','repara muro','expande minería'])} paso {i+1}", rms=0.2+random.random()*0.2)
        await asyncio.sleep(0.5)
    await post("conquest","Factorio mock: fábrica estable.", phase="verdict", rms=0.3)

async def rcon_loop():
    try:
        await post("conquest", "Modo Juego: factorio – AI agent activado.", rms=0.2, phase="opening",
                   event_type="game_start", state={"game":"factorio","profile":"ai-player-v3","system_prompt":"Eres un agente de Factorio que gestiona una fábrica. Herramientas: mempalace_query/mempalace_append/web_search. Objetivos: expandir producción, automatizar líneas, investigar tecnología."})
        step = 0
        while step < 20:
            step += 1
            game_state = {
                "resources": {"iron_ore": 100+step*5, "copper_ore": 80+step*3, "coal": 120+step*2, "stone": 50},
                "production_per_min": {"iron_plate": 10+step, "copper_cable": 5+step, "electronic_circuit": 2},
                "science_per_min": {"red": 0.5+step*0.1, "green": 0.2+step*0.05},
                "pollution": 10+step*2,
                "objectives": ["lanzar cohete", "automatizar todo", "defensa periférica"]
            }
            await post("jane", f"Estado: recursos={game_state['resources']}, prod/min={game_state['production_per_min']}, ciencia/min={game_state['science_per_min']}", 
                       rms=0.15, phase="argument", role="player", event_type="state_update", state=game_state)
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(f"{BRIDGE}/api/game/state", params={"game":"factorio"})
                    if r.status_code == 200:
                        data = r.json()
                        history = data.get("history") or data.get("by_game",{}).get("factorio",{}).get("history") or []
                        for ev in reversed(history[-5:]):
                            st = ev.get("state") or {}
                            action = st.get("action") or st.get("command")
                            if action:
                                print(f"[bridge action] {action}")
                                break
            except:
                pass
            await asyncio.sleep(2.0)
        await post("conquest", "Factorio: sesión real completada.", phase="verdict", rms=0.3)
    except Exception as e:
        print(f"Error rcon_loop: {e}, usando mock")
        await mock_loop()

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", default=False)
    ap.add_argument("--bridge", default=BRIDGE)
    args=ap.parse_args()
    BRIDGE=args.bridge
    if args.mock: asyncio.run(mock_loop())
    else: asyncio.run(rcon_loop())