# feat-349-M6: wire-default-session-metadata — Tasks

> Post-acceptance fix milestone（round 2，orchestrator 亲自实施）。M5 worker E2E 时绕过 CLI 入口暴露的 wire 缺口。

## 目标

修 `default_session_metadata` 死接线问题：`bootstrap_product` 把 workspace `config.yaml` 的 `self_evolution` 配置写入 `ResolvedProductConfig.default_session_metadata`，但 `SessionService` 从不读它，CLI 走 `POST /v1/sessions`（无 metadata）创建的 session 全走 hook 默认值（interval=10），workspace config 形同虚设，feat-349 自进化在真实产品入口几乎不触发。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | SessionService 接收 + merge `default_session_metadata` | DONE |
| R2 | `app.py` 注入 `resolved_product.default_session_metadata` | DONE |
| R3 | 单测覆盖 + E2E 验证 `.nanocode/skills/` 真落盘 | DONE |

## 退出标准

- `SessionService.__init__` 接收 `default_session_metadata`；`create_session` 按"default 底、caller 顶层 key 覆盖"shallow merge；
- `create_app` 把 `resolved_product.default_session_metadata` 透传给 `SessionService`；
- 新增单测：构造时传 default → caller 不传 metadata → 落盘 metadata == default；caller 传部分顶层 key → 仅该 key 覆盖；
- E2E：在 workspace 写 `.nanocode/config.yaml`（`skill_nudge_interval: 1`），通过 server 创建 session 后，`session.metadata.self_evolution` 含该 interval；发一条教学性消息，`<workspace>/.nanocode/skills/<name>/SKILL.md` 真出现一个由 fork agent 写入的文件。
