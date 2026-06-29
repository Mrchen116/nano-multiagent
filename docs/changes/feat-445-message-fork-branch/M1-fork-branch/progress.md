# feat-445-M1 — Progress

## Decision: 决策1 实现路径取轻法 (b)，非 CC 式 raw-clone (a)

- Context: design.md v2.5 决策1 写「CC 式 raw-clone」（复制源 JSONL 原始条目含 compact_boundary/summary、re-stamp UUID 及内部引用、截断到 M、新 session boundary-aware load 派生视图）；design.md:110 同时显式注明等价轻法 (b)（对源 raw 前缀 [0..M] 做 boundary-aware materialize 得 as-of-M 的 Message 列表 → 交现成已测的 `_fork_locked` 写新 session，完全避开 boundary/summary 内部引用 re-stamp）。design-review.md 留 1 条非阻断 WARNING 推荐 (b)。orchestrator 指示由 worker 在 design 自承等价的两法里知情取舍。
- Decision: **取轻法 (b)**。
- Rationale:
  1. 两法模型行为完全相同（design 自承、review 复核确认），都满足 spec「分支≡源在 M 体验一致」——差别只在最后一步实现与风险。
  2. §0.1（复用/扩展现有架构，别新写平行物）：(b) 复用现有 `store.load` boundary-aware materialize（只加 `up_to` 截断参数）+ 现成已测 `runtime._fork_locked`（Message 侧 re-stamp）。(a) 经第一手核对**无法复用 `_fork_locked`**（它遍历 materialized Message、看不到也无法 re-stamp compact_boundary 标记），是一条**新增 raw-entry 克隆路径**，与 design「可复用能力段」自承的「整体复用 _fork_locked」自相矛盾。
  3. (a) 必须正确一致 re-stamp `compact_boundary.summary_uuid` / summary turn `uuid`/`parent_uuid=first_kept_event_id`（design 自标的「头号易错点①」），且与 compact 条目 schema 长期耦合；换来的 kernel-side scrollback 在 nano **无消费者**——kernel JSONL 不是展示面（展示由 IM 展示副本承担，决策3），compact 后 `store.load:224` 永久跳过 boundary 前 turn，克隆进分支是 write-only 死重。无任何 nano 端现在/近期特性消费它。
  4. **关键正确性论证（为何 (b) 的 as-of-M 视图精确等于源在 M 的视图）**：当 agent 产出消息 M 时，源 JSONL 文件状态 = [0..M]。`store.load` 对 [0..M] 前缀的 boundary-aware materialize = 源当时（产出 M 之后那一 turn）实际加载的工作上下文。轻法 (b) 用 `up_to=M` 截断 raw_lines 到 M 行（含）后跑**同一段** store.load 逻辑 = 复现源在 M 的历史文件状态 → 视图逐字一致。无需任何新「无损读」语义。
- Grounding（第一手核对，非二手）:
  - `store.load` boundary-skip: jsonl_store.py:198-231（有 boundary 只留其后 turn + summary；无 boundary 取全部 turn）。
  - `_fork_locked` 操作 materialized Message、`replace()` 保 reasoning/工具: runtime.py:1312-1385。
  - **linchpin 确认**：relay 事件 `message_id`（realtime_stream.py:54）= loop 的 `assistant_msg_id`（loop.py:407 → message_end 事件 message_id loop.py:653）= 持久化 JSONL turn 的 `uuid`（runtime.py `_message_to_entry`:2251 `"uuid": msg.message_id`）。三处同一 id → fork `up_to=message_id` 按 turn uuid 截断精确落在 IM 气泡所标的那条 assistant 消息。
  - relay 多气泡 roll: 每 IM 气泡 ↔ 一个 kernel message_id，`_roll_bubble`（main.py:3218）切换；`message_completed`（turn_end main.py:3700 / roll main.py:3252）是每气泡恰一次的终结点，token_usage 即在此持久化（precedent）。
  - 无生产调用方依赖现有 `runtime.fork_session` 签名（grep 全 src 仅 kernel stub 与测试）；现有 5 个 test_fork_session.py 用例全走 `up_to=None` 路径，保留 cache-first 不破。
- Impact: 仅本 milestone 实现路径；design 决策1 的「等价轻法 (b)」分支被选中，不改 design 任何决策方向（design 已框定两法等价）。可复用能力段措辞按 review Recommendation 已如实（(b) 即「整体复用 _fork_locked + store.load，只加截断」，与 design:49-50 一致）。

---
<!-- 每个 roadpoint 完成后实时追加 -->
