# Design Review

## Round 1

- Reviewer target: 独立 `design_review`（Sol），`7f1872f33`
- review_mode: full
- mode_reason: 首轮，覆盖需求、设计、契约影响和 M1
- started_at: 2026-11-23T13:23:12+09:00
- completed_at: 2026-11-23T13:23:43+09:00
- duration: 31s
- Verdict: Issues Found（0 CRITICAL / 2 WARNING）

### Coverage

- 首文档两项场景由用户级注册和可编辑 checkout 覆盖。复用客户端的 skill 发现机制与现有 Git 工作方式合理。通用素材归独立库，项目规则、产品资产和历史评测各留在原归属。
- 核对 Nano 的实际入口 `AGENTS.md`、`docs/changes/README.md`、`.claude/skills` 别名以及 CI 归档步骤和测试。当前编号工具以 Git common dir 下的 `nano-multiagent/change-unit-ids` 保存跨 worktree 预留，保留该状态符合首文档。M1 的编号兼容测试应从旧预留值高于已有目录的场景执行。
- 变化限开发流程，无产品 spec delta 或 UI 原型。M1 只需用轻量 Sol 跨仓试用核对真实技能发现、项目规则与新会话读到的修订。

### Issues

- **R1-W1 — 明确 CI 与独立库测试的分工。** `design.md` 说 CI 无需安装，但当前 `tests/contract/test_change_skill_archive_contract.py` 直接读取迁出的 PR 模板，`tests/unit/test_change_spec_author_next_unit_id.py` 直接加载迁出的编号脚本。只换文档链接会使干净 checkout 的测试失败。请明确模板与编号工具的测试随资产迁移，并保留 Nano 的独立归档契约。用未注册外部技能的 Nano checkout 验证仓内检查。
- **R1-W2 — 明确两个仓的切换顺序及恢复点。** `design.md` 仅声明各自提交。通用入口链接和项目本地删除一旦先交付，外库 URL 尚不可用或安装冲突时，Nano 没有原入口。请写明先让外库版本可取并验证安装，再移除 Nano 副本，以及切换失败时恢复旧入口的最小方式。当前主机的 `~/.claude/skills` 还指向 `~/.codex/skills`，装配验收应包含同一注册目录重复安装，确认同一来源的已有链接不会被报成冲突。

### Author Resolutions
- R1-W1 accepted，设计补充了编号和模板测试的迁移、Nano 归档与文档检查的保留位置。
- R1-W2 accepted，设计补充外库先发布验证、失败保留/恢复入口以及同源幂等检查。

## Round 2

- Reviewer target: 独立 `design_review`（Sol），`0d45fb2f0`
- review_mode: closure
- mode_reason: 修订限于原两项问题，其他范围沿用 Round 1 证据
- started_at: 2026-11-23T13:24:15+09:00
- completed_at: 2026-11-23T13:24:24+09:00
- duration: 9s
- Verdict: Approved（0 CRITICAL / 0 WARNING）

### 历史问题闭环

- **R1-W1 closed。** Author 将编号和模板测试归入独立库。核对修订，Nano 保留独立归档检查、CI 接线和本地技能链接检查，CI 无需安装或跨库下载测试材料。
- **R1-W2 closed。** Author 明确外库先可获取并实测，再交付 Nano PR。核对修订，安装失败保留旧入口，合入后可撤销切换提交，两宿主指向同一源时重复注册应成功。
