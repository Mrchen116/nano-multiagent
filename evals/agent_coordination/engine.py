"""Dependency scheduling for coordination evaluations, independent of IM transport."""

import time

TERMINAL = {"passed", "failed", "blocked", "untriggered", "uncertain"}


class Engine:
    def __init__(
        self, case, runtime, checkpoint=None, save=lambda value: None, now=time.time
    ):
        self.case, self.runtime, self.save, self.now = case, runtime, save, now
        if checkpoint and checkpoint["case_sha256"] != case["sha256"]:
            raise ValueError("Case changed since checkpoint; use a fresh run")
        self.state = checkpoint or {
            "case_sha256": case["sha256"],
            "nodes": {},
            "workers": {},
        }
        for node in case["nodes"]:
            state = self.state["nodes"].setdefault(node["id"], {"status": "pending"})
            if state["status"] == "sending":
                state.update(
                    status="uncertain",
                    reason="Interrupted action has no confirmed receipt; inspect IM before a fresh run",
                )
        self.save(self.state)

    def finish(self, state, status, **fields):
        state.update(status=status, completed_at=self.now(), **fields)
        self.save(self.state)

    def tick(self):
        self.runtime.refresh()
        states = self.state["nodes"]
        for node in self.case["nodes"]:
            state = states[node["id"]]
            if state["status"] in TERMINAL:
                continue
            dependencies = [*node.get("after", []), *node.get("order_after", [])]
            if any(states[d]["status"] not in TERMINAL for d in dependencies):
                continue
            failed = [
                d for d in node.get("after", []) if states[d]["status"] != "passed"
            ]
            if failed:
                self.finish(state, "blocked", blocked_by=failed)
                continue
            if state["status"] == "pending":
                state.update(
                    status="waiting",
                    started_at=self.now(),
                    deadline=self.now() + node.get("timeout", 120),
                )
                self.save(self.state)
            try:
                if node["type"] in {"user_message", "worker_message"}:
                    if "chosen" not in state:
                        evidence = self.runtime.condition(
                            node.get("when"), node, self.state
                        )
                        if evidence is None and self.now() < state["deadline"]:
                            continue
                        if evidence is None and "fallback" not in node:
                            self.finish(
                                state,
                                "untriggered",
                                reason="Required visible predecessor did not arrive",
                            )
                            continue
                        state.update(
                            chosen="content" if evidence is not None else "fallback",
                            condition=evidence,
                        )
                        state["text"] = node[state["chosen"]]["text"]
                        self.save(self.state)
                    state["status"] = "sending"
                    self.save(self.state)
                    receipt = self.runtime.dispatch(node, state["text"], self.state)
                    self.finish(state, "passed", receipt=receipt)
                else:
                    evidence = self.runtime.observe(node, self.state)
                    if evidence:
                        self.finish(state, "passed", receipt=evidence)
                    elif self.now() >= state["deadline"]:
                        self.finish(
                            state,
                            "untriggered",
                            reason="Required observed action did not arrive",
                        )
            except Exception as error:
                # A transport error can happen after a remote send. Never assume it was rejected.
                status = "uncertain" if state["status"] == "sending" else "failed"
                self.finish(state, status, reason=str(error))
        return all(s["status"] in TERMINAL for s in states.values())
