# M123 Gateway 默认启动与绑定反馈收口

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 注释规范承诺：新增 public module/class/function/method 使用 Google 风格 docstring；注释只解释意图、边界、代价。
- 当前处境：M123，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M123`，branch=`milestone/M123`。
- 测试门禁：`PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant`。
- 基线结果：
  - 当前环境首轮结果为 `56 passed / 7 failed`
  - 失败全部来自 `tests/e2e/test_m112_real_process_roundtrip_e2e.py` 的 `_pick_free_port()`，错误为 `PermissionError: [Errno 1] Operation not permitted`
  - 判断：这是 sandbox 禁止本地端口绑定的环境限制，不是 M123 scope 内业务失败；后续以 M123 定向测试的红绿变化为主
- 关键排查线索：
  - `/Users/czj/Repos/nano-multiagent/node-config.yaml` 默认 `node.node_id=my-macbook`、`im_service.url=http://127.0.0.1:8021`
  - `ACCEPTANCE/M120-acceptance.md` 记录真实失败为 `ERROR node my-macbook did not appear in IM bootstrap` 与 `ValueError: missing API token for kernel client`
  - 当前代码里 `_IMBootstrapClient.ensure_node_binding()` 只会在节点不可见时抛 `RuntimeError("node ... did not appear in IM bootstrap")`，`KernelApiClient` 在 require_auth=True 且 token 为空时直接抛 `ValueError("missing API token for kernel client")`

### R1 默认启动路径与 kernel 认证对齐
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 先补 Red 测试，锁定“默认本地启动不应要求隐藏 token”与“失败提示需给出下一步”。

### R2 节点可见性与未绑定反馈
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 在 R1 收口启动路径后，补节点未出现/未绑定/绑定完成的反馈与真实入口验证。
