# feat-502-M1 Progress

## Context

- unit branch: `unit/feat-502`
- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-502`
- implementation base: `e1691085407c45d4ef311869a903e543d030b199`
- design deviation: none

## Evidence

### Implementation baseline

- Claim: 目标 bootstrap/lifecycle/capability 测试在实施前基线可信。
- Baseline: `unit/feat-502` at `e1691085407c45d4ef311869a903e543d030b199`.
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py tests/unit/personal_assistant/test_gateway_pid_lifecycle.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py`.
- Result: PASS, 34 passed; 2 third-party deprecation warnings.
- Locator: pytest terminal output in the implementation session.
- Limit: 不证明目标刷新语义或真 LLM 产品问答，这些由 Red/Green 和真栈验收覆盖。

### Red

- Claim: 旧实现不满足产品托管 skill 完整刷新、失败恢复和产品手册可达性。
- Baseline: working tree based on `e1691085407c45d4ef311869a903e543d030b199`, only test changes applied.
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py`.
- Result: EXPECTED FAIL, 4 failed / 7 passed；失败分别落在旧同名不覆盖、缺少失败恢复继续、缺少 `nanoassistant-docs` capability 与 `skill_view` 正文。
- Locator: pytest terminal output in the implementation session.
- Limit: Red 只证明 seam 能暴露目标差异，不证明实现正确。

### Green and focused quality

- Claim: 内置 skill 刷新契约、产品手册发现/default-on/正文读取和 Gateway 启动链路已在聚焦层通过。
- Validated tree: uncommitted M1 implementation on `unit/feat-502`, based on `e1691085407c45d4ef311869a903e543d030b199`.
- Method: focused pytest for bootstrap/lifecycle/reporter, skill-creator `quick_validate.py`, Ruff check/format-check, `scripts/docs-check`, and `git diff --check`.
- Result: PASS；36 passed（2 个第三方 warning）；`Skill is valid!`；Ruff、docs-check（208 maintained Markdown sources / 66 required routes）与 diff check 均通过。
- Locator: implementation session terminal output; source manual at `src/personal_assistant/builtin_skills/nanoassistant-docs/SKILL.md`.
- Limit: 尚未覆盖真 IM/Gateway/LLM 用户旅程。

### Impact regression

- Claim: M1 未破坏 PA 单元行为和跨包架构红线。
- Validated tree: same uncommitted M1 implementation.
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant` and `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract`.
- Result: PASS；834 PA unit tests（2 个第三方 warning）和 136 contract tests。
- Locator: implementation session terminal output.
- Limit: 不替代后续真栈验收、独立 review 或仓库 CI。

### Isolated real-stack journey

- Claim: Gateway 启动会刷新全部产品托管 skill、保留非内置名称，并且真实 IM 用户可以让仅启用产品手册的 Agent 调用 `skill_view` 后回答产品问题。
- Validated commit: `c19707871` (`feat(feat-502/M1): add PA product docs skill`).
- Runtime: worktree-local random IM port, copied Gateway config, isolated HOME / workspace / node identity; live proxy model `deepseek:deepseek-v4-flash`.
- Method: 预置 stale `lark-doc` 目录与 `my-custom-skill` 后执行 `scripts/e2e-up.sh`; 通过 IM API 创建只选择 `nanoassistant-docs`、只允许 `skill_view` 的 Agent，发送首次启动与 Gateway ready 问题并观察 WS 工具/消息事件。
- Result: PASS；`lark-doc` 旧残留被删除，`nanoassistant-docs` 安装，`my-custom-skill` 原文保留；收到 completed `skill_view(name=nanoassistant-docs)`，最终回答同时包含 IM→Gateway 启动顺序和 started 不代表已可聊天语义。
- Locator: isolated runtime logs under the unit worktree during acceptance; terminal marker `REAL_PRODUCT_DOCS_JOURNEY_PASS`, agent `docs6cd5c5`.
- Limit: 一次性真栈实例和日志不提交；最终交付前必须清理进程与 runtime 文件。

### Code review fixes

- Finding: 临时 backup 清理失败时，旧目录留在 skill root 下并被 `SkillRegistry` 优先发现；不同 config 的 Gateway 共享 HOME 并发刷新时，后失败者可删除先成功者的新目录并恢复旧版。两项均经 finder 与独立 verifier 复现确认为 `CONFIRMED`。
- Red: 在 `c78d5df89` 上新增 discovery 与 root-lock 回归测试，结果 EXPECTED FAIL（2 failed）：registry 实际定位到 `.nanoassistant-docs.backup-*`，且安装流程不存在共享 root lock。
- Fix: staging/backup 统一置于 registry 排除的 `.archive` 下；整次 bundle 刷新持有 user-global skill root 的 `fcntl` 跨进程锁。
- Green: bootstrap 文件 13 passed；bootstrap/lifecycle/reporter 聚焦集 38 passed；PA 单测 836 passed，contract 136 passed（PA 聚焦/全量各有 2 个第三方 warning）；相关 Ruff check/format-check、docs-check（211 maintained Markdown sources / 66 required routes）与 `git diff --check` 通过。
- Limit: 提交整合后还需执行受影响门禁 closure 和最终 CI。

## Commits

- `c19707871` — `feat(feat-502/M1): add PA product docs skill`.
