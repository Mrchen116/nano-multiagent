# feat-652: Code Review

## Review scope

- Reviewer: 独立 `feat652_code_review`，`gpt-6.1-sol/high`，未参与实现。
- Base / executed_base: `d5b3577923e3dff74de47d947e49c1f963ef91e0`。
- Round 1 head / validated_at: `8024db2f644408f1b412f108c60c40c45009d671`。
- Review mode: full；完整 PR diff 含 bugfix-644 与 feat-652。前者既有 code/product 证据按适用范围保留，同时核对集成接线。
- Included uncommitted files: 无。

## Round 1

2026-10-25，独立审查确认两项 P2：

1. `control.ts` settings 能力投影丢失 `fixed_tools`，使固定上下文工具/PA 工具被界面当作可取消项。实际 Fastify 对比同一 catalog 的旧/新接口，并用前端 capability catalog 核验。
2. 创建页使用默认 preview 工作区的继承审批值；选择已有自定义工作区时可能与实际 runtime 不一致。实际 NodeConfiguration 复现 owner Codex、自定义目录 nano 时显示与运行规则不同。

主会话修复：settings 保留 fixed_tools；新增 owner 受限的目标工作区 approval 只读查询，复用运行时同一策略缓存，不创建目录或读取模型 catalog。创建页输入变化时清除旧标签，稳定后显示真实策略。修复恢复用户已确认的固定工具限制与真实继承值语义，不引入新的用户决策或权限。

## Closure

- 2026-10-25，独立 closure/patch 覆盖 `8024db2f644408f1b412f108c60c40c45009d671..2f93db6560eb2716acc7676e22e30f108bbc581f`。
- Finding 1: closed；Fastify 回归确认 settings 与既有 capabilities 的 fixed_tools 一致。
- Finding 2: closed；owner 校验、响应字段过滤、Gateway RPC 类型、路径变化查询键及缓存语义正确。
- 返回 JSON `[]`，无新增存活问题。as-built 与 canonical delta 已对照实现，无实质矛盾。
- effective_base: `d5b3577923e3dff74de47d947e49c1f963ef91e0`。
- effective_through / final source: `2f93db6560eb2716acc7676e22e30f108bbc581f`；之后只有报告、归档与相对链接调整，源码结论保留。

## Validation

- 修复前完整前端：107 文件、1016 项通过；生产构建和 critical 阈值 audit 通过。audit 仍报告 5 high、2 moderate、4 low，无依赖变更，未扩大范围做升级。
- 修复前完整后端：131 文件、694 项，692 通过；2 项是 main 同步后参数化继承策略测试仍硬编码 dsh。改为对应真实 inheritedRules 后定向后端 2 文件、30 项通过。
- 修复后创建与工作区回归 2 文件、25 项通过；IM/Node 构建、前端 TypeScript 与构建通过。新增测试覆盖固定工具投影、只读工作区策略路由、默认到自定义目录的值变化及过渡未确认。
- Python 65 项通过、31 deselected；ruff check/format 通过，85 文件格式一致。根构建、typecheck、原生交互资源检查已通过。
- 相关源码没有新增原生 iOS 修改；bugfix-644 原 PR399 的远端 iOS 44 测试与 Release archive 证据保留，完整 PR 再由远端 CI 按变更检测执行。
- 原始本地日志在 `/tmp/feat652-close-{frontend,backend,python}.log` 与 `/tmp/feat652-review-{backend,create-final,ui-build}.log`，不提交运行日志或凭据。远端最终 head/CI 结果随 PR 记录。
