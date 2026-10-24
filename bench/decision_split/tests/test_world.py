import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import world


def test_determinism_same_seed():
    w1 = world.World(seed=42, ticks=30)
    w2 = world.World(seed=42, ticks=30)

    for _ in range(30):
        obs1 = w1.observation()
        obs2 = w2.observation()
        assert obs1 == obs2

        leg1 = w1.legal_actions()
        leg2 = w2.legal_actions()
        assert leg1 == leg2

        act = leg1[0]
        w1.apply(act)
        w2.apply(act)

        w1.step()
        w2.step()

    eids1 = [e["event_id"] for e in w1.events()]
    eids2 = [e["event_id"] for e in w2.events()]
    assert eids1 == eids2
    assert w1.events() == w2.events()
    assert w1.snapshot() == w2.snapshot()


def test_different_seeds_differ():
    w1 = world.World(seed=1, ticks=20)
    w2 = world.World(seed=2, ticks=20)

    w1.step()
    w2.step()

    assert w1.snapshot() != w2.snapshot()


def test_legal_actions_never_empty_in_50_ticks():
    w = world.World(seed=77, ticks=50)
    for _ in range(50):
        legal = w.legal_actions()
        assert len(legal) > 0
        assert "wait" in legal
        assert "call_big" in legal
        w.apply("wait")
        w.step()


def test_apply_illegal_action_rejected():
    w = world.World(seed=10, ticks=10)
    w.apply("goto:n99")
    events = w.events()
    assert len(events) >= 1
    rejected = [e for e in events if e["type"] == "rejected"]
    assert len(rejected) == 1
    assert rejected[0]["subject"] == "p0"
    assert rejected[0]["detail"] == "illegal_action:goto:n99"
