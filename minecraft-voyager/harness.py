# Minecraft Voyager – harness stub + adaptador Kateto overlay
# Uso: uv run harness.py --bridge http://127.0.0.1:8099  (--mock fuerza mock)
import argparse, asyncio, random, os, httpx, json
BRIDGE=os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
VOICES=["jane","doktor","conquest"]

async def post(voice, text, phase="argument", rms=0.2, event_type="game_event", state=None):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={"game":"minecraft","event_type":event_type,"voice_id":voice,"text":text,"phase":phase,"rms":rms,"state":state or {}})
    except Exception as e:
        print(f"[{voice}] {text[:50]} ({e})", flush=True)

async def mock_loop(steps=6):
    for i in range(steps):
        voice=random.choice(VOICES)
        task=random.choice(["explora cueva","tala árbol","craftea mesa","busca diamante","chatea con aldeano"])
        await post(voice, f"{voice} {task} (paso {i+1}/{steps})", rms=0.2+random.random()*0.2)
        await asyncio.sleep(0.5)
    await post("conquest", "Voyager: misión mock completada.", phase="verdict", rms=0.3)

async def real_loop():
    # Con el bridge de Kateto como cerebro, solo enviamos estado y leemos decisiones
    # El bridge ya maneja la IA - nosotros solo postamos game_event y leemos respuesta
    try:
        # inicializamos notificando al bridge que empieza una sesión real
        await post("conquest", "Modo Juego: minecraft – Voyager agent activado.", rms=0.2, phase="opening", role="judge",
                   event_type="game_start", state={"game":"minecraft","profile":"voyager","system_prompt":"Eres un agente Voyager en Minecraft. Herramientas: mempalace_query/mempalace_append/web_search. Objetivos: explorar, minar, craftear, sobrevivir."})
        
        step = 0
        while step < 20:  # max steps
            step += 1
            # Estado del juego - en real esto vendría de Mineflayer/bot.js
            # Por ahora simulamos el estado que el bridge usaría para decidir
            game_state = {
                "position": {"x": 100+step*5, "y": 64, "z": 200+step*3},
                "inventory": {"dirt": 10, "wood": 5, "stone": 3, "iron": 0},
                "health": 20,
                "food": 18,
                "nearby_entities": ["cow", "sheep"] if step % 3 == 0 else [],
                "time_of_day": "day" if step < 10 else "night",
                "objectives": ["explore cave", "find diamonds", "build shelter"]
            }
            
            # Pedimos decisión al bridge (la IA del bridge decide qué acción tomar)
            await post("jane", f"Estado: pos={game_state['position']}, inv={game_state['inventory']}, objetivos={game_state['objectives']}", 
                       rms=0.15, phase="argument", role="player", event_type="state_update", state=game_state)
            
            # Polling simple para obtener respuesta del bridge
            # En producción esto sería WS, pero mantenemos simple con GET
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(f"{BRIDGE}/api/game/state", params={"game":"minecraft"})
                    if r.status_code == 200:
                        data = r.json()
                        history = data.get("history") or data.get("by_game",{}).get("minecraft",{}).get("history") or []
                        for ev in reversed(history[-5:]):
                            st = ev.get("state") or {}
                            action = st.get("action") or st.get("command")
                            if action:
                                print(f"[bridge action] {action}")
                                break
            except:
                pass
            
            await asyncio.sleep(1.0)
            
        await post("conquest", "Voyager: sesión real completada.", phase="verdict", rms=0.3)
    except Exception as e:
        print(f"Error real_loop: {e}, usando mock")
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