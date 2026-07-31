# feat-485-M1: 实施记录

> 状态：Completed history。

## Context

feat-475 把 Gate 2 固化为“每轮新 reviewer + 每轮 full + 覆盖旧报告”。feat-484 的真实连续 review 暴露了重复冷启动和重复取证成本。本 milestone 将 review 上下文生命周期、检查范围路由和报告历史一起调整，避免只优化其中一项后仍由其他入口绕过。

## Decision

- Reviewer 生命周期归 design-author 编排，但一个 unit 只创建一次；R2+ 只唤醒同一 target。
- Review mode 归 reviewer 判断，author 只传修订事实和 Resolution。
- 轻量轮以 `rechecked` / `retained` 证明未降低审查维度。
- `design-review.md` 按 Round 追加；每轮记录时区时间、耗时和稳定 issue ID。
- `change-orchestrator` 不消费 `design-review.md`；Gate 2 由 design-author 在交接前收口。
- 不记录 sha256、byte length 或完整产物 manifest，保留 agent 可直接理解和执行的最小契约。
- 根级 `AGENTS.md` 不承载 design-review 细节；流程规则只落在相关 skill 与 `docs/changes/readme.md`。同时撤回 readme 中与本需求无关的 milestone skeleton 改写。
- design-author 每次进入 Gate 2 先读取已有 Round：有历史则恢复 reviewer 并从 `N+1` 继续，无历史才创建 R1。
- 轻量 mode 同时收缩检查与报告：closure 只写 closure 证据，delta 只展开受影响项；不重复全量台账。

## Rationale

同一 reviewer 的热上下文能省掉每轮重新理解 unit 和代码的主要成本；把 mode 交给掌握审查证据的一方，避免 author 为了赶进度低估影响。按 Round 记录时间、问题和 Resolution 已足以支持续审与复盘，不需要再引入机器快照协议。

## Evidence

- Design review canary：
  - Round 1：`full`，`8m37s`，`2 CRITICAL / 3 WARNING`。
  - Round 2：复用 `/root/design_reviewer_485`，由 reviewer 自主选择 `full`，`3m58s`，`Approved — 0 CRITICAL / 0 WARNING`。
- Skill validation：
  - `change-design-author`: `Skill is valid!`
  - `change-design-reviewer`: `Skill is valid!`
- Tests：
  - `tests/contract/test_design_review_round_contract.py`: 按用户要求删除；skill 文案不建立字符串断言契约。
  - `tests/contract/test_change_skill_archive_contract.py` + `tests/unit/test_skill_registry_frontmatter.py`: `9 passed`
- `git diff --check`: passed。

## Rollback

恢复两个 skill 和两个流程入口的 feat-475 口径即可回退调度行为；已经形成的 `design-review.md` Round 历史不删除。
