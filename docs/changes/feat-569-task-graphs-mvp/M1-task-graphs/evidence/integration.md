# Integrated task graph evidence

## Baseline and scope

- Branch: `codex/feat-569-task-graphs`; implementation `f407ec609`, tool guidance/capability fixture `f6062432f`, test-only closure `cb45a06a5`.
- Final sync `99f6e1633` includes `origin/main=363eefc5d`; the incoming change only adds another unit's motivation document. It does not change the runtime, this unit's contracts or previous tests.
- Python uses the main checkout's `.venv` with `PYTHONPATH=src` pointing to this isolated worktree. Frontend dependencies/build are local to this worktree.
- This record covers implementation and integration. The independent [acceptance report](../../acceptance.md) owns product/viewport judgments once available.

## Local checks

| Check | Version / command | Result |
|---|---|---|
| Agent and PA CI shard | `f407ec609`: `pytest -m 'not e2e' -n 4 --dist worksteal tests/unit/agent tests/unit/personal_assistant` | 1986 passed; `/tmp/feat569-agent-pa-tests.log` |
| Remaining CI shard | `f407ec609`: `pytest -m 'not e2e' -n 4 --dist worksteal --ignore=tests/unit/agent --ignore=tests/unit/personal_assistant` | 2063 passed; 2 capability golden failures identified the newly added default tool missing from the expected catalog |
| Golden correction | `f6062432f`: `pytest tests/contract/test_capability_payload_contract.py tests/unit/personal_assistant/test_task_graph_tool.py -q` | 6 passed; only expected catalog entry and create guidance changed; prior shard results retained |
| Atomic resource and PA boundary | `f407ec609`: task graph domain/API/native tool/bridge tests | 29 passed; real loopback HTTP, actual binder and both work modes, agent membership removal, atomic conflicts and DB reopen covered |
| Existing WS owner | `f407ec609`: `test_task_result_correlates_and_releases_existing_business_lane` | 1 passed; mismatched response does not release the owner; matched response unblocks the next business frame |
| Recorded reason closure | `cb45a06a5`: `pytest tests/im_service/integration/test_task_graph_api.py -q`; frontend `task-graphs.test.tsx` | 6 + 6 passed; persisted reason returned over HTTP and visible in node details |
| Frontend CI | `d38360b8b`: `npm run test` | 84 files / 776 passed; later change-note rendering covered by the task-graph suite |
| Frontend build | `f407ec609`: `npm run build` | TypeScript and Vite passed; generated dist excluded from commits |
| Dependency audit | `npm audit --audit-level=critical` | Exit 0; no critical vulnerabilities; existing lower-severity advisories were not changed by this unit |
| Documentation and style | `scripts/docs-check`; `ruff check .`; `ruff format --check .`; `git diff --check` | Passed before canonical merge/archive; final documentation gate is rerun after those mechanical changes |

## Real prompt to durable record

The primary implementer ran the repository's `scripts/e2e-up.sh --feishu` in managed worktree `unit-feat-569`, using only the repository's dedicated E2E configuration and private test App profile. IM/Gateway/workspaces/node/database are isolated from production. The public base URL registered by this local test IM is `http://127.0.0.1:56231`; this localhost value is a property of the E2E configuration, not a generated production address.

At 2026-09-22 09:24 UTC, the test user submitted an ordinary Web IM message in `c_effntspv`, asking to save an empty DAG named 营销视频产品 to the current chat, with no target ID embedded in the human text. The real PA model (`deepseek:deepseek-v4-flash`) obtained the bound target from runtime context. Its first create omitted request_key and was rejected before network I/O; it then corrected that argument and received graph `tg_8f989d6cf6f3469e8d0d96420661bdd5`, revision 1, and a Web IM link. The tool description was subsequently clarified to make request_key mandatory for both create and apply.

A second normal message requested the approved 12-node nested structure. The Agent read the existing graph, applied the batch and reread it. HTTP `GET /im/v1/task-graphs/<id>?view=all` confirmed revision 2, all twelve nodes, eight dependencies across their separate scopes, the X-derived Z sibling relationship and selected Z. The exploratory parent and outer goal stayed `todo`; X was `done` with a negative cost result, Y was `paused`, and Z contained the three-step DAG. No task execution was requested or started by the graph operation.

The live chain was user message → PA model/native tool → loopback listener → authenticated Gateway WS command → IM service/SQLite → correlated tool result → ordinary Agent reply. Runtime Session: `sess_32f13cdc99f57a9b`; first turn: `turn_7f1cd158a7f22ed7`. The raw sessions, logs and databases remain local runtime data; this document records only the necessary test identities and outcomes.

The Gateway was restarted from `99f6e1633` against the same isolated config and stored data before independent acceptance. It did not recreate the graph. Independent acceptance must still establish the browser, external-chat, empty/error, draft-preservation and prototype-specific results; these are not inferred from the HTTP response above.

## Draft navigation regression and final frontend checks

At `21f79e3d8`, actual Chat/Work Markdown task links retain SPA navigation. The previous implementation erased the module-held composer when ordinary anchors loaded a new document. Regression assertions first failed on both entry points; the corrected MessagePane round trip preserves text, mentions and pending attachment data and only appends a task reference. The targeted four suites passed 140 tests; final `npm run test` passed 84 files / 777 tests in 36.83 seconds. `npm run build` passed TypeScript and Vite. Logs: `/tmp/feat569-draft-fix-tests.log`, `/tmp/feat569-draft-fix-build.log`, `/tmp/feat569-frontend-final.log`. The independent product report owns the real-browser revalidation result.
