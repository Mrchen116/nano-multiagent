# M123 Gateway 默认启动与绑定反馈收口

## 前置确认
- 已阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`，后续注释/docstring 均遵守契约与意图分离规则。
- 本 Milestone 仅处理 `Gateway 默认启动 + IM 绑定反馈`，不扩散到 `src/IM/frontend/**`、docs、README 或其它产品。
- prevention_rules 已应用：
  - 默认用户路径不能要求用户理解隐藏 token/bootstrap 细节才能启动成功。
  - 启动失败或未绑定时，必须给出可执行下一步，而不是只留下异常栈。
  - 只修 Gateway/IM 默认启动与绑定反馈，不扩散到 docs 收口或前端入口路由。
  - 真实入口验证必须覆盖“节点出现在 IM / 绑定预期成立”的用户可见结果。

## 当前处境
- Milestone: `M123 / Gateway 默认启动与绑定反馈收口`
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M123`
- branch: `milestone/M123`
- 测试门禁命令: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant`
- 允许改动范围: `src/personal_assistant/**`、`src/IM/**`、`tests/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json(only via script)`
- 禁止改动范围: `src/IM/frontend/**`、`docs/**`、`README.md`、其它无关包/产品
- 基线结果:
  - 当前门禁在 sandbox 内 `56 passed / 7 failed`
  - 7 个失败均来自 `tests/e2e/test_m112_real_process_roundtrip_e2e.py` 的本地端口绑定：`socket.bind(("127.0.0.1", 0)) -> PermissionError: [Errno 1] Operation not permitted`
  - 该失败属于当前执行环境限制，不是 M123 目标缺陷；后续仍需对 M123 定向测试保持新增能力先红后绿

## Roadpoints

### R1 默认启动路径与 kernel 认证对齐
- Status: DONE
- Acceptance:
  - Gateway 默认启动路径与当前默认 `node-config.yaml` / managed kernel 约定一致，正常本地用户不会在首条路径上撞到 `missing API token for kernel client`
  - 默认配置或启动接线不再要求用户理解隐藏 token/bootstrap 细节
  - 启动失败时 CLI/日志会输出用户可执行的下一步，而不是只剩 Python 异常字符串
  - `tests/unit/personal_assistant` 与相关入口测试能覆盖默认启动配置/认证语义
- Tests Plan:
  - unit: 需要，验证默认 kernel 认证/配置推导与失败提示语义
  - contract: 不选，本 Roadpoint 不引入新的稳定协议面
  - integration: 需要，验证 gateway 入口到 kernel client 的真实装配语义
  - e2e: 需要，使用现有真实入口测试或最小入口测试证明默认启动不再断在 token 前置
- Expected Tests:
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_kernel_api_client.py`
  - `tests/unit/personal_assistant/test_main.py`
  - 视实现需要补充 `tests/e2e/test_personal_assistant_main_e2e.py` 或 `tests/e2e/test_m112_real_process_roundtrip_e2e.py` 中的定向用例
- DoD:
  - R1 定向测试先红后绿
  - 门禁命令在当前环境下除已知 sandbox 端口失败外无新增失败
  - 完成 C1/C2/C3
  - `PROGRESS` 写清默认启动与认证收口依据、证据、回滚点

### R2 节点可见性与未绑定反馈
- Status: TODO
- Acceptance:
  - Gateway 连接 IM 后，节点能以用户可理解的方式出现在 IM/绑定流程中，满足“默认启动后能看到节点或绑定入口”
  - 节点未绑定、绑定失败、IM bootstrap 不可达时，用户可见反馈包含明确下一步（例如去哪绑定、检查哪个地址/服务）
  - 节点上线状态与绑定预期可通过真实入口验证，而不是只靠内部 mock
  - 相关 acceptance/integration tests 覆盖“节点未出现 / 节点未绑定 / 绑定完成后节点归属成立”的用户可见结果
- Tests Plan:
  - unit: 需要，验证 bootstrap client 对未绑定/失败分支的反馈与可执行引导
  - contract: 不选，本 Roadpoint 主要收口行为与提示，不扩协议
  - integration: 需要，验证 IM websocket / bind / node list 链路反馈
  - e2e: 需要，覆盖真实入口下“节点出现在 IM / 绑定预期成立”的结果
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/im_service/integration/test_gateway_websocket_api.py`
  - `tests/acceptance/test_im_gateway_real_acceptance.py`
  - `tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- DoD:
  - R2 定向测试先红后绿
  - 门禁命令在当前环境下除已知 sandbox 端口失败外无新增失败
  - 完成 C1/C2/C3
  - `PROGRESS` 写清节点可见性/绑定反馈设计、证据、回滚点
