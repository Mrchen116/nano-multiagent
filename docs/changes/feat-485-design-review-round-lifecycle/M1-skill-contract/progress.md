# feat-485-M1: 实施记录

## Context

feat-475 把 Gate 2 固化为“每轮新 reviewer + 每轮 full + 覆盖旧报告”。feat-484 的真实连续 review 暴露了重复冷启动和重复取证成本。本 milestone 将 review 上下文生命周期、检查范围路由和报告历史一起调整，避免只优化其中一项后仍由其他入口绕过。

## Decision

- Reviewer 生命周期归 design-author 编排，但一个 unit 只创建一次；R2+ 只唤醒同一 target。
- Review mode 归 reviewer 判断，author 只传修订事实和 Resolution。
- 轻量轮以 `rechecked` / `retained` 证明未降低审查维度。
- `design-review.md` 按 Round 追加；每轮记录时区时间、耗时、稳定 issue ID、完整受审 manifest。
- `change-orchestrator` 在真实 worker 派发边界独立消费最新 Round，避免 producer 自证后被跨会话绕过。

## Rationale

同一 reviewer 的热上下文能省掉每轮重新理解 unit 和代码的主要成本；把 mode 交给掌握审查证据的一方，避免 author 为了赶进度低估影响。完整 manifest 与 orchestrator consumer 则保证轻量 review 不以 stale approval 为代价。

## Evidence

- Design review canary：
  - Round 1：`full`，`8m37s`，`2 CRITICAL / 3 WARNING`。
  - Round 2：复用 `/root/design_reviewer_485`，由 reviewer 自主选择 `full`，`3m58s`，`Approved — 0 CRITICAL / 0 WARNING`。
  - Round 2 写入前的 25,616 字节历史前缀 sha256 保持一致。
- Skill validation：
  - `change-design-author`: `Skill is valid!`
  - `change-design-reviewer`: `Skill is valid!`
  - `change-orchestrator`: `Skill is valid!`
- Tests：
  - `tests/contract/test_design_review_round_contract.py`: `5 passed`
  - `tests/contract/test_change_skill_archive_contract.py` + `tests/unit/test_skill_registry_frontmatter.py`: `9 passed`
- `git diff --check`: passed。

## Rollback

恢复三个 skill 和两个流程入口的 feat-475 口径即可回退调度行为；已经形成的 `design-review.md` Round 历史不删除。
