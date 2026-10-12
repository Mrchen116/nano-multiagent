# Legacy test disposition

This inventory records ownership changes, not a claim that old test counts survived unchanged. The immutable pre-migration revision is `4915c44cb7f7b829414a19087877ad9b73d69ea1`; old test implementations remain recoverable there. Research/evaluation baselines and raw evidence are retained.

| Previous owner | Disposition | Current owner and distinct protection |
|---|---|---|
| Python `src/agent` unit/contract/integration tests | retire with implementation | Official pinned DSH owns model loop, native session persistence, tools, subagents and scheduling. `packages/dsh-integration/tests/` exercises the actual installed profile through public APIs for Nano restrictions, approval, model fallback, compaction, history, Workflow and knowledge. No private framework implementation is ported. |
| Python coding CLI tests | retire | Coding CLI is explicitly withdrawn by refactor-581. No substitute CLI behavior is claimed. |
| Python PA tests | rewrite-merge | `packages/personal-assistant/tests/` owns Inbox, routing, durable delivery, configuration, background knowledge, heartbeat, native history and usage. `apps/node/tests/` owns actual process lifecycle, configuration, transport, binding and asset conversion. |
| Python IM tests | rewrite-merge | `apps/im-server/tests/` owns native HTTP/WebSocket and retained SQLite behavior, identity compatibility, owner isolation, channel enrollment, delivery and work views. React/Swift tests remain with their clients. |
| Old import-boundary assertions | rewrite | `tests/contract/test_runtime_dependency_contract.py` checks native package direction, official public DSH imports, pinned dependencies and removal of Python executable packages. |
| Old kernel self-evolution replay-fault fixtures | rewrite-merge | Real DSH `knowledge.test.ts` plus product `knowledge.test.ts` cover private branches, native writes, durable facts, notice deduplication, allowlist activation and cold recovery. The old private Python event injection is retired; these tests are not represented as full IM end-to-end tests. M3 records actual full-stack model evidence; final native-center acceptance is recorded separately. |
| Old cache warning / session JSONL shape | rewrite | Public token-usage critical path checks provider accounting through native Node/IM, visible bubble and metrics. Native adapter reports unavailable cache counters as absent, never invented zero. |
| Old `compact_boundary` internals | rewrite | Public `/compact` critical path checks a real tool result, summary focus, subsequent provider context and process restart. Native automatic pressure/overflow stays under model-policy/history tests. |
| Existing user critical paths | keep / adapt | Public HTTP/WS journeys remain. Native tool names/arguments and TypeScript process entrypoints replace retired Python API assumptions. Tests assert real tool/output and child identities where applicable. |
| Worktree startup fixtures | rewrite | Node preload delays/exits only the actual isolated IM child; tests retain readiness deadline, process ownership and cleanup checks. Runtime evidence is retained after stop. |
| Python dev-tool tests | keep | Docs integrity, change workflow, E2E profile selection, shell/Feishu helper rendering and test naming remain standalone tooling. |

Validation is recorded in [progress.md](progress.md). Removing an obsolete assertion does not turn an unrun replacement into a pass; physical iOS, real Feishu and final product review remain separate evidence gates.
