# feat-439 — 验收报告

> 对齐: spec.md 验收标准（token 气泡缓存命中率 + 内部 IM 展示 thinking 过程时间线）

## Metadata

- **Review Round**: 1
- **Reviewer**: feat-439-reviewer
- **Date**: 2026-06-26
- **Branch**: unit/feat-439
- **Worktree**: /Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-439
- **Highest Required Action**: pass
- **Verdict**: pass

---

## Verdict

**pass**

两条特性均在真 Gateway + 真 K2.6 LLM 下端到端验收通过。

---

## 澄清记录

无需澄清——spec.md 验收标准清晰；dispatch 明确指定了两个核心验收点（缓存数字真实性 + thinking 时间线）。

---

## 用户旅程体验

### 服务接管

- 前端构建：在 worktree 执行 `npm run build`，产物 `index-DPkvgZGx.js`，指纹核验命中 `缓存命中`、`thinking_segment`、`💭` 三个关键 marker ✓
- 服务栈：`scripts/e2e-up.sh` 起 IM(port 53271) + Gateway(PID 66896)，连接 wt-unit-feat-439-66824 节点，agent `default-agent` online ✓
- LLM Proxy：http://127.0.0.1:4000/health → ok ✓，模型 K2.6（adaptive thinking）

### 旅程 1：多工具调用对话 → 验收 M1 + M2 主路径

发送：`请帮我用bash查看一下当前工作目录，然后列出其中的文件，再查看一下README.md的前5行。`

Agent 触发 2 次 LLM 请求（thinking → bash_tool_call → 第二次 LLM → 答复），产生两个气泡：

- 气泡 1："好的，我帮你用 bash 执行这几个操作。"
  - 过程盘：`▸ Process · 1 tools · 2 thinking`
  - 展开后时序：💭 Thinking → 💭 Thinking → ✕ bash（failed 18ms）
  - 展开第 1 段思考：可读完整内容（模型分析了三个子任务的执行策略）
  - 收起：`▸` 标志恢复

- 气泡 2："结果如下：..." + `▸ Process · 1 thinking` + `▸ 5.0k tok · ctx 2%`
  - **token 气泡详情**（截图：`.playwright-cli/page-2026-06-26T10-42-10-341Z.png`）：
    - output tokens: 381
    - total tokens: 5,020
    - context used: 4,639 / 262k
    - **cache hit: 4,096 (46%)** ← 新增行，位置在「已用上下文」行下方

**上游核对**（LLM Proxy logs `/Repos/LLM_PROXY/logs/session/2026-06-26_18-37-29_087_sess_8f833fc6a89a9e7c/`）：
- 请求 1（18:37:29）：`cache_read_input_tokens: 0`, `input_tokens: 4,240`
- 请求 2（18:37:33）：`cache_read_input_tokens: 4,096`, `input_tokens: 4,639`
- 整轮累计：`Σcache_read = 4,096`，`Σcache_total_input = 8,879`，命中率 = 4,096/8,879 = **46.1% ≈ 46%** ✓
- `context_used = 4,639`（最后一次快照值） ✓

### 旅程 2：简单问候 → 验收 M1 非零缓存 + M2 单段 thinking

发送：`你好！`

Agent 单次 LLM 请求回复"你好！有什么我可以帮你的吗？"：
- 过程盘：`▸ Process · 1 thinking`
- token 气泡详情：output 20 / total 4,623 / context 4,603 / 262k / **cache hit: 3,840 (83%)**
  - 系统提示词已缓存，命中率提升至 83%

### 旅程 3：历史回看持久化测试

从对话页导航至 `/chat` → 再返回对话，过程盘仍可见且仍可展开：
- `▸ Process · 1 tools · 2 thinking`（历史）展开 → 💭 行仍可点击展开 → 完整思考内容加载 ✓
- `▸ 5.0k tok · ctx 2%` 仍显示 `cache hit 4,096 (46%)` ✓

---

## 验收标准覆盖

### Requirement: token 气泡展示本轮缓存命中率 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 本轮有缓存命中 | spec.md §验收标准 / design §1.9 | 真栈 K2.6 对话 → 点开 token 气泡详情；上游 proxy log 核对 | 截图 `.playwright-cli/page-2026-06-26T10-42-10-341Z.png`；proxy log `cache_read_input_tokens: 4096`；UI 显示 `cache hit: 4,096 (46%)` | **pass** | 数值经双向核对：UI 46% ≈ upstream 4096/8879=46.1% ✓；context_used 4639 未回归 ✓ |
| 本轮无缓存命中(空态) | spec.md §验收标准 | M1 worker R3 browser QA（seed DB）；live 渲染机制同路径 | worker R3 progress："无命中气泡显示 cache hit 0 (0%)"；live K2.6 始终有缓存命中（系统提示词已预缓存），无法在 live 触发 0% | **pass** | 0% 空态由 worker seed DB 浏览器验证确认行恒显示；live 命中率从未低于 46%，证明数据链路正常。`??0` 防 div-zero 由 worker vitest 覆盖 |

### Requirement: 内部 Web IM 把思考与工具操作展示为一条过程 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 一条回复含多段思考与多次工具操作 | spec.md §验收标准 / design §决策 4 | 真栈 K2.6 多工具请求 → 展开过程盘观察时序 | 截图 `.playwright-cli/page-2026-06-26T10-44-30-264Z.png`；snapshot 显示 `💭 Thinking → 💭 Thinking → ✕ bash` 时序；标签 `▾ Process · 1 tools · 2 thinking` | **pass** | thinking 先于 tool 出现（先思考后调工具），时序混排正确 ✓ |
| 思考整段可展开回看 | spec.md §验收标准 | 点击 💭 行展开 → 读完整内容 → 点击收起 → 导航离开再返回仍可展开 | 截图 `.playwright-cli/page-2026-06-26T10-45-21-804Z.png`（展开全文）；历史回看后 snapshot 确认 `expanded` 状态仍可操作 | **pass** | 展开：显示完整思考文本；收起：`▸` 标志恢复；历史刷新后仍可展开/读全文 ✓ |
| 模型本轮无思考(空态) | spec.md §验收标准 | worker vitest 覆盖（474 passed 含无思考情形） | M2 R4 progress："vitest 覆盖 + 第二气泡「1 thinking / 0 tools」纯思考态"；live 无法用 K2.6 触发无思考（adaptive thinking 始终思考） | **pass** | K2.6 adaptive 每轮必思考，live 不可复现无思考。worker 单测覆盖「无思考无 💭」路径；过程盘逻辑：无思考段 = 无 💭 行，代码路径通过 vitest 验证 |

### Requirement: 外部 IM 不暴露 thinking — 组内结论：not-applicable

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 外部 channel 只收到正文 | spec.md §验收标准 | — | — | **not-applicable** | spec 明确"外部第三方 channel 的实际接入不在本 unit"；本 unit 只保证外部触点不带 thinking 的契约，实现层验证由 M2 worker 单测覆盖（channel 出站序列化不包含 thinking 字段）。本次 e2e 无外部 channel 环境，无法用户面验证 |

---

## Issues 清单

**无 blocking / major 问题。**

### Minor 观察（不立 issue）

| # | 严重度 | 现象 | 分类 | Regression Relation |
|---|---|---|---|---|
| 1 | minor | 第一个气泡的 bash 工具调用显示 `failed`（红色，18ms）。这是事实描述（该 bash 命令确实失败），agent 在第二轮请求中恢复并提供了结果。对不了解 agent 工作流的用户可能产生困惑，但这是既有 tool status 展示逻辑，非本 unit 引入 | Side Finding | unrelated-existing |

---

## Side Findings

- **Tool status "failed" 可读性**：过程盘显示 bash 工具 `failed 18ms`，用户若看到"failed"而下方却有正确结果，可能不解原因。这是既有 tool_call 状态展示逻辑，非本 unit 引入，归类为 minor out-of-unit，不立 issue（minor 不立，记录备查）。
- **K2.6 始终产生 thinking**：使用 adaptive thinking 模型无法在 live 环境触发无思考状态，0% 缓存命中和无思考空态均需 seed DB 或 non-thinking 模型才能复现。这是测试环境约束，不是功能缺陷。

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**（feat-439 不涉及包间架构变动）
- [x] `docs/specs/im/spec.md`（长青行为契约层）：**需要更新** — 当前"对齐"行仍指 bugfix-429/feat-434，未含 feat-439 delta-spec。delta-spec 草案在 `docs/changes/feat-439-im-cache-hit-and-thinking/specs/im/spec.md`，由 orchestrator 收尾归并。
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：**需要更新** — 当前"对齐"行指 bugfix-437，未含 feat-439。delta-spec 在 `docs/changes/.../specs/kernel/spec.md`，orchestrator 收尾归并。
- [x] `docs/specs/gateway/spec.md`（长青行为契约层）：**需要更新** — 同上，delta-spec 在 `docs/changes/.../specs/gateway/spec.md`，orchestrator 收尾归并。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**（feat-439 不涉及开发约定或架构说明变动）
- [x] `docs/SPEC_GUIDE.md`：**无需更新**（feat-439 不改文档体系本身）

> 3 处长青契约层（kernel/gateway/im spec.md）的"对齐"行更新属于 orchestrator §7.0 收尾归并职责，已有 delta-spec 草案，reviewer 仅标记未合并状态。
