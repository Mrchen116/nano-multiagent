# Repository Harness Validation

> 日期：2026-07-30
>
> 范围：验证重构后的知识入口、current/history 边界、恢复能力和隔离运行入口。本文是
> `refactor-486` 的验收记录，不是新的 current owner。

## 结论

机械可达性、同 session 的代表性任务复走和真实隔离 runtime 均通过。当前执行环境没有创建独立冷启动
Agent session，因此“新 Agent 不依赖迁移对话也能完成任务”仍是显式待验证项，不能由本轮结果代替。

## 代表性任务

| 任务 | 实际入口链 | 观察结果 | 结论 |
|---|---|---|---|
| 判断四个顶层包的依赖边界 | [`AGENTS.md`](../../../AGENTS.md) → [`SPEC.md`](../../../SPEC.md) → `tests/contract/` | 根指令直接给出高后果边界；SPEC 提供完整职责、依赖方向和部署拓扑，并指向机械断言。无需读取旧蓝图 | Pass（同 session） |
| 修改 IM 用户可观察行为 | `AGENTS.md` → [`docs/README.md`](../../README.md) → [`IM spec`](../../specs/im/spec.md) → 最窄 area（例如 [`web-chat-ux.md`](../../specs/im/web-chat-ux.md)）→ [`change-workflow.md`](../../development/change-workflow.md) | current area 与 active delta 的边界在根入口、docs map 和 workflow 三处一致：delta 完成归并前不能覆盖 current | Pass（同 session） |
| 在 worktree 启动真实 IM/Gateway | `AGENTS.md` → [`worktree-runtime.md`](../../development/worktree-runtime.md) → [`e2e-up.sh`](../../../scripts/e2e-up.sh) / [`e2e-down.sh`](../../../scripts/e2e-down.sh) | 使用 `/tmp/nano-docs-validation.8UinoR`、随机 IM 端口和隔离 Gateway config；IM `openapi.json` ready，Gateway auto-bound；清理后两 PID 均不存在 | Pass（真实 runtime） |
| 定位一次模型调用记录 | `AGENTS.md` 的直接日志入口 → [`llm-integration.md`](../../development/llm-integration.md) → `LLM_PROXY/logs/session/*_<session_id>/` | 本机存在 101 个 session 目录；最近 session 可按文档定位，并包含 request、downstream response、non-stream response 三类文件。未读取 prompt/response 正文，也未把日志当作规范 | Pass（发现与分类） |
| 恢复一个中断的 active unit | `AGENTS.md` → docs map → [`changes/README.md`](../README.md) → [`feat-484 status`](../feat-484-chat-message-interactions/status.md) → 实时 Git 核对 | `unit/feat-484` 本地/远端均为 `8c22b5e6e`，worktree 存在；worktree 有未跟踪 runtime/review 文件，验证了 status 中“恢复前先检查 cleanliness”的安全提示确有必要 | Pass（未修改该 unit） |
| 查询历史架构选择 | docs map → change archive 搜索 → [`refactor-387 motivation`](../archive/refactor-387-kernel-sdk-no-http-api/motivation.md) / [`design`](../archive/refactor-387-kernel-sdk-no-http-api/design.md) → [`SPEC.md`](../../../SPEC.md) / [`kernel current spec`](../../specs/kernel/spec.md) | 历史 unit 解释了为何移除内核 HTTP、改为 `agent.sdk` 进程内调用；current 架构再次确认该决定。历史理由没有覆盖 current | Pass（同 session） |
| 完成一次 change 收尾 | [`change-workflow.md`](../../development/change-workflow.md) → [`changes/README.md`](../README.md) → [`spec CONTRIBUTING`](../../specs/CONTRIBUTING.md) → [`evidence.md`](../../development/evidence.md) | selected gates、delta 校正与归并、本地 CI、整体 archive、PR/远端 CI 的顺序可从 current owner 得到；流程契约测试锁定 spec review 可选、Gate 2 reviewer 复用和 gate matrix | Pass（静态与契约测试） |

## Runtime Evidence

| Claim | Baseline | Method | Result | Locator | Limit |
|---|---|---|---|---|---|
| worktree runbook 能建立并清理真实隔离栈 | branch `codex/docs-knowledge-system-rebuild` at `4e95552a4` | 以主 Gateway config 为只读源，执行 `e2e-up.sh --wt <temp>`；检查 IM HTTP、Gateway PID/auto-bind；执行 `e2e-down.sh` 后检查 PID 与敏感临时文件 | IM `63150` ready；IM PID `11958`、Gateway PID `11974` 启动后存活，Gateway auto-bound；down 后两 PID 均不存在，PID/JWT/config/ports/credential 临时文件均移除 | 本机 `/tmp/nano-docs-validation.8UinoR` 保留 `.im.log`、`.gateway.log` 与运行数据库 | 单次本机运行；未执行真实用户消息或 LLM 调用；诊断目录不提交 Git |

## Mechanical Evidence

- `./scripts/docs-check`：196 份受维护 Markdown、85 个必须入口，全部通过。
- `pytest -q tests/unit/test_docs_check.py tests/contract/test_change_workflow_documentation_contract.py`：
  8 passed。
- active unit `status.md` 的实时核对使用 `git worktree list`、本地/远端 branch HEAD 和 worktree
  `git status`，没有依据文档快照覆盖实时状态。
- 当前已知、但不应在本次迁移中自动裁决的 drift 仍只记录在
  [`drift-review.md`](drift-review.md)。

## 尚未覆盖

1. 没有使用全新 Agent session 对七项任务做盲测；本轮 Agent 已经拥有迁移上下文，可能低估首次发现成本。
2. 模型日志任务验证了入口、session 定位和文件角色，没有读取敏感请求正文，也没有为了验收额外产生一次
   付费模型调用。
3. 真栈验证覆盖进程 ready、auto-bind 和清理，没有覆盖浏览器用户旅程；本次迁移没有改变产品行为。
