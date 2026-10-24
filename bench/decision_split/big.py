from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from probes import build_big_prompt, parse_big_reaction


def judge_hallucination(
    reaction: dict | None,
    events_window: list[dict],
    snap: dict,
) -> dict:
    if reaction is None or reaction.get("unparseable") is True:
        return {"hallucinated": False, "reasons": ["unparseable"]}

    reasons: list[str] = []
    window_eids = {e.get("event_id") for e in events_window if "event_id" in e}
    entities_map = snap.get("entities", {})

    # H1 ref-fantasma: algún event_id de refs no está en events_window
    for ref in reaction.get("refs", []):
        if ref not in window_eids:
            reasons.append(f"H1: ref-fantasma ({ref})")

    # H2 target-fantasma: override.target no existe en snap["entities"]
    override = reaction.get("override")
    if override and isinstance(override, dict):
        target = override.get("target")
        if target and target not in entities_map:
            reasons.append(f"H2: target-fantasma ({target})")

    # H3 entity-fantasma: say menciona un id con forma \b(p0|n[0-9]+|h[0-9]+)\b que no está en snap["entities"]
    say = reaction.get("say", "")
    mentioned = re.findall(r"\b(p0|n[0-9]+|h[0-9]+)\b", say)
    for mid in mentioned:
        if mid not in entities_map:
            reasons.append(f"H3: entity-fantasma ({mid})")

    # H4 evento-fantasma: say afirma un tipo de evento que no está en la ventana
    # Mapa fijo:
    # muerte|murio|murió|died -> died
    # atac|attack|golpe -> attack
    # toc(ó|o)|contacto|contact -> contact
    # vida baja|hp bajo|herido -> hp_low
    window_types = {e.get("type") for e in events_window}
    say_lower = say.lower()

    if re.search(r"\b(muerte|muri[oó]|died)\b", say_lower):
        if "died" not in window_types:
            reasons.append("H4: evento-fantasma (died)")

    if re.search(r"(atac|attack|golpe)", say_lower):
        if "attack" not in window_types:
            reasons.append("H4: evento-fantasma (attack)")

    if re.search(r"(toc[oó]|contacto|contact)", say_lower):
        if "contact" not in window_types:
            reasons.append("H4: evento-fantasma (contact)")

    if re.search(r"(vida baja|hp bajo|\bherido\b)", say_lower):
        if "hp_low" not in window_types:
            reasons.append("H4: evento-fantasma (hp_low)")

    return {
        "hallucinated": len(reasons) > 0,
        "reasons": reasons,
    }


def react(
    url: str,
    model: str,
    events_window: list[dict],
    snap: dict,
    timeout: float = 300.0,
) -> dict:
    t0 = time.perf_counter()
    try:
        system, user = build_big_prompt(events_window, snap)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 220,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")

        latency_ms = (time.perf_counter() - t0) * 1000.0
        data = json.loads(resp_body)

        choices = data.get("choices", [])
        raw = ""
        if choices and isinstance(choices, list):
            msg = choices[0].get("message", {})
            raw = msg.get("content", "") or ""

        parsed = parse_big_reaction(raw)
        if parsed is None:
            return {
                "say": "",
                "override": None,
                "refs": [],
                "raw": raw,
                "latency_ms": latency_ms,
                "unparseable": True,
            }

        return {
            "say": parsed["say"],
            "override": parsed["override"],
            "refs": parsed["refs"],
            "raw": raw,
            "latency_ms": latency_ms,
            "unparseable": False,
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "say": "",
            "override": None,
            "refs": [],
            "raw": "",
            "error": str(e),
            "latency_ms": latency_ms,
            "unparseable": True,
        }
