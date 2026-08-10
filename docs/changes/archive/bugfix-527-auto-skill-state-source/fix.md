# bugfix-527: 自动 Skill 历史选择与来源修正

## Relations

- Related: feat-349
- Related: feat-446
- Related: feat-502
- Related: feat-519

## 原始报告

> 这个问题先别管。**历史状态异常**：两个自动生成的 Skill 原先可用，后来没有保留在显式名单中。
> **来源记录错误**：自动生成的 Skill 被记录成了 F1 手工创建。
>
> 这两个是明确问题对吧。先解决这两个。“两个自动生成的 Skill 原先可用，后来没有保留在显式名单中。”这个是为啥

> 所以以后自动生成的是不是就会在allowlist中？我想问这是之前历史遗留的问题，还是说新代码还有问题

> 如果新代码没问题，直接改下数据库就行，不用改代码

> 对

## 澄清记录

- Q1: 是否同时把现有两个 Skill 的来源记录从 `F1` 回填为 `F3`？
  A(原话): 对
  Agent 解读: 只回填已经由运行日志确认来自后台自动 Review 的 `remote-host-health-check` 与 `forall-prod-machine-status`，不扫描或改写其他历史 Skill。

## 现象 / 复现

2026-08-03，`forall` 的两次“看看两个机器啥状态”会话分别达到后台 Skill Review 阈值。LLM Bridge 原始响应显示，两个后台 Review 随后分别调用 `skill_manage(action="create", scope="agent")` 创建：

- `remote-host-health-check`；
- `forall-prod-machine-status`。

两者创建时，`forall` 尚未保存非空 Skill 名单，按当时的默认发现语义立即可用；使用记录显示它们随后各被成功读取四次。之后保留下来的配置从空/缺席名单演变为只含 PA 全局内置 Skill 的非空名单，两个工作区 Skill 不在其中。旧版本按“空名单为默认发现、非空名单为显式 allowlist”推断选择意图，因此它们退出该 Agent 的有效 Skill 集合。当前设置页如实显示 `WORKSPACE 0/2`。

现有生产备份能证明：2026-08-03 的 `forall` 配置尚无持久化 Skill 名单；2026-08-06 已变为只含 `nanoassistant-docs` 与 `lark-doc` 的非空名单；2026-08-09 前又扩为完整 PA 全局内置 bundle。第一条全局 Skill 由哪个历史入口写入已无配置操作审计可查，不能继续归因。2026-08-10 的配置操作只把既有非空名单显式标记为 `explicit_allowlist`，没有在该次操作中删除两个工作区 Skill。

当前版本已经用独立的 `skills_selection_mode` 区分默认发现与显式 allowlist。聚焦回归确认：成功创建 Skill 会产生 `skill_created` 事件；事件能到达 Gateway handler；`default_discovery` 由发现机制立即看到新 Skill；`explicit_allowlist` 会把新名称追加到名单。因此“生成后退出名单”是该 Agent 的历史持久状态，不是当前 Allowlist 代码缺陷。本单只修复 `forall` 的确认状态，不增加扫描式自动启用，不扩大其他 Agent 的显式名单。

第二个现象仍可在当前代码稳定复现：后台 self-improvement Review 调用 fork 时没有声明 `skill_creation_source=F3`；fork 只继承父会话 metadata 并补 `run_origin=background_task`。`skill_manage(create)` 建立使用记录时读取不到来源字段，遂按默认值 `F1` 持久化。因而自动 Review 创建的 Skill 在统计中被误报为手工从零创建。

## 根因

历史选择异常来自旧选择模型的表达能力不足，而非当前创建链失效：旧配置只有 Skill names，没有独立的选择模式。创建时的空/缺席 names 表示“按发现集合全部可用”，后续任何把它写成非空子集的配置变化都会同时把语义收窄为显式 allowlist。两个自动生成 Skill 只依赖默认发现生效，并未物化进 names，因此在该历史收窄中被排除。feat-519 已用 `skills_selection_mode` 消除这项歧义，并要求创建事件在默认模式下保持发现、在显式模式下追加名称。修复必须保留显式 allowlist 的权威性，不能把磁盘上所有既有工作区 Skill 扫描式补回。

来源错误来自 F3 意图没有贯穿后台 fork 的创建边界。Skill 生命周期原本区分 F1 手工创建与 F3 per-turn 自动 Review 创建；但现有实现只在使用记录层消费 `skill_creation_source`，没有由 self-improvement 生产者向 fork metadata 写入 `F3`。现有测试分别覆盖 Review 触发、`skill_manage` 来源消费和 Skill 使用统计，却没有覆盖“后台 Review → fork → create → usage record”的来源贯通，所以默认 `F1` 未被发现。

修复必须同时满足：未来仅由 Skill 自动 Review 创建的记录标记为 `F3`；memory-only Review 不虚构 Skill 来源；其他普通 fork、用户创建和历史蒸馏语义不变；现有两个已确认记录只做定向回填。

## 修复

后台 self-improvement 在 Skill-only 与 Skill + Memory Combined Review 启动 fork 时，显式提供仅作用于该 side-chain 的 `skill_creation_source=F3`。通用 `fork_conversation` 增加可选 `metadata_overrides`，先继承父会话 metadata、再应用本次 override，并继续强制 `run_origin=background_task`、移除陈旧 `tool_call_id`；因此真实 `skill_manage(create)` 继续从既有 `session_metadata` 消费来源并把记录写成 F3。

memory-only Review 不提供该 override；普通 fork 不凭空产生 Skill 来源；普通用户 `skill_manage(create)` 仍由既有缺省语义记录为 F1。未修改 Skill Allowlist、历史蒸馏/F4 逻辑、生产配置或任何既有 `.usage.json`。

Reviewer fix1 进一步收窄了消费边界：fork metadata 仍携带 F3，供本次 `skill_manage(create)` 建立自动 Skill 记录；`skill_view` 不再用当前 session 的 creation provenance 推断被查看 Skill 的历史来源。无 usage 记录的手工/遗留 Skill 首次查看时沿用 F1，已有自动 Skill 的 F3/F4 记录不会被覆盖。

提交：

- `674d571b9` — 贯通自动 Skill Review 的 F3 来源；
- `38d114ece` — 锁定 memory-only、普通 fork、普通 create 的不污染边界；
- `2b9a99d91` — 把回归提升为真实 Kernel SDK 入口。
- `65d0cc0bc` — Reviewer fix1：仅 create 消费 creation provenance，view 保留既有来源语义。

## 验证

按“后台自动 Review 创建 Skill 后，usage 来源被错误记为 F1”的原始症状验证：回归先从当前生产链复现，Skill-only 与 Combined 两例均真实落盘为 `F1`，断言报错 `F1 != F3`；修复后同一条链改为从 SDK 公共入口执行 `build_kernel → create_session → submit → agent_end 后台 Review → fork → skill_manage(create) → .usage.json`，两个临时 Workspace 的记录均读回 `source=F3`：

```text
/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/integration/test_self_improvement_skill_source.py
2 passed
```

边界回归覆盖 memory-only Review 不注入来源、普通 fork 不虚构来源、普通用户 create 仍写 F1，并保留 usage / skill_view / F4 batch 既有语义：

```text
81 passed
All checks passed!  # changed-file Ruff
```

扩展门禁覆盖全部 unit + integration：

```text
2637 passed, 2 warnings in 143.47s
```

两条 warning 均来自既有 `lark_oapi` 依赖的 datetime / event-loop deprecation；没有测试失败。验证全程只使用 pytest 临时 Workspace，未读取或改写生产配置、远端 mini 或现有 `.usage.json`。

Reviewer fix1 在同一真实 SDK Review 中增加“查看无记录手工 Skill + 创建新自动 Skill”：修复前 Skill-only / Combined 两例都把手工 Skill写成 F3，精确失败为 `F3 != F1`；修复后分别落为 `manual-skill=F1`、`auto-review-skill=F3`。最低层回归同时确认普通首次 view 为 F1，已有自动 Skill 的 F3/F4 记录继续保持。聚焦矩阵 `82 passed`，changed-file Ruff 全绿；扩展 unit + integration 为 `2638 passed, 2 warnings in 497.18s`，warning 仍仅来自既有 `lark_oapi` 弃用提示。未改 Allowlist、生产状态或既有 usage sidecar。

代码审查在 `599d42d3c` 的 full diff 上确认了上述 `skill_view` 来源污染问题；定向修复后，closure 在 `37d28437b` 返回 `[]`。其后的源码增量只有两份测试文件的 Ruff 机械格式化，未改变断言或运行逻辑，因此审查结论保留到最终实现树。

最终本地 CI 以 `origin/main@48d19d8a` 为 base 执行：documentation integrity、`ruff check .`、`ruff format --check .`、`pytest -m "not e2e" -n 4 --dist worksteal` 全绿，其中 Python 为 `3184 passed`；前端 `npm audit --audit-level=critical` 通过，独占资源重跑 `npm run test` 为 `66 files / 640 tests passed`。并行重跑时曾出现与本单无前端改动无关的 5 秒超时，独占资源后同一原命令全绿，未改前端代码。

## 生产历史数据修复

在 Mac mini 上先对 IM SQLite、Gateway 配置和 `forall` usage sidecar 建立权限受限备份，并通过 SQLite `PRAGMA integrity_check`。随后短暂停止 Gateway，按已确认范围完成三项定向修改：

- `forall` 的 `explicit_allowlist` 在 Gateway 配置与 IM profile 中都从 28 项变为 30 项，只加入 `remote-host-health-check` 与 `forall-prod-machine-status`，每项恰好一次；
- 两个目标 Skill 的既有 usage 来源从 `F1` 回填为 `F3`，未扫描或改写其他 Skill；
- 重启 Gateway 后再次确认配置与 IM profile 完全一致、SQLite integrity 为 `ok`、IM HTTP 返回 200，`mac-mini` 与 `macbook-air` 两个节点均为 online。

该生产修复没有修改 Allowlist 代码；未来创建后的可用性继续由现有 `default_discovery` / `explicit_allowlist` 逻辑负责。
