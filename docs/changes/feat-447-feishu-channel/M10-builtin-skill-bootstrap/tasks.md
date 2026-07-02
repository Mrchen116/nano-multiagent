# feat-447-M10: builtin-skill-bootstrap — Tasks

> 对齐: ../design.md feat-447-M10 行

## 目标

把历史 flat `skills/feishu-doc.md` 迁移为随 personal_assistant package 发布的目录型内置 skill，并在 Gateway 启动时安装到用户全局 skill root。Feishu 绑定 agent 即使配置了显式 skills allowlist，也能自动启用 `feishu-doc`，且 capabilities、prompt preview、list_skills、真实 session 注入都走同一个 skill resolver。

## 退出标准

- [ ] `skills/feishu-doc.md` 迁移为 `src/personal_assistant/builtin_skills/feishu-doc/SKILL.md`，并纳入 package data。
- [ ] Gateway 启动检查 `~/.nanoassistant/skills/feishu-doc/SKILL.md`，缺失则复制内置版本，已有用户 skill 不覆盖。
- [ ] enabled `feishu:<agent_id>` channel 绑定的 agent 若显式配置 skills allowlist，会自动补 `feishu-doc` 并写回本地 config；非 Feishu-bound agent 不补。
- [ ] capabilities、prompt preview、list_skills、真实 session skill 注入同源可见 `feishu-doc`。
- [ ] 单测覆盖缺失复制、不覆盖已有用户 skill、Feishu-bound allowlist 自动补并写回、prompt preview/list_skills/session 注入同源。
- [ ] 相关窄测与 `pytest -m "not e2e"` 通过，或记录环境 blocker。
- [ ] live-critical：真 Gateway 启动路径 + 真实飞书 1:1 入站证明 `feishu-doc` 可见并能给出云文档授权/创建指引。

## 测试策略

- 被测行为（来自退出标准）：内置 skill 包资源安装；用户已有同名 skill 不覆盖；Feishu-bound 显式 allowlist 自动补 `feishu-doc` 并持久化；非 Feishu-bound agent 不补；capabilities、prompt preview、list_skills、runtime session skill resolution 同源可见 `feishu-doc`；真实 Gateway + 真实飞书入站 live smoke。
- 已有测试在：扩展 `tests/unit/personal_assistant/test_gateway_upstream_reporter.py`、`tests/unit/personal_assistant/test_local_store.py`、`tests/unit/agent/test_runtime_skill_resolution_same_source.py`；新建 `tests/unit/personal_assistant/test_builtin_skill_bootstrap.py`，理由是 bootstrap helper 是新的 PA 启动行为，现有文件没有安装/写回生命周期测试承载点。
- 落层/目录/marker：unit tests，无 marker；真实飞书/Gateway smoke 是一次性验收证据，不进入测试套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：干净 HOME Gateway 启动日志、生成的 `~/.nanoassistant/skills/feishu-doc/SKILL.md` 路径、capabilities/config 输出、`lark-cli im +messages-send --as user` 命令输出、Gateway 日志 nonce。

前端 UI：N/A。

## Roadpoints

### R1 — 内置 skill 资源与 bootstrap 安装

- 状态: DOING
- 步骤: 迁移 flat skill 到 `src/personal_assistant/builtin_skills/feishu-doc/SKILL.md`；新增/接入 bootstrap helper；配置 package data。
- 验证: 单测证明缺失复制、已有用户 skill 不覆盖；package data 配置存在；窄测通过。

### R2 — Feishu-bound allowlist 写回

- 状态: TODO
- 步骤: Gateway 启动早期识别 enabled `feishu:<agent_id>` channel；显式 allowlist 自动补 `feishu-doc`；写回本地 config；不影响未绑定 agent。
- 验证: 单测覆盖补入、持久化、非 Feishu-bound 不补。

### R3 — skill 同源可见与 live-critical 验证

- 状态: TODO
- 步骤: 覆盖 capabilities、prompt preview、list_skills、runtime session skill 注入同源可见 `feishu-doc`；跑 Gateway 真启动路径与真实飞书 1:1 smoke。
- 验证: 相关单测、`pytest -m "not e2e"`、真实 Gateway + `lark-cli --as user` 证据。
