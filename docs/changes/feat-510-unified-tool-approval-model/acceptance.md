# feat-510 — 验收报告

> 对齐: `spec.md` 的全部验收标准

> Validation snapshot: `eaaed4c3ec91c5359044ca6b47d3834e8388063f → 89197f46323803d413a012f83418d5dad03049ce`

## Round 1 — 2026-08-06

**Verdict:** `pass`

**Highest Required Action:** `pass`

## 用户旅程体验

本轮从干净的 unit worktree 接管隔离运行时，先执行
`./scripts/e2e-down.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-510`
清除既有 IM / Gateway 进程，再按 design Runbook 从 Web IM 客户端实际使用的 REST / WS
入口驱动真 IM、真 Gateway 与进程内 Kernel。LLM 外部上游使用仓库规定的 deterministic
recording fixture；它记录 Anthropic-compatible 请求体中的 `model`，并让旅程真实完成写工具、
续跑、权限升级和 Gateway 重启。

1. **显式统一模型与重启切换。** 两个 Agent 分别以 A、B 发起消息并完成工具调用；验收锚分别为
   `A → C → A`、`B → C → B`。把磁盘配置从 C 改为 D 后不重启，下一次仍使用 C；重启同一
   Gateway 后才使用 D。真实入口用例
   `test_configured_model_is_unified_and_changes_only_after_restart` 显示 `PASSED`。
2. **省略配置保持原行为。** 不配置审批模型时，两个 Agent 各自完成工具旅程，记录锚为
   `A → A → A` 与 `B → B → B`；
   `test_omitted_model_reuses_each_agent_model` 显示 `PASSED`。
3. **专用模型不可用时不降级。** C 的分类结果不可用后，Web IM 旅程收到既有
   `permission.request`，记录中没有用 A/B 再做分类；
   `test_classifier_failure_escalates_without_model_fallback` 显示 `PASSED`。无人值守分支以同一
   产品权限入口的 origin 矩阵补充核对，仍执行既有 unattended fallback。
4. **无效配置拒绝启动。** 从真实 PA foreground 入口启动未注册审批模型的 Gateway，启动被
   拒绝且错误点名 `llm.tool_approval_model` 与错误值；
   `test_unregistered_model_rejects_gateway_startup` 显示 `PASSED`。

端到端命令：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/e2e/critical_paths/test_tool_approval_model_critical_path.py
4 passed in 44.48s
```

跨运行来源补充命令：

```text
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/test_auto_mode_gate_hook.py -k 'configured_model_for_every_run_origin or configured_model_for_both_stages or classifier_failure_does_not_retry_with_another_model or unattended_origin_skips_ask'
7 passed, 18 deselected in 0.06s
```

该矩阵覆盖 `user`（Web IM 与外部渠道进入 Kernel 后的用户运行）、`heartbeat`、`cron`、
`subagent`，并补充覆盖两阶段分类与无人值守失败处理。它只作为非交互来源的补充证据；模型
选择和 Agent 正常续跑的主结论来自上面的真实 Web IM 真栈旅程。

验收结束后再次执行 `e2e-down.sh`；`.im.pid`、`.gateway.pid` 均不存在，本轮服务已关闭。

## Reference Artifacts Reviewed

N/A。本 unit 不改客户端面，spec/design 未引用原型、设计稿、reference screenshot 或视觉
must-match 契约。

## 问题清单

无 blocking、major 或 minor issue。

## 验收标准覆盖

### Requirement: PA 可统一指定自动工具权限分类模型 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 不同对话模型的 Agent 共用专用审批模型 | `spec.md` 同名 Scenario；`design.md` 决策 7 | 旅程 1：两个 Agent 分别从 Web IM 触发真实工具调用 | 真栈请求锚 `A → C → A`、`B → C → B`；对应 critical-path 用例 `PASSED` | pass | 分类统一为 C，Agent 模型没有被统一替换 |
| 所有 PA 运行来源遵守统一选择 | `spec.md` 同名 Scenario；`design.md` 架构总览 | 旅程 1 的 Web IM 真栈 + user/heartbeat/cron/subagent origin 矩阵 | Web IM critical path `PASSED`；四类 origin、两阶段分类补充矩阵 7 项全绿 | pass | 外部渠道与 Web IM 均作为用户运行进入同一 Kernel；其他后台来源逐 origin 补充核对 |
| 专用审批模型不改变 Agent 对话模型 | `spec.md` 同名 Scenario；`design.md` 决策 4 | 旅程 1：观察首次请求、分类、工具后续跑的完整记录 | `A → C → A` 与 `B → C → B` | pass | 只有中间分类请求使用 C |

### Requirement: 未指定专用审批模型时保持现有行为 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 配置省略审批模型 | `spec.md` 同名 Scenario；`design.md` 决策 1 | 旅程 2：省略字段后从 Web IM 驱动 A、B 两个 Agent | 真栈请求锚 `A → A → A`、`B → B → B`；对应 critical-path 用例 `PASSED` | pass | Gateway 正常启动并完成两个工具旅程 |

### Requirement: 显式审批模型必须真实生效且不静默降级 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 配置未注册的审批模型 | `spec.md` 同名 Scenario；`design.md` 决策 1、2 | 旅程 4：真实 PA foreground 入口启动无效配置 | 启动被拒绝并点名 `llm.tool_approval_model` 与错误值；对应 critical-path 用例 `PASSED` | pass | 未进入可运行 Gateway 状态 |
| 专用审批模型运行时不可用 | `spec.md` 同名 Scenario；`design.md` 决策 5 | 旅程 3：Web IM attended 失败旅程 + unattended origin 补充核对 | Web IM 收到 `permission.request`，record 无 A/B 备用分类；失败/无人值守补充矩阵全绿 | pass | 有人值守与无人值守均沿用既有失败处理，不换模型 |

### Requirement: 审批模型随 Gateway 重启切换 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 修改配置后重启 | `spec.md` 同名 Scenario；`design.md` 决策 6 | 旅程 1：C→D 改盘后先不重启再重启同一 Gateway | 不重启仍记录 C；重启后记录 D；对应 critical-path 用例 `PASSED` | pass | 未观察到运行时热更新 |

## Side Findings

无。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；产品/Kernel 依赖方向和部署拓扑未改变。
- [x] `docs/specs/<包>/`（长青行为契约层）：需要更新；unit 已提供 kernel 与 gateway
  delta-spec，待 orchestrator 按最终实现校正并归并 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；没有新增仓库工作约定或架构红线。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；未改变文档体系。

## Recommended Action

`pass`。全部 7 个必验 Scenario 均有结论且通过，无需 fix、design 修订或 out-of-unit issue。
