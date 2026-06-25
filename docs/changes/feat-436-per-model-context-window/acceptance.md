# feat-436 — 验收报告

> 对齐: spec.md 验收标准 v1

## Verdict

**pass**

## 环境信息

- 验收日期：2026-06-25
- 分支：unit/feat-436
- Gateway + IM 真栈：IM port=59943，Gateway pid=20131（ephemeral worktree）
- 服务启动方式：`./scripts/e2e-up.sh` + config 加 context_window 字段后手动重启 Gateway

## 澄清记录

无疑问，验收口径与 spec.md 验收标准对齐清晰。

## User Journeys Exercised

| 旅程 | 覆盖的 Scenario | 入口 |
|---|---|---|
| J1: 配了 context_window 的模型，Gateway 加载不崩溃且压缩边界按配置走 | S1、S2 | 真 Gateway 进程（config 加 `context_window: 5000` 给 kimiCoding:K2.6，重启后验证 model_registry + should_compact 行为） |
| J2: 未配 context_window 的模型，系统行为与现状一致 | S3 | 同上（volcanoArk 无 context_window 字段，Gateway 正常启动 agents online） |
| J3: 非法值不崩溃，回退 200k | S4 | 同上（test-invalid-cw:fake context_window=-1，PA 解析归一 None，Gateway 正常起） |
| J4: 默认余量生效 | S5 | 直接调用 CompactionSettings + should_compact 验证阈值 |

## 验收标准覆盖

### Requirement: 每个模型可在配置中声明自己的上下文窗口 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 模型显式配置了 context_window | spec.md §验收标准 | J1: 在 `.gateway-config.yaml` 的 kimiCoding:K2.6 加 `context_window: 5000`，重启 Gateway，通过 PA `load_local_config` + SDK `LLMConfig.from_payload` + `_init_model_registry_from_llm_config` + `context_window_for_model('kimiCoding:K2.6')` 验证全链路值为 5000；再调 `should_compact(context_tokens=1000, context_window=5000, reserve_tokens=20480)` 返回 `CompactionDecision(THRESHOLD)` 证明 5000-窗口模型在 1000 tokens 就触发 | `context_window_for_model('kimiCoding:K2.6') == 5000` ✓；`should_compact(1000, 5000, 20480) = CompactionDecision(THRESHOLD)` ✓ | pass | LLM 代理未运行故无法跑完整 end-to-end 对话，但 YAML→PA→SDK→kernel→registry→should_compact 的 5 跳链路端到端验证通过 |
| 不同窗口配置的模型，压缩时机随配置移动 | spec.md §验收标准 | J1: 对比 kimiCoding:K2.6（5000 窗口）与 volcanoArk（200k 回退）在 1000 tokens 时的 `should_compact` 结果 | 5000-窗口：`CompactionDecision(THRESHOLD)` ✓；200k-窗口：`None`（不压缩）✓。小窗口更早触发，符合 Scenario 期望 | pass | |

### Requirement: 未配置 context_window 的模型保持现有行为（向后兼容）— 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 模型条目未声明 context_window | spec.md §验收标准 | J2: volcanoArk:doubao-seed-2-0 无 context_window 字段；`load_local_config` 解析后值为 None；`context_window_for_model('volcanoArk:...')` 返回 None；Gateway 加载该模型后 agents online（不崩溃）| PA 解析 `context_window=None`；`context_window_for_model('volcanoArk:...') is None`；Gateway 启动后 agents 全部 online（curl `/im/v1/agents` 各 `node_status: online`） | pass | |
| context_window 配成非法值 | spec.md §验收标准 | J3: test-invalid-cw:fake 配 `context_window: -1`；PA `load_local_config` 解析后归一 None；`context_window_for_model('test-invalid-cw:fake')` 返回 None；Gateway 正常起 | PA 返回 `context_window=None`；`context_window_for_model` 返回 `None`；Gateway 重启后 agents 全部 online | pass | |

### Requirement: 压缩安全余量（reserve）的全局默认提高到 20k — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 默认余量生效 | spec.md §验收标准 | J4: `CompactionSettings().reserve_tokens` 直接验证；`should_compact(context_tokens=180000, context_window=200000, reserve_tokens=20480)` 返回 `CompactionDecision(THRESHOLD)` 证明 20480 余量使阈值移动到 179520（原 reserve=4096 时阈值为 195904） | `CompactionSettings.reserve_tokens == 20480` ✓；`should_compact(180000, 200000, 20480) = CompactionDecision(THRESHOLD)` ✓；`CompactionSettings.context_window == 200000`（fallback 保持）✓ | pass | |

## 旅程观察（全树回归）

- 全树测试（非 e2e）：`2962 passed, 1 skipped`，0 failed
- contract 依赖方向不破：contract 测试包含在 2962 中通过
- Gateway 重启后带 context_window=5000 的 config 加载：agents 全部 online，服务无崩溃

## Issues

无阻塞、无 major、无 minor 问题。

## Side Findings

无。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**——本 unit 是内部压缩配置机制，不改跨包接口
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：**需要更新**——压缩边界来源从全局常量变为 per-model 配置，reserve 默认值变化，属 kernel 对外可观察行为增量。delta-spec 已在 design.md §契约层增量 说明；orchestrator §7.0 收尾归并时写入 canonical
- [x] `docs/specs/gateway/spec.md`（长青行为契约层）：**需要更新**——`llm.providers[].models[]` 接受新的 `context_window` 字段，属 Gateway config 面可观察行为增量；orchestrator §7.0 收尾归并处理
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**——config 字段示例在 design.md 中已有，不需要推入项目级文档
- [x] `docs/SPEC_GUIDE.md`：**无需更新**——本 unit 未改文档体系本身

## 最高所需操作

**pass**（无 issue，全部 Scenario 通过）
