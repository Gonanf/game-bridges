# Chess – Jane vs Doktor via Kateto
`pip install python-chess httpx`
`python harness.py --mock --rounds 1 --bridge http://127.0.0.1:8080`
Cada jugada POST a /api/game/event {game:chess,voice_id,phase,text,rms} -> overlay.
Mock sin LLM, con Kateto: `LITELLM_URL=http://127.0.0.1:11434/v1` model Kateto.
PGN en last.pgn, UI web mínima pendiente (board + ws overlay).
