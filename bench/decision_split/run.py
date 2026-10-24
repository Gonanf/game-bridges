from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import big
import probes
import small
from world import World


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    if n == 1:
        return float(sorted_v[0])
    idx = (n - 1) * p
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    if lower == upper:
        return float(sorted_v[lower])
    weight = idx - lower
    return float(sorted_v[lower] * (1.0 - weight) + sorted_v[upper] * weight)


def scripted_small_policy(obs: dict, legal: list[str]) -> str:
    p0_hp = obs["self"]["hp"]
    visible = obs["visible"]
    tick = obs["tick"]

    # hp<40 y peligro visible => flee:<id>
    if p0_hp < 40:
        hazards = [v for v in visible if v["kind"] == "hazard"]
        if hazards:
            action = f"flee:{hazards[0]['id']}"
            if action in legal:
                return action

    # npc a distancia 1 => attack:<id>
    close_npcs = [v for v in visible if v["kind"] == "npc" and v["dist"] == 1]
    if close_npcs:
        action = f"attack:{close_npcs[0]['id']}"
        if action in legal:
            return action

    # tick%7==0 => call_big
    if tick % 7 == 0 and "call_big" in legal:
        return "call_big"

    # si no => goto:<más cercano>
    if visible:
        target_id = visible[0]["id"]
        action = f"goto:{target_id}"
        if action in legal:
            return action

    if "wait" in legal:
        return "wait"
    return legal[0] if legal else "wait"


def mock_small_decide(obs: dict, legal: list[str]) -> dict:
    t0 = time.perf_counter()
    label = scripted_small_policy(obs, legal)
    latency_ms = (time.perf_counter() - t0) * 1000.0 + 0.2
    return {
        "label": label,
        "legal": label in legal,
        "raw": label,
        "latency_ms": latency_ms,
        "prompt_tokens": 40,
        "completion_tokens": 2,
        "timings": {"prompt_ms": 0.5, "predicted_ms": 1.0},
    }


def mock_big_react(events_window: list[dict], snap: dict) -> dict:
    t0 = time.perf_counter()
    valid_refs = [e["event_id"] for e in events_window[-3:] if "event_id" in e]
    alive_npcs = [eid for eid in snap.get("alive", []) if eid.startswith("n")]
    override = None
    if alive_npcs:
        override = {"verb": "goto", "target": alive_npcs[0]}

    say = f"Revisando eventos {', '.join(valid_refs)}." if valid_refs else "Sin novedades."
    latency_ms = (time.perf_counter() - t0) * 1000.0 + 0.5
    return {
        "say": say,
        "override": override,
        "refs": valid_refs,
        "raw": json.dumps({"say": say, "override": override, "refs": valid_refs}),
        "latency_ms": latency_ms,
        "unparseable": False,
    }


def save_summary(path: str, summary: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def run_replay(args: argparse.Namespace) -> None:
    windows_file = args.replay_windows
    if not os.path.exists(windows_file):
        raise FileNotFoundError(f"Replay file not found: {windows_file}")

    with open(windows_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    big_latencies: list[float] = []
    big_hallucinated = 0
    big_unparseable = 0
    big_orders = 0

    config = {
        "replay_file": args.replay_windows,
        "big_url": args.big_url,
        "big_model": args.big_model,
        "mock": args.mock,
    }

    summary: dict = {
        "config": config,
        "pooled": {
            "big": {
                "n": 0,
                "hallucinated": 0,
                "rate": 0.0,
                "unparseable": 0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
            }
        },
        "verdict": "RUNNING",
    }

    for idx, line in enumerate(lines, start=1):
        record = json.loads(line)
        events_window = record.get("events_window", [])
        snap = record.get("snap", {})

        if args.mock:
            reaction = mock_big_react(events_window, snap)
        else:
            reaction = big.react(args.big_url, args.big_model, events_window, snap)

        h_res = big.judge_hallucination(reaction, events_window, snap)
        big_latencies.append(reaction.get("latency_ms", 0.0))
        if reaction.get("override") is not None:
            big_orders += 1
        if reaction.get("unparseable") is True:
            big_unparseable += 1
        elif h_res.get("hallucinated") is True:
            big_hallucinated += 1

        rate = (big_hallucinated / idx) if idx > 0 else 0.0
        p50 = percentile(big_latencies, 0.50)
        p95 = percentile(big_latencies, 0.95)

        summary["pooled"]["big"] = {
            "n": idx,
            "hallucinated": big_hallucinated,
            "rate": rate,
            "unparseable": big_unparseable,
            "p50_ms": p50,
            "p95_ms": p95,
        }
        verdict = f"REPLAY_COMPLETE: n={idx}, hallucination_rate={rate:.1%}, p50={p50:.1f}ms, p95={p95:.1f}ms"
        summary["verdict"] = verdict
        save_summary(args.out, summary)

    print(f"SUMMARY_JSON: {json.dumps(summary, separators=(',', ':'))}")
    print("\n" + "=" * 50)
    print("REPLAY COMPLETE")
    print(f"Big calls: {len(big_latencies)}, Hallucinated: {big_hallucinated}, Rate: {summary['pooled']['big']['rate']:.1%}")
    print(f"Verdict: {summary['verdict']}")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision split benchmark runner")
    parser.add_argument("--seeds", type=str, default="1,2,3")
    parser.add_argument("--ticks", type=int, default=200)
    parser.add_argument("--tick-ms", type=int, default=500)
    parser.add_argument("--small-url", type=str, default="http://127.0.0.1:11434/v1/chat/completions")
    parser.add_argument("--small-model", type=str, default="MiniCPM5-1B")
    parser.add_argument("--big-url", type=str, default="http://127.0.0.1:11434/v1/chat/completions")
    parser.add_argument("--big-model", type=str, default="Sharp-MiniCPM5-2B")
    parser.add_argument("--big-every", type=int, default=10)
    parser.add_argument("--out", type=str, default="out/summary.json")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--no-grammar", action="store_true")
    parser.add_argument("--note", type=str, default="")
    parser.add_argument("--record-windows", type=str, default=None)
    parser.add_argument("--replay-windows", type=str, default=None)

    args = parser.parse_args()

    if args.replay_windows:
        run_replay(args)
        return

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    use_grammar = not args.no_grammar

    config = {
        "seeds": seeds,
        "ticks": args.ticks,
        "tick_ms": args.tick_ms,
        "small_model": args.small_model,
        "big_model": args.big_model,
        "mock": args.mock,
        "big_every": args.big_every,
        "grammar": use_grammar,
        "note": args.note,
    }

    per_seed: dict[str, dict] = {}
    all_decisions_latencies: list[float] = []
    all_illegal_count = 0
    all_decisions_count = 0
    all_valid_labels: set[str] = set()

    all_big_latencies: list[float] = []
    all_big_hallucinated = 0
    all_big_unparseable = 0
    all_big_orders = 0
    all_big_n = 0

    total_survival_ticks = 0
    total_damage_taken = 0

    record_file = None
    if args.record_windows:
        os.makedirs(os.path.dirname(os.path.abspath(args.record_windows)), exist_ok=True)
        record_file = open(args.record_windows, "w", encoding="utf-8")

    try:
        for seed in seeds:
            world = World(seed=seed, ticks=args.ticks, tick_ms=args.tick_ms)
            seed_latencies: list[float] = []
            seed_illegal = 0
            seed_decisions = 0
            seed_big_latencies: list[float] = []
            seed_big_hallucinated = 0
            seed_big_unparseable = 0
            p0_initial_hp = world.entities["p0"]["hp"]
            survival_ticks = args.ticks

            for tick in range(args.ticks):
                if "p0" not in world.alive or world.entities["p0"]["hp"] <= 0:
                    survival_ticks = tick
                    break

                obs = world.observation()
                legal = world.legal_actions()

                if args.mock:
                    res = mock_small_decide(obs, legal)
                else:
                    res = small.decide(
                        args.small_url,
                        args.small_model,
                        obs,
                        legal,
                        use_grammar=use_grammar,
                    )

                seed_decisions += 1
                all_decisions_count += 1
                lat = res.get("latency_ms", 0.0)
                seed_latencies.append(lat)
                all_decisions_latencies.append(lat)

                is_legal = res.get("legal", False)
                chosen_label = res.get("label")

                if not is_legal or chosen_label is None:
                    seed_illegal += 1
                    all_illegal_count += 1
                    chosen_label = "wait"
                else:
                    all_valid_labels.add(chosen_label)

                world.apply(chosen_label)

                # Check window recording
                record_interval = args.big_every if args.big_every > 0 else 10
                should_record = ((tick + 1) % record_interval == 0) or (chosen_label == "call_big")
                if record_file and should_record:
                    win_record = {
                        "seed": seed,
                        "tick": tick + 1,
                        "events_window": world.events()[-10:],
                        "snap": world.snapshot(),
                    }
                    record_file.write(json.dumps(win_record) + "\n")
                    record_file.flush()

                # Big model reaction
                if args.big_every > 0 and ((tick + 1) % args.big_every == 0):
                    events_win = world.events()[-10:]
                    snap = world.snapshot()
                    if args.mock:
                        b_res = mock_big_react(events_win, snap)
                    else:
                        b_res = big.react(args.big_url, args.big_model, events_win, snap)

                    all_big_n += 1
                    b_lat = b_res.get("latency_ms", 0.0)
                    seed_big_latencies.append(b_lat)
                    all_big_latencies.append(b_lat)

                    if b_res.get("override") is not None:
                        all_big_orders += 1

                    h_judge = big.judge_hallucination(b_res, events_win, snap)
                    if b_res.get("unparseable") is True:
                        seed_big_unparseable += 1
                        all_big_unparseable += 1
                    elif h_judge.get("hallucinated") is True:
                        seed_big_hallucinated += 1
                        all_big_hallucinated += 1

                world.step()

            p0_final_hp = world.entities["p0"]["hp"]
            damage = max(0, p0_initial_hp - p0_final_hp)
            total_damage_taken += damage
            total_survival_ticks += survival_ticks

            # Compute seed metrics
            p50 = percentile(seed_latencies, 0.50)
            p95 = percentile(seed_latencies, 0.95)
            max_ms = max(seed_latencies) if seed_latencies else 0.0
            cold_ms = seed_latencies[0] if seed_latencies else 0.0
            warm_lats = seed_latencies[1:] if len(seed_latencies) > 1 else seed_latencies
            p95_warm_ms = percentile(warm_lats, 0.95)
            inv_rate = (seed_illegal / seed_decisions) if seed_decisions > 0 else 0.0
            compliance = p95 < args.tick_ms

            big_n = len(seed_big_latencies)
            big_rate = (seed_big_hallucinated / big_n) if big_n > 0 else 0.0
            big_p50 = percentile(seed_big_latencies, 0.50)
            big_p95 = percentile(seed_big_latencies, 0.95)

            per_seed[str(seed)] = {
                "decisions": seed_decisions,
                "p50_ms": p50,
                "p95_ms": p95,
                "max_ms": max_ms,
                "cold_ms": cold_ms,
                "p95_warm_ms": p95_warm_ms,
                "invalid_rate": inv_rate,
                "tick_compliance": compliance,
                "big": {
                    "n": big_n,
                    "hallucinated": seed_big_hallucinated,
                    "rate": big_rate,
                    "unparseable": seed_big_unparseable,
                    "p50_ms": big_p50,
                    "p95_ms": big_p95,
                },
            }

            # Partial pooled computation to rewrite out after each seed
            pooled_p50 = percentile(all_decisions_latencies, 0.50)
            pooled_p95 = percentile(all_decisions_latencies, 0.95)
            pooled_max = max(all_decisions_latencies) if all_decisions_latencies else 0.0
            pooled_cold = all_decisions_latencies[0] if all_decisions_latencies else 0.0
            pooled_warm = all_decisions_latencies[1:] if len(all_decisions_latencies) > 1 else all_decisions_latencies
            pooled_p95_warm = percentile(pooled_warm, 0.95)
            pooled_inv = (all_illegal_count / all_decisions_count) if all_decisions_count > 0 else 0.0
            pooled_compliance = pooled_p95 < args.tick_ms

            pooled_big_rate = (all_big_hallucinated / all_big_n) if all_big_n > 0 else 0.0
            pooled_big_p50 = percentile(all_big_latencies, 0.50)
            pooled_big_p95 = percentile(all_big_latencies, 0.95)

            diversity = (len(all_valid_labels) / all_decisions_count) if all_decisions_count > 0 else 0.0

            pooled = {
                "decisions": all_decisions_count,
                "p50_ms": pooled_p50,
                "p95_ms": pooled_p95,
                "max_ms": pooled_max,
                "cold_ms": pooled_cold,
                "p95_warm_ms": pooled_p95_warm,
                "invalid_rate": pooled_inv,
                "tick_compliance": pooled_compliance,
                "big": {
                    "n": all_big_n,
                    "hallucinated": all_big_hallucinated,
                    "rate": pooled_big_rate,
                    "unparseable": all_big_unparseable,
                    "p50_ms": pooled_big_p50,
                    "p95_ms": pooled_big_p95,
                },
            }

            quality = {
                "survival_ticks": total_survival_ticks,
                "damage_taken": total_damage_taken,
                "action_diversity": diversity,
                "big_orders": all_big_orders,
            }

            verdict_status = "COMPLIANT" if pooled_compliance else "NON-COMPLIANT"
            verdict = (
                f"{verdict_status}: p95={pooled_p95:.1f}ms (budget={args.tick_ms}ms), "
                f"invalid_rate={pooled_inv:.1%}, big_hallucination_rate={pooled_big_rate:.1%}"
            )

            current_summary = {
                "config": config,
                "per_seed": per_seed,
                "pooled": pooled,
                "quality": quality,
                "verdict": verdict,
            }
            save_summary(args.out, current_summary)

    finally:
        if record_file:
            record_file.close()

    # Final summary print
    print(f"SUMMARY_JSON: {json.dumps(current_summary, separators=(',', ':'))}")
    print("\n" + "=" * 50)
    print("DECISION SPLIT BENCHMARK SUMMARY")
    print("=" * 50)
    for s, s_data in current_summary["per_seed"].items():
        print(
            f"Seed {s}: {s_data['decisions']} decisions, p50={s_data['p50_ms']:.1f}ms, "
            f"p95={s_data['p95_ms']:.1f}ms, invalid={s_data['invalid_rate']:.1%}, "
            f"big_hallucinated={s_data['big']['hallucinated']}/{s_data['big']['n']}"
        )
    print("-" * 50)
    print(
        f"POOLED: {pooled['decisions']} decisions, p50={pooled['p50_ms']:.1f}ms, "
        f"p95={pooled['p95_ms']:.1f}ms, invalid={pooled['invalid_rate']:.1%}, compliance={pooled['tick_compliance']}"
    )
    print(
        f"BIG MODEL: {pooled['big']['hallucinated']}/{pooled['big']['n']} hallucinated "
        f"(rate={pooled['big']['rate']:.1%})"
    )
    print(f"VERDICT: {current_summary['verdict']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
