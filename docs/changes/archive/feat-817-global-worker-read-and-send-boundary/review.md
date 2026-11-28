# feat-817-global-worker-read-and-send-boundary: Review

## 范围与版本

- 本次问题与需求/设计位置：[spec.md](spec.md)、[design.md](design.md)、[specs/gateway/spec.md](specs/gateway/spec.md)、[specs/gateway/global-agent.md](specs/gateway/global-agent.md)、[specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md)
- 实际 `executed_base` / `validated_at`：`ce1ca8fba524276e09cc14482185e7bf2b92e5e7` / `9b7d114848ca50524eee8253dc8a4010dd5d97e4`（Round 1）→ `deb28eb58b1e863e33f2f362a3751035b3d0123d`（Round 2 闭环复验）
- 最终 `effective_base` / `effective_through` 与保留依据：已同步最新 `origin/develop`（`effective_base = bbcbc5d4a6599cc4d289ba7e07493e6895cdddb1`），全部代码文件零冲突自动合入，仅合并 3 份 Gateway spec 的对齐头与 `Global Agent` 计数（`25`）；`9b7d11484..deb28eb58` 仅修复 CLI 历史投影与错误摘要（`manager.ts` / `inspector.ts` / `worker-inspection.test.ts`），未改动 Prompt、工具 Schema、`capabilities.ts`、`approval.ts`、`index.ts`、`SKILL.md` 或 DSH wire 上下文，因此 `G2-context-and-behavior` 原 `pass` 结论 `retained`。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| `G1-code-and-contracts`：`WorkerInspector` 跨运行时投影与脱敏、`LocalWorkers` 独立历史表与用量统计、DSH/CLI 终局用量尾注、`GlobalMode`/`capabilities`/`approval` 边界闭合、五端 `fixedTools` 同步与不回归、3 份 Gateway delta-spec 一致性 | `change-code-review` + `corrected-delta`；独立子代理 `ff6361a5-9872-4cbd-b4be-5acf3e8c3c5b`（只读独立审查，R1 full + R2 closure/patch-delta） | `pass` | R1 在 `9b7d11484` 检出 3 处 CLI 历史/摘要缺陷（`F-001`~`F-003`）并确认 3 份 delta-spec `aligned`；R2 复核 `9b7d11484..deb28eb58`（`pnpm --filter @nano/dsh-integration typecheck` + `worker-inspection.test.ts` + `local-worker-manager.test.ts` 全部通过）确认全部 3 项关闭、0 存活阻塞项。限制：审查者未亲自重跑全量 `pnpm test`、全量前端套件及 Xcode `swift test`（由 owner 在交付门禁补充运行）。 |
| `G2-context-and-behavior`：主 Agent 出站 wire 请求工具定义/系统提示词/Skill/缓存前缀稳定性、`read_worker` 返回无系统注入噪声/无图片 base64/凭据脱敏、非授权升级边界、真实模型四场景定量克制读取门槛 | `agent-context-review`（Implementation Mode）；独立子代理 `dcce8f27-bedd-4a86-b985-96b18d3f13f6`（只读独立审查，亲自读取原件） | `retained` (`pass` on `9b7d11484`) | 亲自读取 22 条真实出站 Anthropic wire 请求（14 条 Global Root + 8 条 Worker-1，`wire-requests-2026-11-28T08-03-38-730Z.jsonl`）与四场景轨迹报告（`restraint-report-2026-11-28T08-03-38-730Z.json`）：14 次 Root 请求 `system`/`tools` SHA-256 100% 稳定；`send_message` 纯对外、`list_agents`/`interrupt_agent` 隐藏；`read_worker` 返回 0 系统注入噪声、0 图片 base64、`Bearer [REDACTED]` 脱敏；S1 `read_worker=0`、S2 `summary=1 (499 chars), read=0`、S3 `[Worker usage: turns=1, tokens=60910]` 且 `read=0`、S4 `read(view="activity")=1 (1,353 chars), 0 duplicate`，准确诊断根因且 0 泄密。限制：S4 子代理确定性产出模糊失败，外部 CLI / PA / root fork / `single_thread` 由自动化集成测试覆盖而非本次实网 wire 覆盖。 |

## Findings 与关闭

### `F-001` (`[HIGH]` `[CONFIRMED]` -> `closed`)
- **来源**：`G1-code-and-contracts` Round 1（`9b7d11484`）
- **位置**：`packages/dsh-integration/src/local-workers/manager.ts:807-822`, `311-326`
- **问题与影响**：CLI `tool_end` 将 `summary` 兜底为 `tool_name`（非 `undefined`），导致 `upsertCliHistoryLocked` 用裸 `tool_name` 覆盖 `tool_start` 记录的真实命令/路径摘要。
- **Resolution**：在 `deb28eb58` 移除 `tool_end` 的 `?? tool_name` 兜底，仅在新插入 `tool` 条目无 `prior` 时默认 `item.toolName`；`worker-inspection.test.ts:123` 移除人工 `presentation.summary` 以覆盖真实 CLI 行为。
- **独立关闭依据**：`ff6361a5-9872-4cbd-b4be-5acf3e8c3c5b` 于 `deb28eb58` 核查 diff 与回归测试通过后关闭。

### `F-002` (`[HIGH]` `[CONFIRMED]` -> `closed`)
- **来源**：`G1-code-and-contracts` Round 1（`9b7d11484`）
- **位置**：`packages/dsh-integration/src/local-workers/inspector.ts:411-416,584-631`, `packages/dsh-integration/src/local-workers/manager.ts:473,614,624,849`
- **问题与影响**：`summary()` 优先采用已预截断（601 字符）的 `row.latestError` 而非完整历史项，导致 `latest_error_total_chars` 失真或 `latest_error_item_id` 错配；同时 4 处错误 `system` 写入未显式标记 `status: 'error'`，非英文关键词错误会被漏判。
- **Resolution**：在 `deb28eb58` 为全部 4 处错误 `system` 写入显式设置 `status: 'error'`；`inspector.ts` 改为优先使用完整 `errorItemCandidate?.text`，仅在由真实历史项支撑时返回 `*_truncated`/`*_total_chars`/`*_item_id`。
- **独立关闭依据**：`ff6361a5-9872-4cbd-b4be-5acf3e8c3c5b` 于 `deb28eb58` 核查 diff 与 >600 字符非关键词错误单测后关闭。

### `F-003` (`[WARNING]` `[CONFIRMED]` -> `closed`)
- **来源**：`G1-code-and-contracts` Round 1（`9b7d11484`）
- **位置**：`packages/dsh-integration/src/local-workers/manager.ts:611-621,845-855`
- **问题与影响**：外部 CLI 失败回合同时经 `onDetail(turn_end)` 与 `deliver(turn-end)` 写入两条内容相同的 `system` 错误条目。
- **Resolution**：在 `deb28eb58` 为 `deliver()` 失败/中断分支补充相邻去重检查（与 `completed` 分支一致），并在 `worker-inspection.test.ts` 断言仅保留 1 条去重记录。
- **独立关闭依据**：`ff6361a5-9872-4cbd-b4be-5acf3e8c3c5b` 于 `deb28eb58` 核查 diff 与回归测试后关闭。

### 非阻塞观察（记录留档，不阻断交付）
- `G2` 观察到 DSH `subagent-settled` 附带的 `[Worker usage: ...]` 在 Anthropic wire 上与上一文本块紧邻（无前导 `\n`）、`extractToolSummary` 对 `skill`/`glob` 回退为工具名、`send_message.reply_to_message_id` 共享描述仍保留历史字样；模型在 S1–S4 均准确解析，后续可按需微调。

## 流程收口

- 重要目标和关键设计覆盖：`read_worker` 跨运行时只读观测、轮次与已结算 Token 统计、终局唤醒 `[Worker usage: ...]` 尾注、外部 CLI 独立持久历史、Global/PA `send_message` 纯对外收口、隐藏 `list_agents`/`interrupt_agent`、五端 `fixedTools` 同步及真实模型四场景克制读取硬门槛均已落地并通过验证。
- 开放问题 / pending / inconclusive：无（0 存活阻塞 findings）。
- 最终 delta 校对：3 份 Gateway delta-spec 经 `G1-code-and-contracts` 独立核对为 `aligned`，已归并至 `docs/specs/gateway/{spec,global-agent,agent-capabilities}.md`。
- 版本变化后保留 / 补验的判断与依据：`9b7d11484..deb28eb58` 经 `G1` 独立闭环复验通过；未改动 Context 装配或 DSH wire 行为，`G2` `pass` 结论按 `validation.md` 保留有效；合并 `origin/develop`（`d5000a40d`）后已额外在主推荐模型 `codexOAuth:gpt-6.2-sol` 上补跑完整四场景克制读取与 24 条出站 wire 验证（17 条 Global Root 请求 `system`/`tools` 哈希 100% 稳定，S1 `0`、S2 `summary=1 (698 chars), read=0`、S3 `read=0`、S4 `read(view="activity", limit=8)=1 (1,301 chars), 0 duplicate`，0 泄密/0 噪声，全部通过）。
- 测试资源回收结果：真实模型隔离运行临时目录与本地透明抓包代理已在验证脚本 `finally` 块中关闭并清理完毕，工作树无遗留进程、PID、临时配置或 `src/IM/frontend/dist/` 提交物；开发 worktree 按规范在 PR 合并前保留。
- 交付范围与剩余事项：推送分支并创建目标为 `develop` 的 PR，等待远端 CI（含 macOS iOS `build.sh test`）与人工合并；合并后清理开发 worktree。
