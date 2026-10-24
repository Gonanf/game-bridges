import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import probes


def test_parse_small_label():
    legal = ["attack:n1", "goto:n3", "wait", "call_big"]

    assert probes.parse_small_label(" GOTO:n3 ", legal) == "goto:n3"
    assert probes.parse_small_label("`goto:n3`", legal) == "goto:n3"
    assert probes.parse_small_label("`GOTO:n3`", legal) == "goto:n3"
    assert probes.parse_small_label("ACTION: wait", legal) == "wait"
    assert probes.parse_small_label("ACTION: `wait`", legal) == "wait"
    assert probes.parse_small_label("basura no valida", legal) is None
    assert probes.parse_small_label("", legal) is None


def test_parse_big_reaction():
    text = """```json
    {
      "say": "Detecté actividad hostil",
      "override": {"verb": "goto", "target": "n3"},
      "refs": ["e1", "e2"]
    }
    ```"""
    res = probes.parse_big_reaction(text)
    assert res is not None
    assert res["say"] == "Detecté actividad hostil"
    assert res["override"] == {"verb": "goto", "target": "n3"}
    assert res["refs"] == ["e1", "e2"]

    text_no_fence = '{"say": "Todo en orden", "override": null, "refs": []}'
    res2 = probes.parse_big_reaction(text_no_fence)
    assert res2 is not None
    assert res2["say"] == "Todo en orden"
    assert res2["override"] is None
    assert res2["refs"] == []

    assert probes.parse_big_reaction("Esto no es json") is None


def test_build_small_prompt_length():
    obs = {
        "tick": 42,
        "tick_ms": 500,
        "self": {"pos": [15, 15], "hp": 90, "stamina": 85},
        "visible": [
            {"id": "n1", "kind": "npc", "pos": [16, 15], "dist": 1, "hp": 100},
            {"id": "n2", "kind": "npc", "pos": [14, 15], "dist": 1, "hp": 100},
            {"id": "h1", "kind": "hazard", "pos": [20, 20], "dist": 10, "hp": 100},
            {"id": "h2", "kind": "hazard", "pos": [25, 25], "dist": 20, "hp": 100},
            {"id": "n3", "kind": "npc", "pos": [10, 10], "dist": 10, "hp": 100},
        ],
        "flags": {},
    }
    legal = ["attack:n1", "attack:n2", "flee:h1", "goto:n1", "wait", "call_big"]
    _, user = probes.build_small_prompt(obs, legal)
    words = user.split()
    assert len(words) <= 300


def test_build_grammar():
    grammar = probes.build_grammar(["wait", "goto:n3"])
    assert grammar.startswith("root ::= ")
    assert '"wait"' in grammar
    assert '"goto:n3"' in grammar
