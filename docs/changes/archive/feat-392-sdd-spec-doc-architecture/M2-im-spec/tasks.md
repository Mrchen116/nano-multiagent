# feat-392-M2: IM 行为契约层 — Tasks

> 对齐: ../design.md（决策 6/7：旧子系统 SPEC 退役，契约从 tests/contract + 代码逆向）

## 目标

新建 `docs/specs/im/spec.md`：打开它即可知道 IM 服务**现在**对外承担什么职责、消费者（浏览器前端 /
Node Gateway / 终端用户 / contract 测试）依赖哪些可观察行为。退役旧 `docs/IM-SPEC.md`（混合高度、含
已 rot 段），引用它的活文档改指新契约层 / 顶点 SPEC.md。

## 退出标准

- [x] `docs/specs/im/spec.md` 存在，照 `docs/specs/kernel/spec.md` 形态：`> 对齐:` 头 + Purpose +
      Requirements（纯 `Requirement`/`Scenario`，无 `覆盖:` 行、无 `[可执行]`/`[行为]` 标签）。
- [x] 每条 Scenario 的 WHEN/THEN 主语是消费者（前端 / Gateway / 终端用户 / contract 测试），不写 IM
      内部模块如何接线。
- [x] 契约覆盖 IM 对外行为面：auth/token、用户维 WS 上下行、HTTP 会话/消息、agent 配置中心、
      node binding、节点管理与按需 capabilities、多租 owner 隔离、gateway WS 协议（上下行 + 错误帧）、
      relay 幂等、policies、metrics、降级边界。
- [x] 每条 Requirement 拿 `tests/im_service/` 可执行契约 + `src/IM/` 代码重核（料源优先级 ① tests
      ② 代码 ③ 旧 SPEC 仅 checklist，核不上即弃）。废的按会话 SSE 已弃。
- [x] `docs/IM-SPEC.md` 经 `git mv` 退役至 `docs/archive/`（与 M1 退役内核 SPEC 一致）。
- [x] `SPEC.md` §6 IM 行更新（契约层索引 im 行改生效态 + 旧子系统表移除 IM 行 + 说明段标退役）；只动
      IM 自己那一行，gateway/cli 行原样保留。
- [x] `PYTHONPATH=src pytest -m "not e2e"` 全树绿：**2342 passed, 4 deselected**。

## 测试策略

- 被测行为（来自退出标准）：本 milestone 纯文档（契约层 + 退役 + 修引用），**不新增/不改运行时代码**。
  IM 对外行为的可执行契约已由 `tests/im_service/contract/` + `tests/im_service/integration/` 把守
  （auth 401、owner 隔离 404、消息字段、binding、policies、node capabilities、gateway WS 错误帧
  等），契约层只是把这些可观察行为**文档化**，按决策 4「软对账」不绑 `覆盖:` / 不出 freshness 红测。
- 已有测试在：`tests/im_service/{contract,integration,unit}/`（作逆向锚点，不改） / 新建：无。
- 落层/目录/marker：N/A（无新测试）。退役旧 SPEC + 改 SPEC.md 引用后，跑全树确认无测试引用 IM-SPEC.md
  路径（grep 已确认架构测试无 IM-SPEC 常量）。
- 可选依赖 importorskip：N/A。
- 本 milestone 产生的一次性验收证据：无（文档对账结论写 progress.md）。

前端 UI：N/A（本 milestone 不动前端）。

## Roadpoints

> 状态：R1 DONE / R2 DONE / R3 DONE。证据见 progress.md。

### R1 — 契约层骨架 + 核心对外行为（auth / 会话消息 / agent 配置 / 多租隔离）— DONE

- 步骤:
  - 从 `tests/im_service/contract/{test_account_binding,test_messages,test_chat_flow,test_agent_config,
    test_agent_create,test_settings_policies}.py` + `tests/im_service/integration/{test_routes_require_auth,
    test_auth_routes}.py` + `tests/im_service/unit/test_auth_service.py` 逆向，写 `docs/specs/im/spec.md`：
    `> 对齐: feat-392` 头 + Purpose（IM 定位 / 显式不负责）+ Requirements 第一批（auth/token、Bearer
    门禁与 owner 隔离、会话/消息字段与分页、agent 配置中心 + 版本乐观锁、节点下创建 agent、policies/metrics）。
- 验证: 逐条 Requirement 对照对应 contract/integration 测试断言 + `src/IM/api/routes/` 实际端点重核；
  WHEN/THEN 主语全为消费者。

### R2 — WS 双面 + binding + 节点能力按需 + relay 幂等 + 降级

- 步骤:
  - 补 Requirements 第二批：用户维 WS `/im/ws/user`（token 鉴权、resume 回放、跨租不泄漏）、
    `GET /im/v1/sync` 游标对齐、device binding 流程、节点管理与**按需**向在线网关拉取 capabilities
    （不入库快照）、gateway WS `/im/ws/gateway` 上下行协议 + 错误帧、relay 幂等、IM 离线/中继关闭降级边界。
  - 料源：`tests/im_service/contract/{test_events,test_gateway_protocol}.py` +
    `tests/im_service/integration/{test_user_stream_auth,test_gateway_im_*}.py` +
    `tests/im_service/unit/{test_relay_service_*,test_offline_guard,test_gateway_status_broadcast}.py`
    + `src/IM/ws/`。
- 验证: 逐条对照测试 + 代码；旧 IM-SPEC §4/§10/§11 条目核不上即弃（如已废的按会话 SSE 不写）。

### R3 — 退役旧 IM-SPEC.md + 修引用

- 步骤:
  - `git mv docs/IM-SPEC.md docs/archive/IM-SPEC.md`（与 M1 退役内核 SPEC 一致）。
  - 更新 `SPEC.md` §6 旧子系统 SPEC 表「IM 服务 SPEC」那一行；只动 IM 这一行。
  - grep 全仓确认无**活文档**仍指 `docs/IM-SPEC.md`（历史 TASKS/PROGRESS 快照不动）。
- 验证: `pytest -m "not e2e"` 全树绿；grep `IM-SPEC` 仅剩历史归档与 archive 自身。
