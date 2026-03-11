# M96 - IM Agent 配置 + 用户/设备绑定

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

- Milestone: M96 / IM Agent 配置 + 用户/设备绑定
- Branch: `milestone/M96`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M96`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M96 && PYTHONPATH=src pytest -q tests/im_service`
- Prevention Rules:
  1. 先跑真实基线测试，再开始编码。
  2. 大范围编辑后回查负向断言与 import path，避免留下并行结构。
  3. 保持唯一 canonical 结构；兼容层如存在必须最小且有理由。
  4. TASKS/PROGRESS 明确记录已先阅读 SPEC 与相关模块 SPEC。

## R1 Agent 配置 API 与 profile_version 乐观锁
- Status: TODO
- Acceptance:
  - 新增 `GET /im/v1/agents`。
  - 新增 `GET /im/v1/agents/{id}/config`。
  - 新增 `PATCH /im/v1/agents/{id}/config`。
  - PATCH 需要 `profile_version`，冲突时返回稳定错误语义。
  - 仓储/服务/API 保持 canonical 分层。
- Tests Plan:
  - unit: repository roundtrip 与冲突检测。
  - integration: 真实 HTTP API 验证 list/get/patch 和 409 冲突。
  - contract: 返回结构与错误语义契约。
- Expected Tests:
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/contract/test_agent_config_contract.py`
- DoD:
  - `test_command` 全绿。
  - PROGRESS 记录 profile_version 语义、证据与提交哈希。

## R2 GET/PATCH /im/v1/me 与 POST /im/v1/bind
- Status: TODO
- Acceptance:
  - 新增 `GET /im/v1/me` 当前用户信息与 owned nodes。
  - 新增 `PATCH /im/v1/me` 更新用户设置。
  - 新增 `POST /im/v1/bind` 设备绑定流程，支持生成链接与确认绑定。
  - 绑定后节点 owner 与节点上的 agent owner 自动归属当前用户。
- Tests Plan:
  - unit: repository/service 绑定流程与用户更新。
  - integration: 真实 HTTP API 验证 me roundtrip 与 bind start/confirm。
  - contract: bind payload/result 语义与错误场景。
- Expected Tests:
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/integration/test_account_binding_api.py`
  - `tests/im_service/contract/test_account_binding_contract.py`
- DoD:
  - `test_command` 全绿。
  - PROGRESS 写明绑定状态流转与 owner 回填规则。

## R3 配置仅对新会话生效 + 收口复查
- Status: TODO
- Acceptance:
  - 持久化会话可记录创建时采用的 `profile_version` 快照。
  - 配置更新不会回写已有会话快照，只影响后续新建会话。
  - 复查 IM canonical 结构与 import path，无无理由并行实现。
- Tests Plan:
  - unit: conversation create snapshot 语义。
  - integration: 先创建会话、再改配置、再创建新会话，验证旧新会话版本不同。
  - full: 跑完整 `tests/im_service`。
- Expected Tests:
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/**/*`
- DoD:
  - `test_command` 全绿。
  - PROGRESS 写清新会话生效证据、负向复查结果与回滚点。
