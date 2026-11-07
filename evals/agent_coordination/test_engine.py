"""Regression coverage for dependency, fallback and interruption semantics."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import json
import re

from case import load_case, matches, ROOT
from engine import Engine


class Transport:
    def __init__(self):
        self.seen = {}
        self.sent = []

    def refresh(self):
        pass

    def condition(self, when, node, state):
        return {} if not when else self.seen.get(node["id"])

    def dispatch(self, node, text, state):
        self.sent.append((node["id"], text))
        return {"text": text}

    def observe(self, node, state):
        return self.seen.get(node["id"])


class EngineTest(unittest.TestCase):
    def case(self, nodes):
        return {"id": "test", "sha256": "frozen", "nodes": nodes}

    def test_untriggered_chain_does_not_block_independent_task(self):
        clock = [0]
        nodes = [
            {"id": "Q", "type": "user_reply", "after": [], "timeout": 5},
            {
                "id": "answer",
                "type": "user_message",
                "after": ["Q"],
                "content": {"text": "Yes"},
            },
            {
                "id": "independent",
                "type": "user_message",
                "after": [],
                "order_after": ["Q"],
                "content": {"text": "Other task"},
            },
        ]
        transport = Transport()
        engine = Engine(self.case(nodes), transport, now=lambda: clock[0])
        self.assertFalse(engine.tick())
        clock[0] = 6
        self.assertTrue(engine.tick())
        self.assertEqual(engine.state["nodes"]["Q"]["status"], "untriggered")
        self.assertEqual(engine.state["nodes"]["answer"]["status"], "blocked")
        self.assertEqual(transport.sent, [("independent", "Other task")])

    def test_fallback_is_a_successful_frozen_choice(self):
        clock = [0]
        transport = Transport()
        nodes = [
            {
                "id": "U",
                "type": "user_message",
                "after": [],
                "timeout": 5,
                "when": {"source": "public"},
                "content": {"text": "B"},
                "fallback": {"text": "macOS first"},
            }
        ]
        saved = []
        engine = Engine(
            self.case(nodes),
            transport,
            save=lambda s: saved.append(deepcopy(s)),
            now=lambda: clock[0],
        )
        engine.tick()
        clock[0] = 6
        self.assertTrue(engine.tick())
        transport.seen["U"] = {"text": "B means macOS"}
        restored = Engine(
            self.case(nodes), transport, checkpoint=saved[-1], now=lambda: clock[0]
        )
        self.assertTrue(restored.tick())
        self.assertEqual(transport.sent, [("U", "macOS first")])
        self.assertEqual(restored.state["nodes"]["U"]["chosen"], "fallback")

    def test_unknown_send_is_not_retried_after_resume(self):
        transport = Transport()
        node = {
            "id": "U",
            "type": "user_message",
            "after": [],
            "content": {"text": "Hello"},
        }
        checkpoint = {
            "case_sha256": "frozen",
            "workers": {},
            "nodes": {"U": {"status": "sending", "text": "Hello"}},
        }
        engine = Engine(self.case([node]), transport, checkpoint=checkpoint)
        self.assertTrue(engine.tick())
        self.assertEqual(transport.sent, [])
        self.assertEqual(engine.state["nodes"]["U"]["status"], "uncertain")
        with self.assertRaises(ValueError):
            Engine(
                {"sha256": "changed", "nodes": [node]}, transport, checkpoint=checkpoint
            )

    def test_real_cases_load_and_user_source_matches_selected_words(self):
        for path in (ROOT / "cases").glob("*/case.json"):
            case = load_case(path)
            self.assertGreater(len(case["nodes"]), 10)
        state = {"U": {"text": "Codex 的 computer use，上网搜你就知道我说的是啥了"}}
        self.assertTrue(
            matches("用户原话：" + state["U"]["text"], {"source_node": "U"}, state)
        )
        self.assertFalse(matches("我会自己研究", {"source_node": "U"}, state))

    def test_loader_rejects_cycles_missing_materials_and_invalid_regex(self):
        original = json.loads((ROOT / "cases/gc02/case.json").read_text())
        with tempfile.TemporaryDirectory(dir=ROOT / "cases") as tmp:
            path = Path(tmp) / "case.json"
            for change in ("cycle", "regex", "material"):
                case = deepcopy(original)
                # Use inline content so unrelated relative paths do not hide the intended error.
                for node in case["nodes"]:
                    if node.get("content", {}).get("file"):
                        node["content"] = {"text": "report"}
                if change == "cycle":
                    case["nodes"][0]["after"] = [case["nodes"][-1]["id"]]
                if change == "regex":
                    case["nodes"][1]["matcher"] = {"all": ["["]}
                if change == "material":
                    case["nodes"][0]["content"] = {"file": "../../../private.md"}
                path.write_text(json.dumps(case))
                with self.assertRaises((ValueError, re.error)):
                    load_case(path)


if __name__ == "__main__":
    unittest.main()
