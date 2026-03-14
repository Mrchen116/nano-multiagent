# M174 - 修复 canonical runtime 节点绑定未完成导致直聊无回复

## Summary
- 定位到 fresh canonical runtime 仍卡在 `ACTION node ... is waiting for IM binding` 的根因，不在 websocket 注册或 bind token 生成，而在 `/im/v1/bind` API 把 `bind_url` 固定生成为 `http://127.0.0.1:8011/bind/confirm?...`。
- canonical startup path 实际先连接的是当前 IM host；gateway 打开固定 8011 链接后，浏览器可能落到错误 host，导致用户即使看到 bind 页面入口，确认动作也没有命中当前 runtime 对应的 IM 服务，因此节点 `owner_id` 迟迟不落库，后续直聊仍不会路由到该 node。
- 修复后，`/im/v1/bind` 响应会把持久化的 bind path/query 重新绑定到当前请求 host/scheme，保证 gateway startup path 打开的链接与实际运行中的 IM 服务一致。

## Evidence
- 旧实现证据：`/Users/czj/Repos/nano-multiagent/.worktrees/M174/src/IM/api/deps.py` 仍将 `bind_base_url` 默认写死为 `http://127.0.0.1:8011/bind/confirm`，`BindRepository.create_bind_request()` 也直接持久化该绝对 URL。
- 断点证据：`/Users/czj/Repos/nano-multiagent/.worktrees/M174/src/personal_assistant/main.py` 的 `_IMBootstrapClient.ensure_node_binding()` 会直接打开 `/im/v1/bind` 返回的 `bind_url`；如果这个 URL 指向错误 host，startup path 就永远停留在 waiting-for-binding。
- 修复点：`/Users/czj/Repos/nano-multiagent/.worktrees/M174/src/IM/api/routes/account.py`
  - 新增 `_resolve_bind_url()`，保留原 `path/query/fragment`，但把 `scheme/netloc` 改为当前请求的 IM host。
  - `POST /im/v1/bind` 的 start/confirm 响应现在都走 `to_bind_response(bind, request=request)`，因此 runtime 无论经由 `testserver`、`127.0.0.1:<port>` 还是 canonical host 访问，都能拿到当前 host 上可完成确认的 bind URL。
- 回归更新：
  - `tests/im_service/integration/test_account_binding_api.py` 现在断言 bind URL 指向当前 `TestClient` host，而不是写死 8011。
  - `tests/acceptance/test_im_gateway_real_acceptance.py` 同步断言 acceptance harness 返回当前 host bind URL。
  - `tests/e2e/test_m112_real_process_roundtrip_e2e.py` 同步断言真实 runtime bootstrap 打开的 URL 等于 `im_base` 上的 `/bind/confirm?...`，直接覆盖 canonical runtime startup path。

## Why it previously failed
- 绑定状态真正建立依赖的是：gateway 注册 node -> `/im/v1/bind` 生成 token -> 浏览器打开 bind confirm 页 -> 用户确认 -> `/im/v1/bind` confirm 把 `nodes.owner_id`、`agent_profiles.owner_id`、`users.default_entry_node_id` 一起写回 IM。
- 之前的失败点在第 2/3 步之间：token 虽然生成成功，但返回给 gateway/browser 的 URL host 不一定等于当前运行中的 IM 服务 host。这样确认动作会打到错误入口，导致第 4 步没有发生，IM 看见的 node 一直 owner 为空，于是 gateway 持续报告 `waiting for IM binding`，直聊消息也不会被稳定路由到该节点产生回复。

## Tests
- `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/unit/personal_assistant/test_main.py -k "im_bootstrap_client or build_runtime_defaults_local_kernel_token_when_config_omits_it" -q` -> `4 passed, 23 deselected`
- `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/im_service/integration/test_account_binding_api.py -q` -> `2 passed`
- `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/im_service/integration/test_account_binding_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/acceptance/test_im_gateway_real_acceptance.py /Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/unit/personal_assistant/test_main.py -k "bind or im_bootstrap_client" -q` -> `6 passed, 25 deselected`

## Files changed
- `/Users/czj/Repos/nano-multiagent/.worktrees/M174/src/IM/api/routes/account.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/im_service/integration/test_account_binding_api.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/acceptance/test_im_gateway_real_acceptance.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M174/tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M174/TASKS/M174-修复-canonical-runtime-节点绑定未完成导致直聊无回复.md`

## Commit
- Pending

## Merge readiness
- Code and focused regression coverage are in place.
- Final commit hash still pending, so merge readiness is not final until commit is created.
