# Werewolf Arena – 7 agentes Kateto via courtroom overlay
# Uso: uv run harness.py --bridge http://127.0.0.1:8099  (--mock fuerza mock)
import argparse, asyncio, random, os, httpx
BRIDGE=os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
ROLES=["werewolf","werewolf","seer","villager","villager","villager","villager"]
VOICES=["jane","doktor","conquest","whisperer","jane","doktor","conquest"]
NAMES=["Jane","Doktor","Conquest","Whisper","Jane2","Doktor2","Conquest2"]

async def post(voice, text, phase="argument", rms=0.2, role=None, event_type="game_event", state=None):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={
                "game":"werewolf","event_type":event_type,"voice_id":voice,"text":text,"phase":phase,"role":role,"rms":rms,"state":state or {}})
    except Exception as e:
        print(f"[bridge {voice}] {text[:60]} ({e})", flush=True)

async def get_state():
    # Leemos el historial del bridge para que los agentes tengan contexto de otros agentes
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BRIDGE}/api/game/state", params={"game":"werewolf"})
            if r.status_code == 200:
                return r.json()
    except:
        pass
    return {}

async def round_day(players, alive):
    state = await get_state()
    history = state.get("history") or state.get("by_game",{}).get("werewolf",{}).get("history") or []
    last_speeches = [ev for ev in history[-10:] if ev.get("event_type") == "speech"]
    
    for idx in [i for i,p in enumerate(players) if p["alive"]]:
        v=players[idx]
        # El agente puede ver los últimos speeches de otros
        context = "; ".join([ev.get("text","")[:50] for ev in last_speeches[-3:]])
        lines = random.choice([f"Soy {v['name']} ({v['role']}), sospecho de {random.choice(NAMES)} porque dudó.",f"Como {v['role']}, vi que {random.choice(NAMES)} actuó raro anoche.",f"Propongo votar a {random.choice(NAMES)}, su argumento no cierra."])
        await post(v["voice"], lines, phase="argument", role=v["role"], event_type="speech", state={"alive":[p["name"] for p in players if p["alive"]], "context": context[:200]})
        await asyncio.sleep(0.2)
        if random.random()<0.1:
            candidates=[i for i,p in enumerate(players) if p["alive"] and p["voice"]!=v["voice"]]
            if candidates:
                obj_idx=random.choice(candidates); obj=players[obj_idx]
                await post(obj["voice"], f"¡Objeción! {v['name']} miente, yo soy {obj['role']}", phase="objection", role="adversary", rms=0.4, event_type="objection", state={"target":obj["name"],"accused":v["name"]})
                await asyncio.sleep(0.2)
                await post(v["voice"], "Rechazo la objeción, mis pruebas son sólidas.", phase="rebuttal", rms=0.3, event_type="rebuttal", state={"rebutted":obj["name"]})
    votes={}
    for idx in [i for i,p in enumerate(players) if p["alive"]]:
        target_idx=random.choice([i for i in range(len(players)) if players[i]["alive"] and i!=idx])
        votes[target_idx]=votes.get(target_idx,0)+1
    eliminated=max(votes, key=votes.get)
    players[eliminated]["alive"]=False
    await post("conquest", f"Juez: eliminado {players[eliminated]['name']} ({players[eliminated]['role']}) con {votes[eliminated]} votos.", phase="ruling", rms=0.3)
    return eliminated

async def game(mock=False):
    players=[{"name":NAMES[i],"voice":VOICES[i],"role":ROLES[i],"alive":True} for i in range(7)]
    await post("conquest","Modo Juego: werewolf – 7 jugadores. 2 lobos, 1 vidente.", rms=0.2, phase="opening",
               event_type="game_start", state={"game":"werewolf","profile":"werewolf-arena","system_prompt":"Eres un agente de Werewolf con courtroom. 7 voces: Jane, Doktor, Conquest, Whisper. Mecánica: debate diario, voto, eliminación, lobos matan de noche. Herramientas: mempalace_query/mempalace_append/web_search."})
    await asyncio.sleep(0.3)
    were=[i for i,p in enumerate(players) if p["role"]=="werewolf"]
    victim=random.choice([i for i,p in enumerate(players) if p["alive"] and p["role"]!="werewolf"])
    players[victim]["alive"]=False
    await post(players[were[0]]["voice"], f"(noche) Lobos eliminan a {players[victim]['name']}", phase="argument", role="werewolf", rms=0.15)
    await asyncio.sleep(0.3)
    for day in range(3):
        if sum(1 for p in players if p["alive"] and p["role"]=="werewolf")==0:
            await post("conquest","¡Aldeanos ganan! No quedan lobos.", phase="verdict", rms=0.35); break
        if sum(1 for p in players if p["alive"] and p["role"]!="werewolf")<=2:
            await post("conquest","¡Lobos ganan! Quedan pocos aldeanos.", phase="verdict", rms=0.35); break
        await post("conquest", f"--- Día {day+1} ---", phase="argument")
        await round_day(players, [p for p in players if p["alive"]])
        await asyncio.sleep(0.4)
    await post("conquest", f"Historial: {[p['name']+':'+p['role']+('†' if not p['alive'] else '') for p in players]}", phase="verdict")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", default=False)
    ap.add_argument("--bridge", default=BRIDGE)
    args=ap.parse_args()
    BRIDGE=args.bridge
    asyncio.run(game(mock=args.mock))