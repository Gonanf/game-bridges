# PokeAI – PyBoy + 3 agentes Planning/Execution/Critique via Kateto
# ROM legal: debe existir en ~/ROMs/pokemon_red.gb o game-bridges/pokeai/roms/pokemon_red.gb (dumpeo propio, no pirata)
# Uso: uv run harness.py --bridge http://127.0.0.1:8099 [--mock | --rom ~/ROMs/pokemon_red.gb]
import argparse, asyncio, random, os, httpx, pathlib, json
BRIDGE=os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
LITELLM=os.getenv("LITELLM_URL","http://127.0.0.1:11434/v1")
VOICES={"planning":"jane","execution":"doktor","critique":"conquest"}
ROM_CANDIDATES=[pathlib.Path.home()/ "ROMs/pokemon_red.gb", pathlib.Path("roms/pokemon_red.gb"), pathlib.Path("/run/media/chaos/secundario/ROMs/pokemon_red.gb")]

async def post(role, text, rms=0.2, event_type="game_event", state=None):
    voice=VOICES.get(role, "jane")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={"game":"pokeai","event_type":event_type,"voice_id":voice,"role":role,"text":text,"rms":rms,"state":state or {}})
    except Exception as e:
        print(f"[{role}/{voice}] {text[:50]} ({e})", flush=True)

def find_rom(cli=None):
    if cli and pathlib.Path(cli).exists(): return pathlib.Path(cli)
    for p in ROM_CANDIDATES:
        if p.exists(): return p
    return None

async def mock_loop(steps=6):
    for i in range(steps):
        await post("planning", f"Plan {i+1}: explorar ruta {random.randint(1,10)}, capturar Pokémon.", rms=0.25)
        await asyncio.sleep(0.2)
        await post("execution", f"Ejecuto: presiono {random.choice(['A','B','START'])} mover {random.choice(['arriba','abajo'])}.", rms=0.2)
        await asyncio.sleep(0.2)
        await post("critique", f"Crítica: {random.choice(['bien','reintentar','ajustar ruta'])} tras paso {i+1}.", rms=0.22)
        await asyncio.sleep(0.4)

async def real_loop(rom_path):
    try:
        from pyboy import PyBoy
        print(f"PyBoy ROM {rom_path} iniciando...")
        pyboy = PyBoy(str(rom_path), window="null")
        
        # Notificamos al bridge que empieza sesión real
        await post("planning", "Modo Juego: pokeai – Pokémon Red agent activado.", rms=0.2, event_type="game_start", 
                   state={"game":"pokeai","profile":"pokeai","system_prompt":"Eres un agente Pokémon. 3 voces: Jane (planning), Doktor (execution), Conquest (critique). Herramientas: mempalace_query/mempalace_append/web_search. Objetivo: explorar, capturar, entrenar, ganar el juego."})
        
        step = 0
        max_steps = 50
        while step < max_steps:
            step += 1
            
            # Estado del juego - en real esto vendría de la memoria del ROM
            game_state = {
                "step": step,
                "position": {"map": "Pallet Town", "x": step % 10, "y": (step*3) % 10},
                "party": [{"name": "PIKACHU", "level": 5+step//5, "hp": 20-step%10}],
                "badges": min(step//10, 8),
                "pokedex_count": step,
                "in_battle": step % 5 == 0,
                "inventory": {"pokeball": 10-step//10, "potion": 5}
            }
            
            # 3 agentes postean al bridge en orden: planning -> execution -> critique
            await post("planning", f"Paso {step}: ¿Qué debería hacer en {game_state['position']}?", rms=0.25, 
                       event_type="state_update", state=game_state)
            await asyncio.sleep(0.3)
            
            # Esperamos decisión del bridge (GET)
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(f"{BRIDGE}/api/game/state", params={"game":"pokeai"})
                    if r.status_code == 200:
                        data = r.json()
                        history = data.get("history") or data.get("by_game",{}).get("pokeai",{}).get("history") or []
                        last_action = None
                        for ev in reversed(history[-3:]):
                            st = ev.get("state") or {}
                            last_action = st.get("action") or st.get("command")
                            if last_action:
                                break
                        if last_action:
                            print(f"[bridge action] {last_action}")
                            # simulamos ejecución: presionamos un botón
                            btn = random.choice(["a","b","start","up","down"])
                            pyboy.button_press(btn); pyboy.tick(10, False)
                            await post("execution", f"Ejecuto '{btn}' (bridge: {last_action})", rms=0.2)
            except:
                # fallback sin bridge
                btn = random.choice(["a","b","start"])
                pyboy.button_press(btn); pyboy.tick(10, False)
                await post("execution", f"Ejecuto '{btn}' (sin bridge)", rms=0.2)
            
            await asyncio.sleep(0.3)
            await post("critique", f"Crítica paso {step}: {random.choice(['OK','ajustar','reintentar'])}", rms=0.22)
            await asyncio.sleep(0.5)
        
        pyboy.stop()
        await post("planning", f"PokeAI: sesión real completada ({step} pasos).", rms=0.3, event_type="game_end")
    except Exception as e:
        print(f"PyBoy fail {e}, fallback mock")
        await mock_loop()

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--rom", default=None)
    ap.add_argument("--mock", action="store_true", default=False)
    ap.add_argument("--bridge", default=BRIDGE)
    args=ap.parse_args()
    BRIDGE=args.bridge
    rom=find_rom(args.rom)
    if rom and not args.mock:
        print(f"ROM encontrada {rom}")
        asyncio.run(real_loop(rom))
    else:
        if not rom: print(f"ROM no encontrada, crea {ROM_CANDIDATES[1]} con dumpeo legal. Usando mock.")
        asyncio.run(mock_loop())