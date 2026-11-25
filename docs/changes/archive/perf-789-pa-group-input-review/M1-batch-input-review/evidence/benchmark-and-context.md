# M1 Evidence: 参与群按唤醒批次合并输入审核

## 1. 同口径性能对照（Baseline vs Candidate）

- **对比基线**: `4ff83afda84a2ba67047524cb559e8b2f8655fb1` (`origin/develop`)
- **分词与请求核算口径**: `@deepseek-ai/dsh-token-meter/estimate`（含 `standalone-model-retry.ts` 的 `+4` message framing 与 `'[]'` tools 开销核对），预设相同 20 条群历史背景（含主人与 4 名群成员交替讨论），驱动真实 `GlobalAgent`、`InboxStore`、`personalInputBatchContext` 与 `inputReviewEvidence`。
- **复现定位**:
  - 单元与集成回归：`apps/im-server/tests/personal-input-context.test.ts`、`packages/dsh-integration/tests/personal-security.test.ts`、`packages/personal-assistant/tests/input-admission.test.ts`、`packages/personal-assistant/tests/personal-attention.test.ts`、`packages/product-contracts/tests/runtime-rpc.test.ts`。
  - 会话暂存基准脚本与捕获原件（仓外 scratch，验收后随会话生命周期维护）：`measure_baseline.mjs`、`measure_candidate.mjs`、`sample-batch-review-request.json`。

| 指标 | 样本 A 基线 (`4ff83afda`) | 样本 A 候选 (M1) | 样本 A 变化 | 样本 B 基线 (`4ff83afda`) | 样本 B 候选 (M1) | 样本 B 变化 |
|---|---:|---:|---:|---:|---:|---:|
| 总入站群消息数 | 20 | 20 | 不变 | 25 (20 普通 + 3 主人 + 2 `@PA`) | 25 | 不变 |
| 主 PA 唤醒次数 (`mainWakeCalls`) | 1 | 1 | 不变 | 2 | 2 | 不变 |
| 可读未读消息数 (`unreadInInbox`) | 20 | 20 | 不变 | 25 | 25 | 不变 |
| `pa.input.context` 调用次数 | 20 | **1** | **-95.0%** | 22 | **2** | **-90.9%** |
| `pa.review('input')` 模型请求数 | 20 | **1** | **-95.0%** (目标 `1`) | 22 | **2** | **-90.9%** (目标 `2`) |
| 累计 System Prompt Tokens | 28,640 (`1,432 × 20`) | **1,105** (`1,105 × 1`) | **-96.1%** | 31,504 (`1,432 × 22`) | **2,210** (`1,105 × 2`) | **-93.0%** |
| 累计 User Evidence Tokens | 46,235 | **2,181** | **-95.3%** | 50,490 | **3,475** | **-93.1%** |
| **累计审核输入 Tokens (`system + user`)** | **74,875** | **3,286** | **-95.6%** (目标 `≤ 8,000`) | **81,994** | **5,685** | **-93.1%** (目标 `≤ 15,000`) |
| 含 Wire Framing 总输入 Tokens | 75,055 | **3,295** | **-95.6%** | 82,192 | **5,703** | **-93.1%** |
| 估算 JSON 判定输出 Tokens | ~320 | **331** | 持平（省去 19 次独立推理前缀） | ~352 | **370** | 持平（省去 20 次独立推理前缀） |
| 本地准入与批审管线耗时 | — | **17.84 ms** | 单次同步内存/SQLite 管线 | — | **16.95 ms** | 双批次管线 |

## 2. 模型可见批量输入 Context 脱敏结构摘要

由 `personalInputBatchContext` + `personalReviewPolicy('input', true)` + `inputReviewEvidence` 实际序列化生成的混合批次请求结构摘要（合成群聊样本 B 第 1 批：16 条非主人待审项 + 1 条穿插主人发言）：

- **执行参数**：`tools: undefined`，`temperature: 0`，`maxTokens: 4096`，`reasoningEffort: 'low'`（若模型支持）。
- **System 关键契约摘要**：
  - 仅激活批量模态指引（不含单条 `The current message is the only pending input` 文本，不含 `needs_owner` 枚举）；
  - 声明 `conversation`、`previous`、`reply_targets` 与无 `item` 的 `timeline` 条目（`needs_decision=false`）均为不可执行背景证据；
  - 要求对 `item: 1..k` 逐条独立判定 `allow | deny`：普通群务与未获授权的直白外部协作请求判 `allow`（交主 PA 与出站披露审核把关），显式注入、伪装系统/主人授权、隐蔽套话或借历史接力注入判 `deny`，前文他人可疑发言不连坐后续正常发言者。
- **User JSON 结构摘录（合成数据）**：

```json
{
  "conversation": { "id": "c_group", "type": "group", "delivery": "participant", "channel": "web" },
  "omissions": [],
  "previous": [
    {
      "id": "seed_1",
      "sender": { "id": "owner", "name": "陈总", "type": "user", "is_owner": true },
      "addressed_to_agent": false,
      "content": "产品评审第 1 条讨论：确认本迭代接口字段、灰度发布窗口与联调排期细节，避免阻塞客户端提测。",
      "created_at": "2025-11-25T08:40:00.000Z"
    }
  ],
  "timeline": [
    {
      "item": 10,
      "id": "mix_10",
      "sender": { "id": "member_3", "name": "同事3", "type": "user", "is_owner": false },
      "addressed_to_agent": false,
      "content": "模块 10 的自测用例已经跑通，边界异常状态码和重试幂等性都核对过了。",
      "created_at": "2025-11-25T08:47:30.000Z"
    },
    {
      "id": "mix_11",
      "needs_decision": false,
      "sender": { "id": "owner", "name": "陈总", "type": "user", "is_owner": true },
      "addressed_to_agent": false,
      "content": "收到，这块大家按排期推进，有风险随时在群里同步。",
      "created_at": "2025-11-25T08:47:45.000Z"
    },
    {
      "item": 11,
      "id": "mix_12",
      "sender": { "id": "member_1", "name": "同事1", "type": "user", "is_owner": false },
      "addressed_to_agent": false,
      "content": "模块 12 的自测用例已经跑通，边界异常状态码和重试幂等性都核对过了。",
      "created_at": "2025-11-25T08:48:00.000Z"
    },
    {
      "item": 16,
      "id": "mix_17",
      "sender": { "id": "member_2", "name": "同事2", "type": "user", "is_owner": false },
      "addressed_to_agent": true,
      "explicit_mentioned_agent_ids": ["pa_bench"],
      "content": "<mention type=\"user\" target_id=\"u_pa_bench\" /> 帮我们整理一下刚才前面大家同步的模块联调进展",
      "created_at": "2025-11-25T08:49:15.000Z"
    }
  ]
}
```
