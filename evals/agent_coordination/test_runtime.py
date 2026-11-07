"""Check the real adapter's consumption boundary without contacting a model."""

from datetime import datetime, timezone
import unittest
from runtime import Runtime


class RuntimeBoundaryTest(unittest.TestCase):
    def test_public_question_requires_actual_root_consumption_and_then_order(self):
        runtime = Runtime.__new__(Runtime)
        runtime.root = "root"
        runtime.wire = []
        node = {"id": "Q", "after": ["S"], "after_report": "S"}
        state = {
            "nodes": {
                "S": {
                    "status": "passed",
                    "text": "Which platform?",
                    "completed_at": 1,
                    "receipt": {"child": "child", "at": 1},
                }
            }
        }

        def public(at):
            runtime.messages = [
                {
                    "id": "public",
                    "created_at": datetime.fromtimestamp(at, timezone.utc).isoformat(),
                    "sender": {"type": "agent"},
                    "content": "macOS or Windows?",
                }
            ]

        public(3)
        self.assertIsNone(runtime.public_match(node, state, {"all": ["macOS"]}))
        runtime.wire = [
            {
                "type": "root_request",
                "root": "root",
                "at": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Agent child sent a message: Which platform?",
                            }
                        ],
                    }
                ],
            }
        ]
        self.assertIsNone(runtime.public_match(node, state, {"all": ["macOS"]}))
        public(5)
        receipt = runtime.public_match(node, state, {"all": ["macOS"]})
        self.assertEqual(receipt["message_id"], "public")
        self.assertEqual(receipt["root_request_at"], 4000)

    def test_choice_uses_predecessor_receipt_even_if_it_is_older_than_current_node(
        self,
    ):
        runtime = Runtime.__new__(Runtime)
        state = {
            "nodes": {
                "Q": {"completed_at": 10, "receipt": {"at": 9, "text": "B macOS first"}}
            }
        }
        result = runtime.condition(
            {"evidence_node": "Q", "matcher": {"all": ["B.*macOS"]}}, {}, state
        )
        self.assertEqual(result["at"], 9)


class ConsumedRowsTest(unittest.TestCase):
    def test_native_received_without_model_request_is_not_consumed(self):
        from runtime import consumed_rows

        event = {
            "type": "user/message",
            "seq": 14,
            "time": 2000,
            "data": {
                "source": {"kind": "agent-message"},
                "content": [{"type": "text", "text": "User decided B"}],
            },
        }
        wire = [
            {
                "type": "child_request",
                "id": "child",
                "at": 3000,
                "messages": [{"role": "user", "content": "Earlier decision A"}],
            }
        ]
        self.assertEqual(list(consumed_rows([event], wire, "child")), [])
        wire[0]["messages"][0]["content"] = "User decided B"
        self.assertEqual(
            list(consumed_rows([event], wire, "child"))[0]["request_at"], 3000
        )
        self.assertEqual(list(consumed_rows([event], wire, "child", since=2.5)), [])


if __name__ == "__main__":
    unittest.main()
