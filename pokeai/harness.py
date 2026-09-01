# PokeAI – PyBoy + 3 agentes Planning/Execution/Critique via Kateto
# ROM legal: debe existir en ~/ROMs/pokemon_red.gb o game-bridges/pokeai/roms/pokemon_red.gb (dumpeo propio, no pirata)
# Uso: uv run harness.py --bridge http://127.0.0.1:8099 [--mock | --rom ~/ROMs/pokemon_red.gb]
import argparse, asyncio, random, os, httpx, pathlib
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
        for i in range(5):
            await post("planning", f"Veo pantalla {i}, decido mover.", rms=0.25)
            pyboy.button_press("a"); pyboy.tick(10, False)
            await asyncio.sleep(0.5)
        pyboy.stop()
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
