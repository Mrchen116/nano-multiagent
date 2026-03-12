# M118 NodeGateway 默认启动体验优化

## 目标
把 Node Gateway 默认用户路径收口为“启动即后台常驻 + 内核默认内聚 + 未绑定自动浏览器引导绑定 + 绑定后直接进入 Web IM 聊天”，消除用户手工管理 kernel 与手调绑定 API 的体验断点。

## Exit Criteria
1. 默认启动命令成功后尽快返回，Gateway 在后台常驻；只有显式 debug/foreground 模式才前台阻塞。
2. 默认配置不要求用户填写 `kernel.command` / `kernel.base_url`；Gateway 内部默认内核入口真实可用。
3. 未绑定节点在连接 IM 后会自动打开浏览器进入登录/绑定流程，而不是要求用户手动调用 curl/API。
4. 绑定完成后用户可直接进入 Web IM 并发送消息，默认聊天链路会选择已绑定节点。
5. 相关 Python / 前端自动化测试与真实入口验证通过，且不修改 `ROADMAP.md` / 不手改 `data/dev-tasks.json`。

## Roadpoints

### R1 默认后台启动与前台模式分流
- **Acceptance**:
  1. `python -m personal_assistant.main --config ...` 默认走后台启动，不长期占用当前终端。
  2. 默认启动会等待到 Gateway ready 或明确失败，再向用户返回退出码与必要信息。
  3. 显式 `--foreground`（或等价 debug 模式）保留现有前台常驻行为，便于调试与 smoke。
  4. 后台启动不会破坏现有 graceful shutdown / smoke / runtime 生命周期测试语义。
  5. 默认启动的输出包含可用于后续排障的最小信息（如 pid / health url / log 路径或等价信息）。
- **Tests Plan**:
  - unit: 需要；覆盖 CLI 参数分流、后台子进程参数拼装、ready 等待/失败语义。
  - contract: 不单独新增；入口契约主要由 CLI 行为与既有 `main` contract 测试覆盖。
  - integration: 需要；覆盖后台父进程快速返回且子进程仍存活的入口路径。
  - e2e: 需要；保留/更新真实 smoke 与真实命令入口验证，证明 foreground 仅在显式模式下发生。
- **Expected Tests**:
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/e2e/test_personal_assistant_main_e2e.py`
- **DoD**: 相关 `main` / e2e 套件全绿 + C1/C2/C3 齐全 + `PROGRESS` 写清后台化取舍、证据与回滚点。
- **Status**: TODO

### R2 内核默认内聚与未绑定自动浏览器绑定
- **Acceptance**:
  1. 用户最小配置可省略 `kernel.command`，Gateway 使用内部默认内核入口成功启动。
  2. Gateway 连接 IM 后，能判断当前节点是否已绑定；未绑定时自动发起 bind request 并打开浏览器到 `bind_url`。
  3. 已绑定节点不会重复拉起浏览器；IM 离线或无 IM 配置时不误触发绑定引导。
  4. 绑定引导逻辑收口在 Gateway/IM 边界，不把 curl/API 步骤暴露为默认用户路径。
  5. 相关 IM contract / integration / runtime 测试证明 bind URL 与节点归属判断稳定可用。
- **Tests Plan**:
  - unit: 需要；覆盖默认 `kernel.command`、IM bootstrap 查询、未绑定判定、浏览器打开触发与幂等。
  - contract: 需要；补 bind URL / 节点 owner 判定相关 API 契约，避免前后端口径漂移。
  - integration: 需要；覆盖 IM HTTP bind 流与 Gateway IM bootstrap 的协同。
  - e2e: 需要；保留真实进程级注册/绑定联调，并增加“未绑定自动引导”真实入口验证。
- **Expected Tests**:
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/im_service/contract/test_account_binding_contract.py`
  - `tests/im_service/integration/test_account_binding_api.py`
  - `tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- **DoD**: 相关 Gateway + IM 测试全绿 + C1/C2/C3 齐全 + `PROGRESS` 写清 bind 触发边界、浏览器策略与回滚点。
- **Status**: TODO

### R3 Web IM 绑定页与绑定后直聊闭环
- **Acceptance**:
  1. 浏览器打开 bind URL 后有真实可操作的登录/绑定页面，不再停留在占位链接或手工 API。
  2. 绑定完成后页面可直接进入 `/chat`，并让聊天默认使用刚完成绑定的节点。
  3. `/chat` 在未绑定场景会给出清晰状态或引导，不会静默发送到空目标节点。
  4. 绑定完成后的真实聊天链路可在 Web IM 中直接发消息并收到 agent 回复。
  5. 前端改动仅限绑定引导 / chat 直聊闭环，不扩散到无关设置页重构。
- **Tests Plan**:
  - unit: 需要；覆盖前端 bind/query 解析、chat bootstrap 节点选择、未绑定引导分支。
  - contract: 不单独新增；沿用 IM bind/account API 契约，前端只消费既有接口。
  - integration: 需要；覆盖前端路由与真实 IM 模式下的 bind→chat 流转。
  - e2e: 需要；做真实入口验证，证明“浏览器绑定完成后直接在 Web IM 聊天”。
- **Expected Tests**:
  - `src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/app/router.test.tsx`
  - `tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- **DoD**: Python/前端门禁全绿 + 必要真实入口验证完成 + C1/C2/C3 齐全 + `PROGRESS` 写清路由/用户态选择/证据与回滚点。
- **Status**: TODO
