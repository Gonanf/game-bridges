# Minecraft Voyager

Real: `git clone https://github.com/MineDojo/Voyager && pip install -r Voyager/requirements.txt` (Mineflayer)

Mock: `python harness.py --mock --steps 6`

Traduce explore/craft/chat -> POST `/api/game/event` (jane/doktor/conquest).

Test Kateto: `LITELLM_URL=http://127.0.0.1:11434/v1`

## Adapter

`minecraft_adapter.py` arranca el servidor local de Voyager (NodeJS), abre un
bridge WebSocket/HTTP y traduce cada evento a un `POST /api/game/event` con
los campos:

- `game = "minecraft"`
- `event_type`
- `voice_id` (`jane` / `doktor` / `conquest`)
- `role`
- `phase`
- `text`
- `rms`
- `state`

Modo mock (sin servidor NodeJS):

```
python minecraft_adapter.py --mock --steps 6
```

Modo real (lanza `npm start` dentro de `./Voyager` y reenvía su WebSocket):

```
python minecraft_adapter.py
```

Variables de entorno:

- `BRIDGE_URL` (default `http://127.0.0.1:8080`): endpoint del bridge
  `/api/game/event`.
- `FREELLMAPI_URL` (default `http://127.0.0.1:4000/v1`): URL del LLM que usa el adaptador (FreelLMAPI fusion).
- `VOYAGER_DIR` implícito en `<repo>/Voyager`.

Si Voyager no está disponible, el adaptador cae automáticamente al modo mock.
