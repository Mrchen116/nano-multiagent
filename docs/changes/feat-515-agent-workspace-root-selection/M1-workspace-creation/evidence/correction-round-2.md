# feat-515-M1 round-2 correction evidence

Date: 2026-08-08 (Asia/Shanghai)

## Review targets

- Restore the approved fill-NULL-only root/provenance contract.
- Keep target-Gateway workspace syntax opaque in IM and Web IM.
- Recover a lost `agent.created` response only through a matching ownerless registration seed.
- Keep each distillation request on one Gateway node.
- Avoid blocking Gateway WebSocket receive on repeated session-tree scans.

## Corrected boundaries

| Boundary | Correction | Permanent coverage |
|---|---|---|
| Gateway registration | Existing non-NULL provenance is retained with its existing root; only NULL is seeded. | `test_gateway_im_registration.py` re-registers with a changed root and provenance and retains the first pair. |
| Node Agent create | IM accepts any non-blank root returned by the target Gateway; the create page forwards non-POSIX syntax. | HTTP and Vitest Windows-root regressions. |
| Lost response | A lock-serialized claim updates only an ownerless profile matching node/root/provenance and Gateway display name. | Real `node.register` seed then same-root/name retry; different root/name stays 409. |
| Distillation | List/sync exposes `source_node_id`; the selected node disables transcript paths from every other node. | HTTP projection and sidebar component regression. |
| Session lookup | Up to four local scans run in background tasks; receive can process a second resolve before the first scan finishes. | `test_gateway_session_log_resolution.py`. |

## Commands and results

```text
python -m pytest \
  tests/im_service/integration/test_users_conversations_api.py \
  tests/im_service/integration/test_gateway_im_registration.py \
  tests/im_service/contract/test_agent_create_immutability_contract.py \
  tests/unit/personal_assistant/test_gateway_session_log_resolution.py -q
17 passed, 7 warnings

python -m pytest \
  tests/unit/personal_assistant/test_gateway_session_log_resolution.py \
  tests/unit/personal_assistant/test_gateway_im_connection_behavior.py -q
29 passed, 2 warnings

npm run test -- --run agent-create-workspace.test.tsx conversation-sidebar.test.tsx chat-workspace.integration.test.tsx
69 passed (existing React act warnings retained)

npm run build
passed; existing Vite chunk-size warning only
```

## Isolated browser check and cleanup

- Started only this worktree's `e2e-up.sh` IM/Gateway stack and a Vite server on generated high ports.
- Logged in with the repository E2E account, opened the real Agent creation page, selected Custom path, and submitted `C:\\Gateway Data\\windows_ui_round2`.
- The request reached the target Gateway and displayed its target-side parent validation error; no client-side `pathAbsolute` rejection occurred.
- Stopped Vite and the E2E stack; confirmed both generated ports were no longer listening. No production service, configuration, or data was used.
