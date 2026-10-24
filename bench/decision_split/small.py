from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from probes import build_grammar, build_small_prompt, parse_small_label


def decide(
    url: str,
    model: str,
    obs: dict,
    legal: list[str],
    timeout: float = 20.0,
    use_grammar: bool = True,
) -> dict:
    t0 = time.perf_counter()
    try:
        system, user = build_small_prompt(obs, legal)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 12,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if use_grammar:
            payload["grammar"] = build_grammar(legal)

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

        label = parse_small_label(raw, legal)
        is_legal = label is not None and label in legal

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

        raw_timings = data.get("timings")
        timings = None
        if isinstance(raw_timings, dict):
            timings = {
                "prompt_ms": raw_timings.get("prompt_ms"),
                "predicted_ms": raw_timings.get("predicted_ms"),
            }

        return {
            "label": label,
            "legal": is_legal,
            "raw": raw,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "timings": timings,
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "label": None,
            "legal": False,
            "raw": "",
            "error": str(e),
            "latency_ms": latency_ms,
            "prompt_tokens": None,
            "completion_tokens": None,
            "timings": None,
        }
