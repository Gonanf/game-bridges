# Chess – Jane vs Doktor via Kateto Event Bus (GameMode SPEC §1)
import argparse, asyncio, random, httpx, chess, chess.pgn, chess.svg, io, os, pathlib, uuid, time, json
BRIDGE = os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
VOICES = {"white":"jane","black":"doktor","judge":"conquest"}
BUS_TIMEOUT = float(os.getenv("BUS_TIMEOUT","10"))
BUS_POLL = float(os.getenv("BUS_POLL_INTERVAL","0.8"))

async def post(game, voice, text, rms=0.15, phase=None, role=None, event_type="game_event", state=None):
    payload={"game":game,"event_type":event_type,"voice_id":voice,"text":text,"rms":rms,"phase":phase,"role":role,"state":state or {}}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r=await c.post(f"{BRIDGE}/api/game/event", json=payload)
            return r.json() if r.content else {}
    except Exception as e:
        print(f"[bridge fail] {e} bridge={BRIDGE}",flush=True)
        return {"status":"mock","payload":payload}

def render_board(board: chess.Board, last_move: chess.Move | None = None):
    print(board.unicode(borders=True), flush=True)
    print(f"FEN: {board.fen()}", flush=True)
    try:
        svg = chess.svg.board(board, lastmove=last_move, size=500)
        pathlib.Path("board.svg").write_text(svg)
        html = f"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=1>
<title>Chess</title><style>body{{margin:0;background:#1a1a2e;display:flex;justify-content:center;align-items:center;height:100vh}}svg{{max-width:90vmin;max-height:90vmin;box-shadow:0 0 20px #000}}</style>
{svg}<div style="position:fixed;bottom:8px;left:50%;transform:translateX(-50%);color:#fff;font:14px monospace;background:#0008;padding:4px 8px;border-radius:4px">FEN: {board.fen()}</div>"""
        pathlib.Path("board.html").write_text(html)
        print(f"[board] board.svg + board.html (OBS: file://{pathlib.Path('board.html').resolve()})", flush=True)
    except Exception as e:
        print(f"[board svg fail] {e}", flush=True)

async def request_move_via_bus(board: chess.Board, voice: str, mock: bool) -> str:
    if mock:
        return random.choice(list(board.legal_moves)).uci()
    req_id = uuid.uuid4().hex[:8]
    legal = [m.uci() for m in board.legal_moves]
    color = "blancas" if board.turn == chess.WHITE else "negras"
    opponent = VOICES["black"] if voice == VOICES["white"] else VOICES["white"]
    history = " ".join([m.uci() for m in board.move_stack][-8:])
    await post("chess", voice, f"{voice} ({color} vs {opponent}) solicita jugada FEN {board.fen()}", rms=0.12, phase="awaiting_move", role="player",
               event_type="move_request", state={"fen":board.fen(),"legal_moves":legal,"request_id":req_id,"ply":len(list(board.move_stack)), "color":color, "opponent":opponent, "history":history, "side": "white" if board.turn==chess.WHITE else "black"})
    # Listen to Kateto overlay WS where voices' TextChunk/ToolCall are auto-broadcast
    # (no polling UI). If WS unavailable, fallback to polling is not needed – voices auto-register.
    ws_url = BRIDGE.replace("http://","ws://").replace("https://","wss://").rstrip("/") + "/ws/overlay"
    deadline = time.monotonic() + BUS_TIMEOUT
    try:
        import websockets
        async with websockets.connect(ws_url, open_timeout=4) as ws:
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=BUS_POLL)
                    data = json.loads(raw) if isinstance(raw, str) else {}
                    # overlay broadcasts either raw game event or wrapped {event,...}
                    cand = data.get("state") or data.get("data",{}).get("state") or {}
                    uci = cand.get("uci") or data.get("uci")
                    rid = cand.get("request_id") or data.get("request_id")
                    vid = data.get("voice_id") or data.get("data",{}).get("voice_id")
                    # also capture TextChunk that looks like UCI (voices speak move)
                    if not uci:
                        txt = (data.get("text") or data.get("data",{}).get("text") or "").strip().split()
                        if txt:
                            t0 = txt[0].lower().strip(".,;:")
                            if len(t0)==4 and t0[0] in "abcdefgh" and t0[1] in "12345678":
                                uci = t0
                                rid = req_id
                    if uci:
                        uci = str(uci).lower().strip()
                        if rid == req_id or (vid == voice and len(uci)==4):
                            try:
                                if chess.Move.from_uci(uci) in board.legal_moves:
                                    print(f"[bus ws] {voice} -> {uci} (req {req_id})", flush=True)
                                    return uci
                            except: pass
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"[ws recv fail] {e}", flush=True)
                    break
    except Exception as e:
        print(f"[ws connect fail {ws_url}] {e} -> fallback", flush=True)
    # Fallback: direct poll only if WS missed (keeps offline support)
    # ponytail: keep minimal – one GET try, no loop
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{BRIDGE}/api/game/state", params={"game":"chess"})
            if r.status_code == 200:
                hist = r.json().get("history") or r.json().get("by_game",{}).get("chess",{}).get("history") or []
                for ev in reversed(hist):
                    st = ev.get("state") or {}
                    if st.get("request_id")==req_id and st.get("uci"):
                        uci = str(st["uci"]).lower()
                        if chess.Move.from_uci(uci) in board.legal_moves:
                            print(f"[bus poll] {voice} -> {uci}", flush=True)
                            return uci
    except: pass
    print(f"[bus timeout {BUS_TIMEOUT}s req {req_id}] -> random", flush=True)
    return random.choice(list(board.legal_moves)).uci()

async def play_one(mock=False):
    board=chess.Board()
    game=chess.pgn.Game()
    node=game
    turn=0
    await post("chess", "conquest", "Modo Juego: chess – Jane vs Doktor. Activando Game Profile.", rms=0.2, phase="opening", role="judge",
               event_type="game_start", state={"game":"chess","profile":"chess","system_prompt":"Estás jugando a ajedrez como Jane/Doktor. Herramientas: mempalace_query/mempalace_append/web_search. Jugá solo UCI legal.","tools":["mempalace_query","mempalace_append","web_search"],"voices":VOICES, "fen":board.fen()})
    render_board(board)
    while not board.is_game_over() and turn<80:
        voice = VOICES["white"] if board.turn==chess.WHITE else VOICES["black"]
        uci = await request_move_via_bus(board, voice, mock)
        try: move = chess.Move.from_uci(uci)
        except: move = random.choice(list(board.legal_moves)); uci=move.uci()
        if move not in board.legal_moves:
            print(f"[reject] {uci} illegal, game_action_rejected", flush=True)
            await post("chess", voice, f"Movimiento rechazado {uci}", rms=0.3, phase="error", role="player", event_type="game_action_rejected", state={"fen":board.fen(),"rejected":uci,"reason":"illegal"})
            move = random.choice(list(board.legal_moves)); uci=move.uci()
        san = board.san(move)
        board.push(move)
        render_board(board, last_move=move)
        await post("chess", voice, f"{voice} juega {san} ({uci})", rms=0.2+random.random()*0.3, phase="argument", role="player", state={"fen":board.fen(),"uci":uci,"san":san,"ply":turn+1})
        if turn%4==3:
            await post("chess","conquest", f"Conquest: {random.choice(['Excelente apertura','Tensión en el centro','Final interesante'])} tras {san}", rms=0.25, phase="ruling", role="judge", state={"fen":board.fen()})
        node=node.add_variation(move)
        turn+=1
        await asyncio.sleep(0.5)
    result=board.result()
    exporter=io.StringIO(); print(game, file=exporter); pgn=exporter.getvalue()
    await post("chess","conquest", f"PGN guardado", rms=0.1, event_type="pgn_save", state={"pgn":pgn,"fen":board.fen(),"result":result})
    pathlib.Path("last.pgn").write_text(pgn)
    print(f"PGN guardado last.pgn resultado {result}")
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", default=False, help="no usa bus, random directo")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--bridge", default=BRIDGE)
    args=ap.parse_args()
    BRIDGE=args.bridge
    for i in range(args.rounds):
        print(f"=== partida {i+1}/{args.rounds} mock={args.mock} bridge={BRIDGE} ===")
        asyncio.run(play_one(mock=args.mock))
