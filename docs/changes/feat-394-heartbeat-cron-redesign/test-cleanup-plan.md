# feat-394 测试套件审计 — 逐文件处置清单

对照 `docs/TESTING_GUIDE.md` 逐文件审查 PR #78 全部新增/变更测试文件，产出保留/改名/合并/拆分/删除建议。

审查维度：
1. **命名违规**：文件/函数名含 milestone 流水号（`test_m9*`、`M9-E:`、`R11-3:` 等）
2. **行数超限**：单文件 > 400 行（软上限）
3. **落层错误**：目录与被测范围不匹配
4. **重叠/冗余**：多文件测同一行为
5. **一次性验收证据混入**："半年后还该跑吗？"答案为否的

---

## 一、前端 TypeScript 测试（vitest）

### `agent-detail-page.test.tsx` — **改名 + 拆分**

| 属性 | 现状 |
|---|---|
| 行数 | 1041 行（超 400 软上限 2.5 倍） |
| 命名 | describe/it 中含大量 milestone 编号（`feat-379-M3`、`feat-394-M9-E:`、`R7-4:`、`R9-2:`、`R11-3:`、`R11-4:`、`feat-383-M1:`） |
| 落层 | 正确（frontend 单元/集成层） |

**处置**：
- 拆成两个文件（均在同目录）：
  - `agent-detail-page.test.tsx`：保留「agent detail page」describe + 现有通用行为测试（chat 按钮、identity、skills/tools pill）
  - `agent-behavior-card.test.tsx`：承接「Behavior card」/ features 控制 / tool_allowlist 默认模式 / cron+heartbeat UX 等所有 `describe("feat-*")` 块
- 改名：去掉所有 `it()`/`describe()` 里的 milestone 流水号前缀，改为行为描述，例：
  - `"feat-394-M9-E: Heartbeat card 显示并可开关"` → `"heartbeat card 在 features.heartbeat 启用时显示并可开关"`
  - `"R11-3: Skills / Tool allowlists render as pill toggles"` → `"Skills / Tool allowlists render as pill toggles"`

### `agent-m9c-features-panel.test.tsx` — **改名**

| 属性 | 现状 |
|---|---|
| 行数 | 442 行（略超 400，可接受） |
| 命名 | 文件名含 `m9c`（milestone 编号）；所有 `describe()` 名称均含 `M9-C:` / `M11:` 前缀 |
| 落层 | 正确 |
| 内容 | 独立测 features panel 和 HeartbeatCard 行为，与 agent-detail-page.test.tsx 无重叠 |

**处置**：
- **改文件名** → `agent-features-panel.test.tsx`
- 去掉 describe 名称里的 `M9-C:` / `M11:` 前缀，例：
  - `"M9-C: heartbeat controlled by Features list"` → `"heartbeat controlled by Features list"`
  - `"M11: cadence input binds to config value, no hardcoded 30m fallback"` → `"cadence input binds to backend value"`

### `im-agent-config-api.test.ts` — **保留，改名内部注释**

| 属性 | 现状 |
|---|---|
| 行数 | 78 行 |
| 命名 | 文件名合法；describe 名含 `feat-394 round-trip` 和版本描述，可接受 |
| 内容 | 专测 `normalizeAgentConfigResponse` heartbeat_json 解析逻辑，独立关注点 |

**处置**：保留。顶层注释引用的 `feat-394 M9-E` 可改为行为描述，但优先级低。

---

## 二、Python unit 测试

### `tests/unit/personal_assistant/test_cron_awareness.py` — **拆分**

| 属性 | 现状 |
|---|---|
| 行数 | 525 行（超 400） |
| 命名 | 文件名合法（行为描述）；内部函数名合法 |
| 内容 | 测 CronRunner 的 3 个独立关注点：① isolated session 提交机制，② System(untrusted) awareness 注入，③ M6 shim 接口契约 |

**处置**：
- 拆成两个文件（均 < 300 行）：
  - `test_cron_awareness.py`：保留 awareness 注入相关测试（`test_cron_runner_awareness_*`、`test_awareness_*`）
  - `test_cron_runner_session.py`：承接 isolated session 提交 + shim 接口契约测试

### `tests/unit/personal_assistant/test_cron_config_sync.py` — **合并检查**

| 属性 | 现状 |
|---|---|
| 行数 | 315 行 |
| 命名 | 合法 |
| 内容 | 测 `sync_agent` cron_enabled 传递行为 |
| 重叠风险 | `test_m9b_cron_json_retire.py`（已在 PR 之前合入）也测 cron_json→features 同步，部分断言可能重叠 |

**处置**：
- 对照 `test_m9b_cron_json_retire.py` 检查重叠，将重叠用例合并到行为描述更准确的文件，删除冗余断言
- `test_cron_config_sync.py` 本身保留（命名合法，关注点清晰）

### `tests/unit/personal_assistant/test_cron_at_expiry.py` — **保留**

| 属性 | 现状 |
|---|---|
| 行数 | 95 行 |
| 命名 | 合法（测 `at` schedule 到期行为） |
| 内容 | 独立关注点，无重叠 |

**处置**：保留，无需改动。

### `tests/unit/personal_assistant/test_cron_file_tools.py` — **保留**

| 属性 | 现状 |
|---|---|
| 行数 | 99 行 |
| 命名 | 合法 |
| 内容 | 测 `resolve_effective_tool_allowlist` 函数签名 + cron 工具追加逻辑 |

**处置**：保留，无需改动。

### `tests/unit/personal_assistant/test_cron_polling_runner.py` — **保留**

| 属性 | 现状 |
|---|---|
| 行数 | 186 行 |
| 命名 | 合法 |
| 内容 | 测 polling runner 对 cron_enabled 的路由分支 |

**处置**：保留，无需改动。

### `tests/unit/personal_assistant/test_cron_delivery_chain.py` — **保留**

| 属性 | 现状 |
|---|---|
| 行数 | 356 行 |
| 命名 | 合法 |
| 内容 | 测 cron 可见交付链（run_context_store seeding + stream consumer） |

**处置**：保留。可选：函数 docstring 去掉 `feat-394-M7 R2` 引用。

### `tests/unit/agent/test_feature_registry.py` — **保留**

| 属性 | 现状 |
|---|---|
| 行数 | 173 行 |
| 命名 | 合法 |
| 内容 | 测 FeatureRegistry 注册表结构和 cron/heartbeat 条目形状 |
| 落层 | 正确（unit/agent） |

**处置**：保留，无需改动。

---

## 三、Python contract 测试

### `tests/contract/test_cron_coding_cli_isolation.py` — **保留**

| 属性 | 现状 |
|---|---|
| 行数 | 91 行 |
| 命名 | 合法 |
| 内容 | 架构边界：coding_cli 不含 cron tool / heartbeat segment |
| 落层 | 正确（contract 层） |

**处置**：保留，无需改动。

### `tests/contract/test_kernel_sdk_behavior_contract.py` — **保留（变更为追加）**

| 属性 | 现状 |
|---|---|
| 行数 | 401 行（恰好在软上限） |
| 变更 | PR 在文件末尾追加了 `append_message` cache coherence 测试（81 行） |
| 内容 | 追加部分测 cron awareness 回归，关注点属于 kernel SDK 契约层 |

**处置**：保留。若后续文件继续增长需考虑按关注点拆分（cache coherence 独立文件）。

### `tests/contract/test_no_hardcoded_workspace_dirname.py` — **保留（白名单行号更新）**

| 属性 | 现状 |
|---|---|
| 变更 | 2 行：白名单行号因 ruff 格式化更新 |
| 内容 | 纯机械维护，正确处置 |

**处置**：保留，无需改动。

---

## 四、Python integration 测试

### `tests/im_service/integration/test_agent_config_api.py` — **保留，关注行数**

| 属性 | 现状 |
|---|---|
| 行数 | 965 行（超 400 软上限 2.4 倍） |
| 命名 | 函数名合法 |
| 变更 | PR 追加了 cron jobs / heartbeat md RPC 测试（350 行新增） |
| 落层 | 正确（im_service/integration） |

**处置**：
- 近期（本 PR 范围外）按关注点拆成：
  - `test_agent_config_api.py`：agent config CRUD 核心行为（现有前 600 行）
  - `test_agent_rpc_relay.py`：cron jobs / heartbeat md RPC 中继（PR 新增部分）

### `tests/im_service/integration/test_heartbeat_config_sync_pipeline.py` — **保留**

| 属性 | 现状 |
|---|---|
| 行数 | 265 行 |
| 命名 | 合法 |
| 内容 | 全链路回归：IM PATCH → WS frame → sync_agent → scheduler，独立关注点 |
| 落层 | 正确（integration，不起真 LLM） |

**处置**：保留，无需改动。

### `tests/im_service/unit/test_gateway_handler.py` — **拆分**

| 属性 | 现状 |
|---|---|
| 行数 | 1111 行（超 400 软上限 2.8 倍） |
| 命名 | 合法 |
| 变更 | PR 追加 501 行（heartbeat md / cron jobs RPC handler 测试） |

**处置**：
- 按关注点拆成（均在 `tests/im_service/unit/`）：
  - `test_gateway_handler.py`：保留 connection management / relay / turn_start 逻辑（约前 600 行）
  - `test_gateway_rpc_handlers.py`：承接 heartbeat_md / cron_jobs / cron_delete RPC handler 测试（PR 新增 500 行）

---

## 五、Python contract/integration 小改动

### `tests/im_service/contract/test_agent_config_contract.py` — **保留（契约更新）**

变更：添加 `heartbeat_json` 到期望 schema 集合，更新 tools/skills 的 `default_on` 字段。属于契约同步，正确处置。

### `tests/im_service/contract/test_agent_create_contract.py` — **保留（契约更新）**

变更：同上，3 行 schema 更新。正确处置。

### `tests/integration/test_personal_assistant_bootstrap_integration.py` — **保留**

变更：将 exact list 断言改为 membership 断言，适应 cron 工具新增。正确处置。

### `tests/integration/test_prompt_sections_golden.py` — **保留**

变更：`assert "## Heartbeat" in` 改为 `not in`（heartbeat 改为 feature-gated）。正确处置，黄金输出同步更新。

---

## 六、已存在的 milestone 流水号命名文件（不在 PR #78 范围，但属于本 unit）

下列文件在 `git diff origin/main` 中可见，命名违规，**收尾时须统一处理**：

| 文件 | 违规 | 建议改名 |
|---|---|---|
| `test_m9b_cron_json_retire.py` | `m9b` 流水号 | `test_cron_json_retire.py` |
| `test_m9_agent_config_features.py` | `m9` 流水号 | `test_agent_workspace_config_features.py` |
| `test_m9_r5_tools_default_on.py` | `m9_r5` 流水号 | `test_upstream_reporter_tools_default_on.py` |
| `test_m9e_dead_code_removal.py` | `m9e` 流水号 | `test_cron_json_dead_code_removed.py` |
| `test_m9_feature_model_gate.py` | `m9` 流水号 | `test_heartbeat_cron_feature_gate.py` |

改名同时检查各文件内 `def test_` 函数名是否含 `m9`/`M9` 前缀，有则一并改为行为描述。

---

## 七、优先级排序

| 优先级 | 文件 | 处置 | 估时（CC） |
|---|---|---|---|
| P0（命名违规，CI 可读性） | `agent-m9c-features-panel.test.tsx` 改名 + describe 去 milestone 前缀 | 改名 | 5 min |
| P0 | `agent-detail-page.test.tsx` 内 it/describe 去 milestone 前缀 | 改名 | 10 min |
| P0 | `test_m9*` 五个文件改名 | 改名 | 10 min |
| P1（行数超限，维护性） | `agent-detail-page.test.tsx` 拆分 | 拆分 | 15 min |
| P1 | `test_gateway_handler.py` 拆分 | 拆分 | 15 min |
| P1 | `test_cron_awareness.py` 拆分 | 拆分 | 10 min |
| P2（重叠清理） | `test_agent_config_api.py` 拆分（近期） | 拆分 | 20 min |
| P2 | `test_cron_config_sync.py` vs `test_m9b_cron_json_retire.py` 重叠核查 | 合并/删冗余 | 10 min |

P0 项可在本 PR 合入前处理；P1/P2 可作为 cleanup PR 跟进（建议 gh issue 追踪）。
