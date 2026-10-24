from __future__ import annotations

import random


class World:
    def __init__(self, seed: int, ticks: int, tick_ms: int = 500) -> None:
        self.seed = seed
        self.ticks = ticks
        self.tick_ms = tick_ms
        self.tick = 0
        self.rng = random.Random(seed)
        self.event_counter = 0
        self._events: list[dict] = []
        self._hp_low_emitted: set[str] = set()
        self._died_emitted: set[str] = set()

        self.entities: dict[str, dict] = {}
        # Fixed entities: p0 (player), n1..n7 (npcs), h1, h2 (hazards)
        self.entities["p0"] = {
            "id": "p0",
            "kind": "player",
            "pos": [self.rng.randint(5, 25), self.rng.randint(5, 25)],
            "hp": 100,
            "stamina": 100,
        }

        for i in range(1, 8):
            nid = f"n{i}"
            self.entities[nid] = {
                "id": nid,
                "kind": "npc",
                "pos": [self.rng.randint(0, 31), self.rng.randint(0, 31)],
                "hp": 100,
                "stamina": 100,
            }

        for i in range(1, 3):
            hid = f"h{i}"
            self.entities[hid] = {
                "id": hid,
                "kind": "hazard",
                "pos": [self.rng.randint(0, 31), self.rng.randint(0, 31)],
                "hp": 100,
                "stamina": 100,
            }

        self.alive: list[str] = sorted(list(self.entities.keys()))

    def _emit_event(self, type: str, subject: str, detail: str) -> dict:
        self.event_counter += 1
        event = {
            "event_id": f"e{self.event_counter}",
            "tick": self.tick,
            "type": type,
            "subject": subject,
            "detail": detail,
        }
        self._events.append(event)
        return event

    def observation(self) -> dict:
        p0 = self.entities["p0"]
        candidates = []
        for eid, ent in self.entities.items():
            if eid != "p0" and eid in self.alive:
                dist = abs(ent["pos"][0] - p0["pos"][0]) + abs(ent["pos"][1] - p0["pos"][1])
                candidates.append((dist, eid, ent))

        candidates.sort(key=lambda c: (c[0], c[1]))
        visible = []
        for dist, eid, ent in candidates[:5]:
            visible.append({
                "id": eid,
                "kind": ent["kind"],
                "pos": list(ent["pos"]),
                "dist": dist,
                "hp": ent["hp"],
            })

        return {
            "tick": self.tick,
            "tick_ms": self.tick_ms,
            "self": {
                "pos": list(p0["pos"]),
                "hp": p0["hp"],
                "stamina": p0["stamina"],
            },
            "visible": visible,
            "flags": {},
        }

    def legal_actions(self) -> list[str]:
        obs = self.observation()
        actions = []
        for v in obs["visible"]:
            vid = v["id"]
            if vid in self.alive:
                actions.append(f"attack:{vid}")
                actions.append(f"flee:{vid}")
                actions.append(f"goto:{vid}")
        actions.append("wait")
        actions.append("call_big")
        return sorted(actions)

    def apply(self, label: str) -> None:
        legal = self.legal_actions()
        if label not in legal:
            self._emit_event(
                type="rejected",
                subject="p0",
                detail=f"illegal_action:{label}",
            )
            return

        if label == "wait":
            self.entities["p0"]["stamina"] = min(100, self.entities["p0"]["stamina"] + 5)
            return

        if label == "call_big":
            self._emit_event(
                type="escalate",
                subject="p0",
                detail="call_big",
            )
            return

        verb, target_id = label.split(":", 1)
        p0 = self.entities["p0"]
        target = self.entities.get(target_id)
        if not target:
            return

        if verb == "goto":
            dx = target["pos"][0] - p0["pos"][0]
            dy = target["pos"][1] - p0["pos"][1]
            if abs(dx) >= abs(dy) and dx != 0:
                p0["pos"][0] += 1 if dx > 0 else -1
            elif dy != 0:
                p0["pos"][1] += 1 if dy > 0 else -1
            p0["pos"][0] = max(0, min(31, p0["pos"][0]))
            p0["pos"][1] = max(0, min(31, p0["pos"][1]))
            p0["stamina"] = max(0, p0["stamina"] - 1)

        elif verb == "flee":
            dx = target["pos"][0] - p0["pos"][0]
            dy = target["pos"][1] - p0["pos"][1]
            if abs(dx) >= abs(dy) and dx != 0:
                p0["pos"][0] -= 1 if dx > 0 else -1
            elif dy != 0:
                p0["pos"][1] -= 1 if dy > 0 else -1
            else:
                if p0["pos"][0] > 0:
                    p0["pos"][0] -= 1
                else:
                    p0["pos"][0] += 1
            p0["pos"][0] = max(0, min(31, p0["pos"][0]))
            p0["pos"][1] = max(0, min(31, p0["pos"][1]))
            p0["stamina"] = max(0, p0["stamina"] - 2)

        elif verb == "attack":
            damage = 25
            target["hp"] = max(0, target["hp"] - damage)
            p0["stamina"] = max(0, p0["stamina"] - 5)
            self._emit_event(
                type="attack",
                subject=target_id,
                detail=f"p0 attacked {target_id}",
            )
            if target["hp"] <= 25 and target_id not in self._hp_low_emitted:
                self._hp_low_emitted.add(target_id)
                self._emit_event(
                    type="hp_low",
                    subject=target_id,
                    detail=f"{target_id} hp low",
                )
            if target["hp"] <= 0 and target_id not in self._died_emitted:
                self._died_emitted.add(target_id)
                if target_id in self.alive:
                    self.alive.remove(target_id)
                self._emit_event(
                    type="died",
                    subject=target_id,
                    detail=f"{target_id} died",
                )

    def step(self) -> None:
        hazards = [self.entities[hid] for hid in ["h1", "h2"] if hid in self.alive]
        for h in hazards:
            alive_npcs = [self.entities[nid] for nid in self.alive if nid.startswith("n")]
            if alive_npcs:
                alive_npcs.sort(
                    key=lambda n: (
                        abs(n["pos"][0] - h["pos"][0]) + abs(n["pos"][1] - h["pos"][1]),
                        n["id"],
                    )
                )
                target = alive_npcs[0]
                dx = target["pos"][0] - h["pos"][0]
                dy = target["pos"][1] - h["pos"][1]
                if abs(dx) >= abs(dy) and dx != 0:
                    h["pos"][0] += 1 if dx > 0 else -1
                elif dy != 0:
                    h["pos"][1] += 1 if dy > 0 else -1
                h["pos"][0] = max(0, min(31, h["pos"][0]))
                h["pos"][1] = max(0, min(31, h["pos"][1]))

            for eid in list(self.alive):
                ent = self.entities[eid]
                if ent["kind"] == "hazard":
                    continue
                dist_chebyshev = max(abs(h["pos"][0] - ent["pos"][0]), abs(h["pos"][1] - ent["pos"][1]))
                if dist_chebyshev <= 1:
                    dmg = 15
                    ent["hp"] = max(0, ent["hp"] - dmg)
                    self._emit_event(
                        type="contact",
                        subject=eid,
                        detail=f"{h['id']} contact with {eid}",
                    )
                    if ent["hp"] <= 25 and eid not in self._hp_low_emitted:
                        self._hp_low_emitted.add(eid)
                        self._emit_event(
                            type="hp_low",
                            subject=eid,
                            detail=f"{eid} hp low",
                        )
                    if ent["hp"] <= 0 and eid not in self._died_emitted:
                        self._died_emitted.add(eid)
                        if eid in self.alive:
                            self.alive.remove(eid)
                        self._emit_event(
                            type="died",
                            subject=eid,
                            detail=f"{eid} died",
                        )

        self.tick += 1

    def events(self) -> list[dict]:
        return [dict(e) for e in self._events]

    def snapshot(self) -> dict:
        entities_copy = {
            eid: {
                "id": ent["id"],
                "kind": ent["kind"],
                "pos": list(ent["pos"]),
                "hp": ent["hp"],
                "stamina": ent["stamina"],
            }
            for eid, ent in self.entities.items()
        }
        return {
            "tick": self.tick,
            "entities": entities_copy,
            "alive": sorted(list(self.alive)),
            "event_ids": [e["event_id"] for e in self._events],
        }
