# bugfix-491: stale node owner 下恢复影子同步

## Relations

- Related: feat-447
- Related: bugfix-471
- Closes: #225

## 原始报告

Issue：https://github.com/Mrchen116/nano-multiagent/issues/225

> 飞书 inbound 主路径能正常回复用户，但内部 IM 看不到飞书交互。根因是 Gateway `config.node.user_id` 与 IM 鉴权用户不一致时，`IMShadowConversationSync` 在落库前硬失败，而飞书出站仍是 best-effort，形成静默双轨。

> `external_shadow_sagas.sqlite3` 中 pending saga 的 `owner_id` 被写成配置里的 stale 值（现网曾为 `demo-user`），与 `GET /im/v1/me` 返回的真实 UUID 不一致

> 飞书可回、IM 不可见，不符合「跨入口会话可理解」的产品预期

> 相关历史：`docs/changes/archive/feat-447-feishu-channel/M9-fix-gateway-live-run/progress.md` 已修过「participant 用 `/me` 而非 stale config」，但 **prepare 仍先用 config owner，并在 mismatch 时硬失败**，缺口仍在。

现网复现和临时处置见 issue 原文；当时通过把 mini `~/.nano-assistant/config.yaml` 的 `node.user_id` 改成 IM 真实用户 id，并清理 stale owner 的 pending saga 恢复。

## 澄清记录

- Q1: 当 `config.node.user_id` 与当前 IM 鉴权用户不一致时，产品是否应继续飞书回复，并以鉴权用户为准自动修复/重放影子同步（包括已落成 stale owner 的 pending saga），而不是让 Gateway 或飞书 channel 拒绝 ready？
  A(原话): 是。不要因为 `config.node.user_id` 过期而让 Gateway 拒绝 ready，也不要中断飞书回复；影子会话的 owner 以当前 `GET /im/v1/me` 的鉴权用户为准，同一真实 owner 下已经写成 stale owner 的 pending saga 也要纠正后继续重放，最终把飞书期间的用户消息和 Agent 回复补回内部 IM。跨真实 owner 的 node bind 门禁继续保留，不能把它和本地字段过期混成一类。此次不要求自动改写本机配置文件；运行时自愈并留下可诊断告警即可，是否顺手回写配置属于 design 取舍。
  Agent 解读: stale 本地字段不再充当影子会话 owner 真值；运行时以 IM 鉴权用户恢复当前和历史 pending 同步，同时保留真正跨 owner 的 node bind 安全门禁。外部回复优先、最终补齐影子历史和可诊断性三项都必须保住。

## 现象 / 复现

用户在飞书与 Agent 正常对话，Bot 能持续回复，但内部 Web IM 长期没有对应的 `agent名 · feishu` 影子会话，或影子会话缺少这段飞书期间的用户消息和 Agent 回复。Gateway 日志持续出现 `configured node owner differs from authenticated IM owner` 和 shadow recovery 重试错误；重试不会自行恢复。

触发条件是 Gateway 本机 `config.node.user_id` 仍是旧值，而当前 IM token 的 `GET /im/v1/me` 返回同一真实 owner 的有效用户 UUID。此时飞书出站不依赖 shadow sync 成功，形成“飞书能回、Web IM 永久不可见”的静默双轨。

稳定复现：

1. 让 Gateway 配置保留 stale `node.user_id`（现网曾为 `demo-user`），使用能从 `/im/v1/me` 得到真实 UUID 的有效 IM 鉴权。
2. 从飞书向该 Gateway 上的 Agent 发送消息。
3. 飞书中可看到 Agent 正常回复。
4. Web IM 中不出现或不更新对应影子会话；本地 shadow saga 以 stale owner 保持 pending，连接期恢复反复失败。

### Requirement: stale 本地 owner 不阻断外部对话和影子同步

#### Scenario: stale node.user_id 下飞书仍回复且 Web IM 最终可见

- **GIVEN** `config.node.user_id` 已过期，但 Gateway 当前 IM 鉴权仍属于该节点的真实 owner
- **WHEN** 用户在飞书向 Agent 发送消息并收到 Agent 回复
- **THEN** Gateway 不因本地 owner 字段过期而拒绝 ready 或中断飞书回复
- **AND** 对应用户消息和 Agent 回复最终出现在该鉴权用户的内部 IM 影子会话中

#### Scenario: 已写入 stale owner 的 pending saga 自动恢复

- **GIVEN** 同一真实 owner 的飞书消息已经以 stale 本地 owner 写成 pending saga，且用户消息或 Agent 回复尚未同步到 Web IM
- **WHEN** Gateway 能以当前有效 IM 鉴权重新执行 shadow recovery
- **THEN** 用户无需手工清理本地 saga 或修改配置，缺失的用户消息和 Agent 回复最终补入正确的影子会话
- **AND** 重放不产生重复影子会话或重复消息

#### Scenario: stale 字段被运行时自愈时留下可诊断信号

- **GIVEN** Gateway 发现本机 `node.user_id` 与 `/im/v1/me` 返回的鉴权用户不一致
- **WHEN** Gateway 继续运行并恢复影子同步
- **THEN** 运维者能从诊断信息看出本地 owner 字段已过期并发生运行时自愈
- **AND** 本期不要求系统自动改写本机配置文件

#### Scenario: 真正跨 owner 的节点绑定仍被拒绝

- **GIVEN** 当前操作属于真实的跨 owner node bind 或 owner transfer，而不是同一 owner 的本地字段过期
- **WHEN** 新 owner 尝试接管已有 owner 的节点和外部 channel
- **THEN** 系统继续按现有 node bind owner 门禁拒绝该操作，不把本次运行时自愈当作跨 owner 迁移入口

## 根因

### 直接原因

`composition.py` 把启动配置中的 `config.node.user_id` 传给 `IMShadowConversationSync`。`sync_user_message()` 为保证 IM 暂时离线时仍先持久化外部事件，会在请求 `/im/v1/me` 之前用该配置值调用 saga store `prepare()`；`owner_id` 同时进入 saga 主键和持久记录。

随后同步器从 `/im/v1/me` 得到当前鉴权用户。一旦 pending saga 的 `owner_id` 与鉴权用户不一致，代码直接抛出 `ValueError("configured node owner differs from authenticated IM owner")`。该异常被包装成 `ShadowSyncPendingError`，而恢复路径重放同一条 stale saga 时仍走相同 mismatch 分支，因此它不是暂时失败，而是永久 pending。

飞书消息处理按既有 best-effort 契约继续执行并发出 Agent 回复，所以错误没有使外部主路径失败，只让内部 IM 影子历史永久缺失。

### 原始设计意图与必须保住的不变量

这项能力最初由 `feat-447` 引入：

- 外部 channel 对话在内部 IM 形成独立影子会话，用户消息和 Agent 回复都可见；
- 飞书与 Web IM 影子入口共享外部会话上下文；
- IM 暂时不可达不阻塞飞书回复。

`feat-447/M9` 已专门修过 stale config：影子会话 participant 和用户消息 sender 必须使用 `GET /im/v1/me` 的当前鉴权用户，而不是 `config.node.user_id`。因此当前鉴权用户是 shadow owner 的产品真值，不应让同一真实 owner 下过期的本地字段覆盖它。

`bugfix-471/M2` 后续引入 durable external shadow saga，目标是在 IM 离线或 Gateway 重启后，按稳定外部事件身份补齐用户 anchor、Agent 输出和配置边界，同时仍让外部平台回复优先。修复本问题必须保住这套 crash-safe、幂等重放能力，不能通过删除 pending、跳过 shadow 或阻塞飞书回复来消除报错。

本次必须同时保持：

- 当前和恢复期 shadow owner 都以有效 IM 鉴权身份为准；
- 同一真实 owner 下已写成 stale owner 的 pending saga 能纠正并继续重放，既有用户消息和已持久化 Agent 输出不丢失；
- 重放保持幂等，不重复影子会话、用户消息、Agent 回复或边界；
- Gateway ready 与飞书回复不因 stale 本地字段被阻断；
- 真正跨 owner 的 node bind/transfer 仍按现有安全门禁拒绝；
- 运行时自愈留下可诊断告警，但本期不强制回写本机配置文件。

### 回归引入点

回归由 commit `a660cc942f5a8654ccd88b478f9033583ed885a3`（`feat(bugfix-471/M2/R2): 持久化边界投递与外部影子事务`）引入。该提交新增 durable saga，并把配置 owner 用作 IM 请求之前的持久身份；同时新增了配置 owner 与 `/me` 不一致时的硬失败。它覆盖了 `feat-447/M9` 已确立的“鉴权用户优先”语义。

### 为什么这种错能进入主线

- durable saga 的设计正确关注了“IM 离线前先保存外部 source fact”，但把“能在离线时取得的配置字段”误当成了最终 owner 真值，没有把离线持久化与联网后的身份校正分开。
- shadow sync 单测统一让构造参数 `owner_user_id="owner-a"` 与 `/im/v1/me` 返回 `owner-a`，覆盖了正常落库、离线 pending 和重启恢复，却没有覆盖 stale config mismatch 及已有 pending 的纠正重放。
- `feat-447` 的 live 验收曾通过手工把 worktree `node.user_id` 对齐临时 IM owner 后继续，证明了正常路径，但也让 stale 配置下必须运行时自愈的回归缺口没有成为长期门禁。

## 修复

`IMShadowConversationSync` 继续在请求 IM 前用本地 owner 建立 durable source fact，因而
IM 离线时不会丢失外部事件；但该值现在只作为离线期的暂存身份。IM 恢复后，同步器先从
`GET /im/v1/me` 得到 token 对应的 user/owner identity，再通过 owner-scoped
`GET /im/v1/nodes` 严格确认本 Gateway 的 `node_id` 确实绑定到该 owner。只有这项门禁通过，
stale saga 才能在一个 SQLite 事务中把 `owner_id` 校正为鉴权用户，并追加
`shadow_owner_recovered:<old>-><authenticated>` 诊断；未绑定节点或另一 owner 的 token
只能让 shadow 保持 pending，不能接管外部历史。

校正刻意保留原 `saga_id`：已持久化的 Agent output、pending configuration boundary 和 IM
caller idempotency key 都已引用该 identity。`prepare()` 也会先按不含可校正 owner 的稳定
provider event identity 查找已有 saga，保证运维者随后纠正 `config.node.user_id` 时，同一
事件仍复用原事务，而不是按新 owner 派生第二个 saga。恢复顺序仍是 user anchor → Agent
output → boundary，重复 recovery 不会重复写入。运行时告警在 owner 校正事务成功返回后才
记录，避免数据库失败时留下虚假的“已恢复”信号。

本次不修改 `config.yaml`，也不改变 Gateway WebSocket 注册和 IM node bind 规则；生产组合
仅把既有 `config.node.node_id` 传给 shadow sync，用现有 owner-scoped nodes API 复用同一条
durable owner 权限边界。

实现提交：`75397d424`（`fix(gateway): recover stale shadow saga owner`）、`2b40787e7`
（`fix(gateway): authorize shadow owner recovery`）。

## 验证

### Red / Green 与回归保护

- Red（修复前）：
  `pytest -q tests/unit/personal_assistant/test_gateway_im_relay.py` → `2 failed`；当前事件和
  restart recovery 都在 `configured node owner differs from authenticated IM owner` 处转成
  `ShadowSyncPendingError`。
- Green（修复后）：同一文件 → `2 passed`。测试覆盖 stale config 下当前消息、已有 stale
  pending saga、已持久 Agent final output、pending boundary promotion、durable diagnostic，
  并重复执行 recovery 证明不会重复 shadow 用户消息或 Agent 回复。
- 首轮独立 code review 后的定向回归：
  `pytest -q tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_gateway_shadow_sync.py tests/unit/personal_assistant/test_connection_ready_shadow_recovery.py tests/unit/personal_assistant/test_gateway_build_runtime.py`
  → `25 passed`。新增覆盖另一 owner token 和 ownerless node 均不能改写 pending saga，以及
  运维者纠正本地 owner 后重放同一 provider event 仍复用原 saga/anchor。
- 相关扩展：
  `pytest -q tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_gateway_shadow_sync.py tests/unit/personal_assistant/test_connection_ready_shadow_recovery.py tests/im_service/integration/test_gateway_auth_boundary.py::test_authenticated_wrong_owner_cannot_replace_bound_node_socket_or_key tests/im_service/integration/test_account_binding_api.py::test_bind_is_same_owner_idempotent_and_rejects_cross_owner_takeover`
  → `18 passed`。其中两条 IM 集成测试确认跨 owner node register/bind 门禁未被放宽。
- Gateway/IM 风险扩展：
  `pytest -qq --disable-warnings tests/unit/personal_assistant tests/im_service/integration/test_messages_api.py tests/im_service/integration/test_gateway_auth_boundary.py tests/im_service/integration/test_account_binding_api.py`
  → 退出码 0（`808 tests collected`）。
- 静态检查：
  `ruff check src/personal_assistant/gateway/composition.py src/personal_assistant/gateway/shadow_saga.py src/personal_assistant/gateway/shadow_sync.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_gateway_shadow_sync.py`
  → passed。
- 首轮独立 code review 找到并确认 3 项阻断问题：跨 owner token 可接管 stale saga、修正配置
  后 owner-dependent saga id 会分叉、恢复事务失败前可能先打印成功告警。修正后由独立 verifier
  仅对这 3 项做 closure，结论 `3/3 closed`；其定向测试为 `14 passed`。

### 隔离真栈

- Claim：stale owner 的 durable Feishu source fact 通过真实 IM HTTP 鉴权后，能补齐唯一影子
  会话中的用户消息和已持久 Agent 回复，同时提升原 saga 的 boundary，且二次恢复无重复。
- Baseline：`unit/bugfix-491`，`2b40787e7`；worktree
  `.worktrees/unit-bugfix-491`；`scripts/e2e-up.sh` 启动隔离 IM + Gateway，端口、数据库、
  node identity、config 和 workspace 均为本 unit 独占。
- Method：在真实栈存活时登录隔离 IM 用户，选择已注册 Agent；构造带
  `connector_account_id + provider_event_id` 的规范化 Feishu external event，先以
  `demo-user` 持久化 user saga、Agent final output 和 boundary callback，再让
  `IMShadowConversationSync.recover_pending()` 经真实 `/im/v1/me`、owner-scoped `/im/v1/nodes`、external
  find-or-create 与 message HTTP API 恢复两次；最后从用户侧 REST 列出 conversation 和
  timeline。
- Result：pass。owner 校正为真实鉴权 UUID；匹配影子会话恰好 1 个；timeline 中 user
  `bugfix-491 live user message` 和 Agent `bugfix-491 live agent reply` 各 1 条；pending saga
  与 pending output 都为 0；boundary promotion 为 1；durable diagnostic 为
  `shadow_owner_recovered:demo-user-><authenticated>`。验证后 `e2e-down.sh` 已停止进程并确认
  隔离 IM 端口释放。
- Limit：隔离 node 没有 static 或 managed Feishu credential，仓库也没有可稳定重放的
  Feishu/Lark fixture，因此没有连接第三方飞书 WebSocket 或向真实飞书账号发消息。证据覆盖
  本次根因所在的 external shadow adapter → durable SQLite → 真实 IM HTTP/DB 跨进程链路；
  Feishu SDK 收发和真实 LLM 回复继续由既有 channel tests/历史 live 验收约束，本轮不把它们
  冒充为已重新实测。

### Canonical spec 对账

No spec delta。本修复恢复 `docs/specs/gateway/relay-protocol.md` 已有的「Gateway 重启或 IM
恢复后按稳定事件身份补齐 user/Agent shadow mirror 且幂等」契约，以及
`docs/specs/gateway/external-channels.md` 已有的「飞书主路径不因 shadow sync 失败而阻塞、
飞书用户消息和回复最终出现在同一内部影子会话」契约；没有新增或改变长期对外行为。
