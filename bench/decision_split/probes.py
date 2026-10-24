from __future__ import annotations

import json
import re


def build_small_prompt(obs: dict, legal: list[str]) -> tuple[str, str]:
    system = (
        "Sos el controlador rápido. Respondé ÚNICAMENTE la etiqueta elegida "
        "de la lista de acciones legales, sin explicaciones ni markdown."
    )
    obs_json = json.dumps(obs, separators=(",", ":"))
    actions_str = ",".join(legal)
    user = f"OBS:{obs_json}\nLEGAL:{actions_str}"
    return system, user


def build_grammar(legal: list[str]) -> str:
    if not legal:
        return 'root ::= "wait"'
    escaped_items = []
    for action in sorted(legal):
        esc = action.replace("\\", "\\\\").replace('"', '\\"')
        escaped_items.append(f'"{esc}"')
    return "root ::= " + " | ".join(escaped_items)


def parse_small_label(text: str, legal: list[str]) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    cleaned = cleaned.replace("`", "").strip()
    if cleaned.upper().startswith("ACTION:"):
        cleaned = cleaned[7:].strip()
    cleaned = cleaned.strip("\"'").strip()
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        cleaned = lines[0]
    legal_map = {item.strip().lower(): item for item in legal}
    return legal_map.get(cleaned.lower(), None)


def build_big_prompt(events_window: list[dict], snap: dict) -> tuple[str, str]:
    system = (
        "Sos el modelo principal y estratégico. Reaccionás únicamente a eventos que ya ocurrieron "
        "y al snapshot actual del mundo. No inventes estado ni entidades. "
        "Debés citar en 'refs' los 'event_id' exactos en los que basás tu decisión. "
        "Respondé ÚNICAMENTE un objeto JSON válido con las claves 'say', 'override' y 'refs'."
    )
    events_lines = "\n".join(json.dumps(e, separators=(",", ":")) for e in events_window)
    snap_json = json.dumps(snap, separators=(",", ":"))
    user = (
        f"VENTANA_EVENTOS:\n{events_lines}\n\n"
        f"SNAPSHOT:\n{snap_json}\n\n"
        "Formato requerido:\n"
        '{"say": "<texto>", "override": null | {"verb": "goto|attack|say|interact|stop", "target": "<id>"}, '
        '"refs": ["<event_id>", ...]}'
    )
    return system, user


def parse_big_reaction(text: str) -> dict | None:
    if not text or not isinstance(text, str):
        return None
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    else:
        start = cleaned.find("{")
        if start == -1:
            return None
        cleaned = cleaned[start:]

    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(cleaned)
    except Exception:
        try:
            obj = json.loads(cleaned)
        except Exception:
            return None

    if not isinstance(obj, dict):
        return None

    if "say" not in obj or not isinstance(obj["say"], str):
        return None

    if "override" not in obj:
        return None
    override = obj["override"]
    if override is not None:
        if not isinstance(override, dict):
            return None
        if "verb" not in override or not isinstance(override["verb"], str):
            return None
        if "target" not in override or not isinstance(override["target"], str):
            return None

    if "refs" not in obj or not isinstance(obj["refs"], list):
        return None
    for ref in obj["refs"]:
        if not isinstance(ref, str):
            return None

    return {
        "say": obj["say"],
        "override": obj["override"],
        "refs": obj["refs"],
    }
