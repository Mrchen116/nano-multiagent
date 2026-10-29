# feat-677 implementation evidence

## Scope

2026-10-29 用户要求先实现、停在实际模型评测之前。本轮仅完成 LongMemEval 框架、Nano 文档记忆候选接线和确定性验证；真实候选模型、真实 judge、公开 benchmark 正式样本均未运行。不得从固定响应的通过率推断模型效果。

实现保留用户指定的 feat-676 分支基线，不把主仓的新 Dreaming 设计当成已实现行为。后续记忆改版的接线留在 Nano adapter。

## M1 implementation

- 稳定 `MemoryCandidate.prepare/answer/close` 类型与 opaque 状态引用位于 product-contracts；数据、Runner、官方评分规则和报告不导入 DSH。
- Nano 专用入口加载评测 profile 插件，使用 DSH 公开 SessionPersistence 导入历史、实际 KnowledgeRuntime 准备记忆。空历史基线先登记，再追加原文，避免首次激活跳过经历。
- 每道题与每次答题分别创建独立 runtime/workspace/session。只恢复文档记忆和其必要版本/来源状态；答题工具拒绝访问旧 runtime、控制文件及越界 glob。
- 默认 CLI 为计划，真实 run/score 必须显式开启。未完成项不从分母移除；judge 可基于同一原回答重试，保留旧尝试。
- 入口与操作命令见 [suite README](../../../evals/memory/README.md)。本 unit 不修改生产启动、RPC、工具或 current 记忆行为；no spec delta，长期评测契约在 suite README。

## Test ownership

搜索了 `packages/dsh-integration/tests/{dreaming-runtime,dreaming-incomplete-runtime,memory-runtime,communication-native}.test.ts` 和现有 `evals/`。保留全部既有产品机制覆盖；新评测接口的历史导入、跨环境恢复与控制区隔离此前没有同因覆盖。

| Risk | Owner / seam | Disposition |
|---|---|---|
| 原历史保真、标注与未来问题隔离 | `evals/memory/dataset.test.ts` 数据边界 | 新增最低层覆盖 |
| opaque 候选、失败分母、重评分保留 | `evals/memory/runner.test.ts` 公共候选协议 | 新增；两种状态表示复用同一 Runner |
| 默认计划零出站、显式开关 | `evals/memory/cli.test.ts` 真实 CLI 子进程及本地监听端点 | 新增用户入口覆盖 |
| 原生映射、真实记忆消费、冷答题越界、预算与清理 | `packages/dsh-integration/tests/evaluation-runtime.test.ts` 真实 DSH/provider seam | 新增适配器集成覆盖；不替代已有 Dreaming 产品测试 |
| 固定官方规则与 judge HTTP 失败 | `evals/memory/judge.test.ts` 固定模板/本地 HTTP | 新增评分接口覆盖 |

## Validation before independent gates

- 首次导入验证暴露 DSH 原生 turn/step 从 1 起编号；按锁定原生格式修正，未修改 DSH。
- 模型输入是冻结对象；预算在公开 `agent/request` 配置边界施加，`llm/stream` 只捕获和核验，不改写已组装消息。
- `pnpm --filter @nano/dsh-integration... --filter @nano/personal-assistant... build`：通过。
- `pnpm exec tsc -p evals/memory/tsconfig.json`：通过。
- `pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts`：5 files / 13 tests 通过；包括真实运行时完整准备/两次冷答题、请求上限、挂起 provider 超时终止。
- `pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json`：通过，1 题 / 2 会话 / 4 消息，零模型调用；仅合成示例。
- 独立门禁与本地全量检查随后记录。

所有测试 runtime 使用独立临时目录并由 adapter 终止；默认回归清理临时数据。未触碰生产身份、生产配置或公开 IM。单次排障证据在 `/tmp/feat677-native-debug/`，仅为可清理本地产物。
