# bugfix-383 — 回归验证

> 对齐: incident.md

## Verdict

**pass**

---

## 复现验证

### 原始 bug 描述

incident.md 记录：用户在 Web IM 会话里 agent 跑长 tool 循环（multi-turn tool calls 持续 > 2 分钟）时，消息被错误标 failed，正文末尾出现 `[error] relay timed out after 300s with no completion event`，但 agent 实际后台仍在工作。

根因：`relay_watchdog.py` 以 `messages.created_at` 判超时，仅看消息创建时间，不考虑中间是否有活跃 event 推进。

### 修复后验证路径

#### V1：单元测试（最小化验证核心逻辑）

环境：`worktree unit-bugfix-383` + `.venv`

```
pytest tests/im_service/unit/test_relay_watchdog.py -v
```

结果：**12/12 PASS**，新增用例覆盖：
- `test_active_relay_not_killed` — message 创建 10 分钟前、event 30 秒前刚推进 → 不杀（pass）
- `test_idle_relay_killed_with_new_wording` — message 创建 10 分钟前、last event 5 分钟前 → 被杀，content 含新文案 `relay idle for 120s with no new event`（pass）
- `test_no_event_fallback_to_created_at` — message 4 分钟前创建、零 event → fallback 按 created_at，被杀（pass）
- `test_boundary_just_over_idle_threshold` — last event 121s 前 → 被杀（pass）
- `test_boundary_just_under_idle_threshold` — last event 119s 前 → 不杀（pass）
- 原有 7 个测试全部 PASS，无回归

#### V2：env override 验证（退出标准 d）

起 IM 服务并设 `IM_RELAY_WATCHDOG_TIMEOUT_SECONDS=60`：

```
IM_JWT_SECRET=... IM_RELAY_WATCHDOG_TIMEOUT_SECONDS=60 \
PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 59041
```

在 DB 中插入一条 `running` 消息（created_at 65s 前，无任何 conversation_events），等待 watchdog 扫描（30s interval）：

**结果：**
```
relay_watchdog: reaped stuck message 9c8c7c2a... in conversation 44fac61b... (age > 60s)
```
消息状态从 `running` → `failed`，content 末尾追加：
```
[error] relay idle for 60s with no new event
```
**env override 生效，文案已更新为新版本。**

#### V3：活跃 relay 不被误杀（bug 核心路径）

同一 IM 实例（60s override），插入 message（created_at 10 分钟前），并插入 conversation_events（最新 event 30s 前）：

模拟 2 次 watchdog 扫描（每次扫描前推入新 event，模拟"活跃推进"场景）：

**结果：**
- 推进后扫描 #1：message 状态 = `running`（未被杀）
- 推进后扫描 #2：message 状态 = `running`（未被杀）

随后停止推进 event，将所有 event created_at 回拨到 70s 前，等下次 watchdog 扫描：

**结果：** message 状态 → `failed`，content：
```
[error] relay idle for 60s with no new event
```
即：真正 idle（event 停止推进超过阈值）才被杀，活跃推进不被误杀。**核心 bug 路径修复确认。**

#### V4：e2e 完整栈验证（退出标准 c）

使用 `scripts/e2e-up.sh` 启动完整栈（IM + Kernel API + Gateway）：
```
IM  port=59917, API port=59918, Gateway wt-unit-bugfix-383-39872
```

登录 nano 账号，在 Web IM 中创建包含 `default-agent` 参与者的会话，发送触发 bash tool 调用的消息：

```
请用 bash 工具运行以下命令序列：1) pwd 2) ls 3) echo '...' 4) date 然后告诉我结果。
```

**结果：**
- Gateway 接收消息，dispatch 到 agent
- agent 执行 tool 调用后返回结果
- 消息状态 = `completed`
- UI 展示（Playwright 截图）：消息气泡完整显示命令执行结果，底部显示 `1 tool call · 19ms · 307 tok · ctx 2%`
- **无任何 `[error]` 文字，无 `relay timed out`，无 `relay idle` 误杀文案**

截图证据：`/tmp/webim-chat-open.png`（保存于 reviewer 本地，非提交产物）

---

## 回归测试

### IM 单元测试套件

```
pytest tests/im_service --ignore=tests/im_service/integration -v
```
结果：**155/155 PASS**，无回归。

（注：integration 测试因 worktree 内 `pyyaml` 未包含在 `pyproject.toml` 依赖中导致 import error，系 pre-existing 问题，与本次 bugfix 无关。）

### 关键回归覆盖

- bugfix-365 行为保留：失败消息 content backfill、agent identity 恢复逻辑均未受影响（原有测试 `test_scan_inherits_prior_relay_processing_payload_for_id_continuity`、`test_scan_writes_detail_into_empty_message_content`、`test_scan_appends_error_note_to_partial_streamed_content`、`test_scan_recovers_agent_identity_when_relay_processing_missing` 全部 PASS）
- watchdog 扫描周期（30s interval）不变，正常 relay 完整流程无影响

---

## 自动化测试增量

新增 5 个单元测试（`tests/im_service/unit/test_relay_watchdog.py`）：

| 测试名 | 覆盖场景 | 防止回归 |
|---|---|---|
| `test_active_relay_not_killed` | 活跃推进（last_evt < threshold）不被杀 | 防误杀回归 |
| `test_idle_relay_killed_with_new_wording` | 真 idle 被杀 + 新文案 | 防文案退化 |
| `test_no_event_fallback_to_created_at` | 零 event fallback 到 created_at | 防 COALESCE fallback 失效 |
| `test_boundary_just_over_idle_threshold` | last_evt 121s 前 → 被杀 | 边界正确性 |
| `test_boundary_just_under_idle_threshold` | last_evt 119s 前 → 不杀 | 边界正确性 |

---

## 上层文档同步

- [x] `SPEC.md`：无需更新（watchdog 为 IM 内部实现细节，不在架构总览层）
- [x] `docs/内核设计SPEC.md`：无需更新（本次改动限于 IM 包）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新（操作手册无需反映 watchdog 阈值变化）
- [x] 相关产品 SPEC（`docs/IM-SPEC.md`）：无需更新（SPEC 无记录 watchdog 超时参数；如需添加，属后续文档改善项，不阻本次验收）

---

## Side Findings

- 前端 TypeScript 构建（`npm run build` via tsc）报类型错误：`tests/im_service/unit/... message-pane.test.tsx` 中 Message 类型缺少 `permission_requests` 字段（pre-existing，与本次 bugfix 无关）。Vite 直接构建（`npx vite build`）可绕过，产物正常。
- integration 测试 `test_group_chat_flow.py` 等 7 个文件有 `ModuleNotFoundError: No module named 'yaml'`（worktree 内 `pyyaml` 未在 dev extras 中列出，pre-existing 问题）。

以上均为 pre-existing，不影响本 unit 验收结论。
