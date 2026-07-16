# M11 — Session capability 与 IM transport owner 收口

## Goal

删除 Round 4 code review 识别的两处 owner 漂移源：foreground binder 与 unattended shim 必须复用同一 Agent session capability projection；shadow/config-sync/bootstrap 必须依赖中立的公开 IM HTTP transport seam，而不是跨 owner 导入私有 helper。同步关闭 PR whitespace gate。

## Exit criteria

- [ ] foreground 与 cron/heartbeat 从同一 typed snapshot projection 得到 prompt/tools/features/skills；scenario metadata/title 差异不复制 capability 规则。
- [ ] restricted、empty 与 `None` skills/tools/features 在两类 session 中语义一致，既有 session reuse 不变。
- [ ] IM base URL/header 归一化迁入中立公开 owner；config sync、shadow sync、main 不再跨 owner import underscore helper。
- [ ] architecture/deletion tests 阻止 session capability 双投影与私有 IM transport import 回归。
- [ ] Round 4 三处 EOF 空行清理完成，`git diff --check main...HEAD` 无输出。
- [ ] 聚焦测试、`ruff check .` 与 `pytest -m "not e2e"` 全部通过。
- [ ] milestone 分支合入并推送 `unit/refactor-463`，随后清理 milestone worktree/branch。

## Test strategy

- session composition contract：同一 snapshot 在 foreground/unattended 场景下 capability kwargs 完全一致，仅允许 title/metadata/scenario 输入差异。
- architecture contract：禁止 binder/main 重复调用 capability resolver，禁止从 `agent_config_sync` 导入 IM HTTP 私有 helper。
- config-sync/shadow/bootstrap 现有 HTTP 行为回归。
- `git diff --check main...HEAD` 作为永久发布检查证据。
- 非前端改动，无 frontend build/test 要求。

## Roadpoints

### R1 — Shared Agent session projection

- [x] C1 红测：锁定 foreground/unattended capability parity 与 deletion guard。
- [x] C2 实现：抽取 typed projection 并迁移两个 owner。
- [x] C3 文档：记录 capability 边界与验证证据。

### R2 — Neutral IM HTTP transport seam

- [ ] C1 红测：锁定私有跨 owner import 删除与现有 HTTP 归一化行为。
- [ ] C2 实现：迁移公开 helper 并更新所有 consumer。
- [ ] C3 文档：记录 owner/deletion 证据并清理 whitespace gate。
