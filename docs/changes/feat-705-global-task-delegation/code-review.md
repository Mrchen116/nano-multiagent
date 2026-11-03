# Code Review: feat-705

## Round 1 — full

- `executed_base`: `492b72603cebc5f904f7001b12e3d4475ce55639`
- `validated_at`: `45cd9117cb6183f504cdf63bdb5c8aef4e882dd3`
- `diff_range`: `492b72603cebc5f904f7001b12e3d4475ce55639..45cd9117cb6183f504cdf63bdb5c8aef4e882dd3`
- 独立审查现场：`unit/feat-705`，派发时及审查源码时 HEAD 均为上述 validated_at。仅写审查报告；不修改源码、测试、设计或配置。
- 范围：完整实现 diff 及受影响的配置、原生 lineage／冷恢复、工具执行、产品权限、Workflow 特定 child、Skill／Feature 和占用保护消费链。按 `change-code-review` full 执行，包含 `agent-context-review` Mode B — Implementation Review。

## Findings

```json
[]
```

在已审范围内没有达到 CONFIRMED／PLAUSIBLE 报告条件的存活代码缺陷。该结果不表示 M1 所有验收证据齐备；证据缺口与能力 delta 校正单独记录在 `verification.md`。

## Agent Context Implementation Review

触发原因：本 diff 改变实际工具选择、根／一级／二级职责、共享系统段投影、fork 指导及配置更新时的工具占用解释。

| Surface／生命周期 | 实际检查与结论 | 证据及限制 |
|---|---|---|
| 角色来源／新建／冷恢复 | `child-role.ts:19-61` 从原生 origin、depth、fork descriptor／创建上下文和宿主冻结配置导出角色；模型无法用参数或 Prompt 自授 worker 身份。`index.ts:255-268` 和 `owned-sessions.ts:40-119` 在可信父配置／原生 composition 上共用 attachAgent。 | 源码；新增 global-child-tools 原生 fixture 覆盖 Global／PA、一级／二级及一级同 ID 冷恢复。普通二级同 ID 冷恢复尚无本轮直接请求证据。 |
| 工具／Schema／配置更新 | `capabilities.ts:32-44,69-87` 对已装载原生工具取快照，只让适用内部角色独立于根普通选择；Goal、产品入口和用户提问入口另有限制。根不走 independentTool。`agent-config.ts:180-216` 保留选择撤回和共享配置更新。 | `/tmp/feat705-narrow3.log`，7 文件 18 用例通过；新增 fixture 实际执行 read、spawn、worker fork，并检查根无未选 read／fork。这是实际 DSH + stub，不能证明真实模型选择。 |
| 普通一级系统指导 | `agent-config.ts:154-174`、`global-mode.ts:113-132`：独立局部职责、不复制根 Persona／Inbox，执行完整事项、自主分工、必要问题回父级、内部回传不等于公开交付。参数仍用 DSH 原生工具及原生父 ID，无额外 Nano 报告工具。 | 新 fixture 的 `llm/stream` 请求与原生工具执行；没有本轮一级最终 provider wire 可替代项。 |
| 普通二级系统／任务／来源 | `agent-config.ts:134-147,154-174`：不注册产品身份／一级指导，并过滤共享 nano-* 系统段；保留 DSH 原生 AGENTS、parent ID、子目标及工具说明。权限仍由宿主实际身份执行。 | 新 fixture 对合成 sentinel、原生父 ID 和 AGENTS 的实际适配前请求断言；不将其声称为 provider 序列化或模型消费证据。 |
| worker fork／继承 | `child-role.ts:23-40,64-66` 和 PA／Task／UI 的 internal execution 投影使二级 worker fork 与有效一级父配置保持系统／工具一致，保留原生前缀与现有最窄任务尾说明；没有新根开关 Prompt 分支或取消流程。根直接 fork、SingleThread 继续原规则。 | global-child-tools 对 worker fork system 内容／schemas 与一级相等；既有 task-child-context／llm-attribution 可证明其原有受控 wire 边界，不外推为本轮普通二级 wire。 |
| 保留／撤回／占用 | `capability-state.ts:28-37,69-74` 与 `index.ts:626-653`：真实调用仍记账，仅根普通选择的占用投影排除独立 worker 工具；Feature／Skill 占用不因此免除。Workflow 冻结 scope 通过 scopedChildren 保持非目标角色。 | capability-state 新例保护 root read 撤回和 shared Skill 占用；原生 fixture 验根新输入与 worker 运行。`/tmp/feat705-role-boundaries.log` 4 文件 9 用例通过，保护既有 Workflow／维护／PA 权限；不等于新增所有角色更新组合已逐一执行。 |

审查复用了实施记录中与本 SHA 适用的红绿证据：`/tmp/feat705-baseline-red.log` 将五个 runtime 文件暂退至 fcd995949 并重建时新增风险用例真实失败，恢复候选重建后通过；该记录不被当作另一个受审版本。未另起真实服务、未重复全量检查。

## 未验证条件

- 普通 Global 和 PA 的真实模型自然旅程、原事项补充／日常短问／真实公开交付仍待实施 owner 和产品 reviewer 提供定位；无证据支持“模型必定委派正确”或“模型一定误解”的断言。
- 本轮新增普通一级／普通二级／worker fork 的最终 provider 请求（转换时含 upstream）尚未提供；适配前捕获、catalog preview、旧 fork wire 不替代此证据。
- 普通二级同 ID 冷恢复及要求的共享撤回／深度边界最终证据、required CI 尚待收口。此处不把未完成检查伪装成代码 bug，也不凭 `[]` 放行 Gate。

