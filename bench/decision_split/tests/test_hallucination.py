import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import big


def test_h1_ref_fantasma():
    events_window = [{"event_id": "e1", "type": "contact"}]
    snap = {"entities": {"p0": {}, "n1": {}}}
    reaction = {
        "say": "Continuamos avanzando",
        "override": None,
        "refs": ["e999"],
    }
    res = big.judge_hallucination(reaction, events_window, snap)
    assert res["hallucinated"] is True
    assert any("ref-fantasma" in r or "H1" in r for r in res["reasons"])


def test_h2_target_fantasma():
    events_window = [{"event_id": "e1", "type": "contact"}]
    snap = {"entities": {"p0": {}, "n1": {}}}
    reaction = {
        "say": "Ataquen al enemigo",
        "override": {"verb": "attack", "target": "n99"},
        "refs": ["e1"],
    }
    res = big.judge_hallucination(reaction, events_window, snap)
    assert res["hallucinated"] is True
    assert any("target-fantasma" in r or "H2" in r for r in res["reasons"])


def test_h3_entity_fantasma():
    events_window = [{"event_id": "e1", "type": "contact"}]
    snap = {"entities": {"p0": {}, "n1": {}}}
    reaction = {
        "say": "Veo a n9 cerca",
        "override": None,
        "refs": ["e1"],
    }
    res = big.judge_hallucination(reaction, events_window, snap)
    assert res["hallucinated"] is True
    assert any("entity-fantasma" in r or "H3" in r for r in res["reasons"])


def test_h4_evento_fantasma():
    events_window = [{"event_id": "e1", "type": "contact"}]
    snap = {"entities": {"p0": {}, "n1": {}}}
    reaction = {
        "say": "Alguien murió en combate",
        "override": None,
        "refs": ["e1"],
    }
    res = big.judge_hallucination(reaction, events_window, snap)
    assert res["hallucinated"] is True
    assert any("evento-fantasma" in r or "H4" in r for r in res["reasons"])


def test_clean_reaction_no_hallucination():
    events_window = [{"event_id": "e1", "type": "contact"}]
    snap = {"entities": {"p0": {}, "n1": {}}}
    reaction = {
        "say": "Hubo contacto en la zona",
        "override": {"verb": "goto", "target": "n1"},
        "refs": ["e1"],
    }
    res = big.judge_hallucination(reaction, events_window, snap)
    assert res["hallucinated"] is False
    assert res["reasons"] == []


def test_unparseable_reaction():
    events_window = [{"event_id": "e1", "type": "contact"}]
    snap = {"entities": {"p0": {}, "n1": {}}}

    res1 = big.judge_hallucination(None, events_window, snap)
    assert res1["hallucinated"] is False
    assert res1["reasons"] == ["unparseable"]

    res2 = big.judge_hallucination({"unparseable": True}, events_window, snap)
    assert res2["hallucinated"] is False
    assert res2["reasons"] == ["unparseable"]
