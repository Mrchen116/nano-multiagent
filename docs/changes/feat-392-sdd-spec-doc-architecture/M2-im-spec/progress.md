# feat-392-M2 — Progress

本 milestone 纯文档：建 IM 长青行为契约层 `docs/specs/im/spec.md`、退役旧 `docs/IM-SPEC.md`、修活引用。
照 M1 验证过的样板 `docs/specs/kernel/spec.md` 形态写，纯 `Purpose + Requirement/Scenario`（决策 4：无
`覆盖:` 行、无 `[可执行]`/`[行为]` 标签、无 freshness 测试，drift 靠收尾软对账）。WHEN/THEN 主语全为消费者
（浏览器前端 / Node Gateway / 终端用户 / contract 测试）。

## R1 — 契约层骨架 + 核心对外行为

- Context: 从可执行契约（最不 drift 的料源）逆向 IM 对外行为面的第一批：auth/token、Bearer 门禁 + owner
  隔离、会话/消息字段与分页、agent 配置中心 + 乐观锁、节点下创建 agent、agent↔users 行同步、policies。
- Decision: 写 Purpose（IM 定位 / 个人 owner 模型 / Actor 语义 / 显式不负责）+ 7 条 Requirement。
- Rationale: 料源优先级 ① `tests/im_service/contract` + `integration` + `unit` 可执行契约 → ② `src/IM/
  api/routes` 代码逆向 → ③ 旧 IM-SPEC 仅 checklist。每条 Requirement 对照测试断言重核，核不上即弃。
- Evidence:
  - Tests: 不新增测试（决策 4 软对账，契约层不出 freshness 红测）。逆向锚点测试本就全绿。
  - Entry: 对账（非"单测通过"）——逐条 Requirement 对照具体断言：
    - auth/token ← `unit/test_auth_service.py`（register/login/refresh 轮换/logout 吊销/401 不区分存在性）
      + `integration/test_auth_routes.py`
    - Bearer 门禁 + owner 隔离 404 ← `integration/test_routes_require_auth.py`（401 无 token、跨租 404、
      身份取 token 非 query、metrics owner-scope）
    - 会话/消息字段+分页 ← `contract/test_messages_contract.py`（delivery_status/sender_type/attachments/
      `{items,next_before_message_id}` 信封）+ `contract/test_chat_flow_contract.py`（未知会话 404 detail）
    - agent 配置+乐观锁+live 合并 ← `contract/test_agent_config_contract.py`（字段集、features/custom_prompt
      持久化、source=live 保留 IM 自有字段、409 冲突）
    - 节点下创建 agent ← `contract/test_agent_create_contract.py`（字段集、409 重复、404 未知节点）
    - agent↔users 行 ← 旧 IM-SPEC §7.5 + `integration/test_m18_agent_user_bootstrap.py`（user_id 恒非空）
    - policies ← `contract/test_settings_policies_contract.py`（字段集稳定、PATCH 回显）
  - Frontend State Matrix: N/A（不动前端）
  - Browser QA: N/A
  - E2E/Regression: N/A（决策 4 不绑测试）
  - Visual/Interaction: N/A
- Rollback: `git revert` R1 commit（纯新增文件）
- Commits: C2=见 git log `docs(feat-392/M2/R1)`（文档 milestone，内容即 R1，无独立红测 C1）

## R2 — WS 双面 + binding + 节点能力按需 + gateway 协议 + 状态广播 + relay 幂等 + 降级

- Context: 补 IM 对外行为面第二批，覆盖两条 WebSocket、设备绑定、节点能力按需解析、gateway 协议错误帧、
  节点状态广播、relay 幂等、IM 可选性/降级边界。
- Decision: 追加 8 条 Requirement。
- Rationale: 同 R1 料源优先级。**relay 幂等按 CDC 裁剪**：`enqueue_message_relay` 是内部应用层 API，不作
  Scenario 主语；改写为终端用户可观察的「重复 idempotency_key 不产生重复消息」+ Gateway 上行
  `node.delivery_receipt` 推进投递状态。旧 IM-SPEC 里**已废**的按会话 SSE（`GET .../events`）核代码不存在 → 弃，
  契约只写现行用户维 WS + `/sync`。
- Evidence:
  - Tests: 不新增（同 R1）。
  - Entry: 逐条对账：
    - 用户维 WS 鉴权+resume 回放+跨租不泄漏 ← `integration/test_user_stream_auth.py`（无/非法 token/仅
      user_id 被拒、合法 token resume 回放本租 message.sent/delivered）；`/sync` ← `contract/test_events_contract.py`
    - device binding ← `contract/test_account_binding_contract.py`（start 返回结构、缺字段 400 detail）
    - 节点能力按需+features 透传 ← `contract/test_agent_config_contract.py`（node/agent capabilities
      features 列表、网关无 features 时优雅降级空列表、五元字段）
    - gateway WS 协议错误帧 ← `contract/test_gateway_protocol_contract.py`（invalid_message /
      unsupported_message_type 信封）
    - 节点状态广播 ← `unit/test_gateway_status_broadcast.py`（register 广播 online 给本租）+
      `unit/test_offline_guard.py`（心跳超时翻 offline 广播 heartbeat_timeout、已 offline 幂等不重播）
    - relay 幂等 ← `unit/test_relay_service_task.py`（同 key 复用同 task、delivery receipt 推进 sent→completed）
    - IM 可选/降级 ← 旧 IM-SPEC §10/§11 + 硬约束（IM 离线外部 IM 主路径自治、中继关闭配置中心仍可用）；
      代码侧 `unit/test_offline_guard.py` 佐证心跳/降级路径存在
  - Frontend State Matrix / Browser QA / E2E / Visual: N/A
- Rollback: `git revert` R2 commit（同文件追加段）
- Commits: C2=见 git log `docs(feat-392/M2/R2)`

## R3 — 退役 docs/IM-SPEC.md + 修活引用

- Context: 旧 IM-SPEC 是混合高度（契约+架构+内部走查+已 rot 段，如按会话 SSE）。契约已迁入新层，退役之。
- Decision:
  - `git mv docs/IM-SPEC.md docs/archive/IM-SPEC.md`（与 M1 退役 `内核设计SPEC.md` 处置完全一致）。
  - `SPEC.md`：契约层索引 `im` 行改为生效态描述（去"建立"措辞、加 markdown 链接）；旧子系统 SPEC 表
    **移除 IM 行**；说明段加 "`IM-SPEC` 已随 feat-392-M2 退役（移入 docs/archive/，IM 契约改看
    docs/specs/im/spec.md）"。**只动 IM 自己的行**，gateway/cli 待退役行原样保留（M2/M3/M4 共享文件协调纪律）。
  - AGENTS.md 关键文档索引的 IM 契约层行 M1 已预置（指 docs/specs/im/spec.md），无需改。
  - 架构测试 `tests/contract/test_multi_product_architecture_acceptance.py` 经 grep 确认无 IM-SPEC 路径常量
    （只有结构注释行），无需改。
- Rationale: 决策 6/7：旧子系统 SPEC 已 rot，与新契约层并存=双重维护。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -m "not e2e"` → **2342 passed, 4 deselected**（退役未破坏任何测试）。
  - Entry: `grep -rn IM-SPEC` 确认无**活引用**残留指 `docs/IM-SPEC.md`；剩余命中全是历史 per-unit
    changes/acceptance/regression 快照（feat-340/333/379/383/362/390/336/349 等，与 M1 不动历史 TASKS/
    PROGRESS 同理，不动）。
  - 其余 N/A
- Rollback: `git revert` R3 commit 即恢复 `docs/IM-SPEC.md` 原位 + SPEC.md 引用
- Commits: C2=见 git log `docs(feat-392/M2/R3)`

## 范围边界发现（out-of-scope，已报 leader，未在本 milestone 改）

退役后 grep 发现 **src 源码注释 + 两份活文档** 仍带悬空文档锚 `IM-SPEC §N`（章节号）：
- `src/IM/infra/db.py`（3 处：§6/§6/§4）、`src/IM/ws/gateway_handler.py:1`（§4）
- `docs/operator-runbook.md:297`（§12）、`docs/IM前端蓝图.md:276`（§5）

判断：design.md M2「范围」列只含 `docs/specs/im/spec.md` + 退役 `docs/IM-SPEC.md`；派发包点名要更新的活引用
是 SPEC.md / AGENTS.md / 架构测试常量（均已处理/确认）。改 src 源码注释 + 这两份活文档**超出 M2 范围**，
且新契约层无 §编号、硬替章节锚对不上。按 §0.7 不顺手扩范围——记录于此并报 leader 决定（可作后续文档同步
项，不阻本 milestone；这些是注释文档锚，不影响任何运行时/测试）。
