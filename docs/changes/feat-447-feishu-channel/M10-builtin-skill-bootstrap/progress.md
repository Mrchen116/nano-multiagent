# feat-447-M10 — Progress

## R1 — 内置 skill 资源与 bootstrap 安装

- Context: 历史 `skills/feishu-doc.md` 是 repo 根目录 flat 文件，既不符合 `SkillRegistry` 的 `<skill>/SKILL.md` 发现模型，也不会稳定进入 pip 安装后的 Gateway 运行态。
- Decision: 新增 `personal_assistant.builtin_skills` 包，把 `feishu-doc` 迁移到 `src/personal_assistant/builtin_skills/feishu-doc/SKILL.md`；新增 `install_builtin_skills()`，Gateway `build_runtime()` 早期调用它把缺失的内置 skill 复制到 `~/.nanoassistant/skills`；`pyproject.toml` 声明 `personal_assistant = ["builtin_skills/**"]` package data。
- Rationale: 包内资源是发布来源，用户全局 skill root 是 PA kernel 的运行时 discovery 来源。安装策略只在 `SKILL.md` 缺失时复制，已存在的用户自定义 skill 不覆盖；启动期安装失败只记录 warning 并继续，避免本机文件权限问题阻断非文档主路径。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py` -> 3 passed；`pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/unit/agent/test_runtime_skill_resolution_same_source.py` -> 16 passed。
  - Entry: Gateway 启动入口 `build_runtime()` 已接入 `install_builtin_skills()`；真实进程启动与飞书入站证据在 R3 live-critical 统一记录。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单测覆盖缺失复制、已有用户 skill 不覆盖、package data 声明；live-critical 不作为永久测试，R3 记录一次性证据。
  - Visual/Interaction: N/A
- Rollback: revert `2139df27` 并恢复 flat `skills/feishu-doc.md`，再 revert 本文档提交。
- Commits: C1=3f8dfff0, C2=2139df27, C3=TODO
- Next: R2

## R2 — Feishu-bound allowlist 写回

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R3

## R3 — skill 同源可见与 live-critical 验证

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: 本 milestone 完成
