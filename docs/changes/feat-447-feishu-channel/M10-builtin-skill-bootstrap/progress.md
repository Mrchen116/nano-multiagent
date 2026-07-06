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
- Commits: C1=3f8dfff0, C2=2139df27, C3=a77caeb5
- Next: R2

## R2 — Feishu-bound allowlist 写回

- Context: Feishu channel 可用但 agent 配了显式 `skills` allowlist 时，运行时只注入 allowlist 内 skill；如果不自动补 `feishu-doc`，用户从飞书请求云文档操作时 session 看不到内置 skill。
- Decision: 在 config 层新增 `ensure_feishu_doc_skill_for_feishu_agents()`：从 enabled `feishu:<agent_id>` channel 推导绑定 agent，只对已有非空 skills allowlist 且缺少 `feishu-doc` 的 agent 追加该 skill。`build_runtime()` 在安装内置 skill 后调用该 helper，变化时用 `save_local_config()` 写回同一个本地 config，并继续用更新后的 `LocalConfig` 构建运行时。
- Rationale: 绑定关系来自 Gateway 本地 channel config，是启动时最早且最权威的来源；只处理非空 allowlist 保留“未配置 skills = 全部可发现 skills”的既有语义，非 Feishu-bound agent 不被污染。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py` -> 4 passed；`pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py tests/unit/personal_assistant/test_local_store.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/unit/agent/test_runtime_skill_resolution_same_source.py` -> 62 passed。
  - Entry: 单测通过真实 `build_runtime(load_local_config(config_path))` 启动装配点验证，重读本地 config 后 `feishu-agent.skills == ("existing-skill", "feishu-doc")`，`plain-agent.skills == ("existing-skill",)`。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py::test_gateway_startup_persists_feishu_doc_for_feishu_bound_allowlist` 覆盖启动写回和非绑定 agent 不补。
  - Visual/Interaction: N/A
- Rollback: revert `3aca12cf` 并删除对应 C1 测试断言，再 revert 本文档提交。
- Commits: C1=aaca4fe8, C2=3aca12cf, C3=5ed782ef
- Next: R3

## R3 — skill 同源可见与 live-critical 验证

- Context: R1/R2 已让内置 `feishu-doc` 进入 Gateway 启动路径并写回 Feishu-bound agent allowlist；剩余风险是 capabilities、prompt preview、`list_skills`、真实 session skill 注入是否真的使用同一个 skill resolver，以及真实飞书入站链路是否能触发 agent 引用 `feishu-doc`。
- Decision: 新增同源单测覆盖 PA kernel capabilities、prompt preview、`kernel.list_skills()` 与 runtime session skill resolution；在真实 Gateway 启动路径中用临时移走全局 `~/.nanoassistant/skills/feishu-doc` 的方式验证 bootstrap 复制，并用真实 `lark-cli im +messages-send --as user` P2P 消息触发 agent 回复。
- Rationale: 同源单测防止未来 capabilities/prompt/session 各走各的 resolver；live-critical 保留一次真实飞书链路证据，覆盖 webhook/IM/Gateway/session/LLM/飞书回发的集成风险。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py` -> 5 passed；`pytest -q tests/unit/personal_assistant/test_builtin_skill_bootstrap.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/unit/agent/test_runtime_skill_resolution_same_source.py` -> 18 passed；`pytest -m "not e2e"` -> 3246 passed, 1 skipped, 22 deselected, 20 warnings in 143.04s。
  - Entry: live config `/Users/czj/Repos/nano-multiagent/.worktrees/feat-447-M10/.gateway-config.yaml` 使用 `feishu:default-agent.settings.appId = cli_aac9315ef3f9dbda`，`lark-cli auth status --json --verify` 返回相同 `appId`，bot open id `ou_b33ae16df1338a00a77d4cdbec653b71`，user open id `ou_e6d1591026cfdac8d131eb1fdd71bdb9`。启动前临时移走全局 user skill；Gateway 启动后生成 `/Users/czj/.nanoassistant/skills/feishu-doc/SKILL.md`，local config 写回 `default-agent.skills = [change-spec-author, feishu-doc]`。IM `GET /im/v1/nodes/wt-feat-447-M10-live/capabilities` 输出 `node_capability_has_feishu_doc True`，`GET /im/v1/agents/default-agent/capabilities?node_id=wt-feat-447-M10-live` 输出 `agent_capability_has_feishu_doc True`。真实飞书发送命令：`lark-cli im +messages-send --as user --user-id ou_b33ae16df1338a00a77d4cdbec653b71 --text "feat-447-m10-live-20260702-200233 请使用 feishu-doc 说明如何创建飞书文档；如果未授权，请给出授权指引"`；输出 `message_id = om_x100b6b517b5164b0b39585855bc2f7b`, `chat_id = oc_1906eead0189484ce5ea8a4c245400a6`, `create_time = 2026-07-02 20:02:33`。随后 `lark-cli im +chat-messages-list --as user --chat-id oc_1906eead0189484ce5ea8a4c245400a6 --start 2026-07-02T20:02:00+08:00 --end 2026-07-02T20:08:00+08:00 --order asc` 返回 app 回复 `message_id = om_x100b6b517934c0b8b4bd4aa87ed1f7e`, `create_time = 2026-07-02 20:03`，内容引用 `feishu-doc` skill 并给出 `feishu-cli auth login` / `feishu-cli auth status` 授权指引和创建文档命令示例。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: live Gateway/IM 前台会话在 127.0.0.1:65083 启动并已停止；IM 日志包含 `POST /im/v1/conversations/external/find-or-create` 201、`POST /im/v1/conversations/.../messages` 201、capabilities 200。停止后 `lsof -nP -iTCP:65083 -sTCP:LISTEN` 无输出；`.im.pid` / `.gateway.pid` 已删除；临时移走的用户全局 `feishu-doc` skill 已恢复。
  - Visual/Interaction: N/A
- Rollback: revert `020eed33` 删除启动日志，revert `24563421` 删除同源单测，再保留 R1/R2 或整体 revert 本 milestone；live-critical 仅为一次性证据，无运行时状态需回滚。
- Commits: C1=24563421, C2=020eed33, C3=this commit
- Next: 本 milestone 完成
