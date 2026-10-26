# As-built：宿主维护使用原生 fork provider

本文在实现后整理。基线为 `304c59412e8316ef3ea7df9d904a9a450ca618a2`，范围仅为本 unit 的代码、回归与契约增量。

## 最终结构

`KnowledgeRuntime.review` 解析公开 `ctx.subagents.getProvider('fork')`，构造公开的 one-shot descriptor 后调用 provider 的 `start`。它继续使用原生 fork provider 的完整实现，只不经过追加 `subagent/catalog` 的委派服务。没有替换 `list_agents`、修改 Session 日志、导入私有接口或增加执行循环。

`withKnowledgeRun` 在创建前固定父级 launchSeq，创建后把原生 run 交给 `TrajectoryRuns.knowledge` 观察。后者沿用现有 `nano_trajectory_runs` 存储和起止观察，记录显式维护 kind、background、provider=fork、真实会话 ID、起止和终结事实；原始 result/dispose 的执行能力继续由 native run 提供。失败结果不伪装成 completed，拒绝的 result 记录为 failed 并向原调用者传播。

模型委派的普通子 Agent 仍由原生 subagent 服务处理。维护会话保留原生 one-shot descriptor，因此现有轨迹控制器可以通过原生子会话地址只读分页，不需要特殊的 origin 兼容逻辑。

## Context 与生命周期

维护仍继承原生 provider 选择的已完成父轮次前缀。现有创建监听冻结父请求的 system prompt 和完整工具定义，执行白名单单独拦截；记忆快照、输出预算与策略继承路径不变。代表性联合维护回归在真实 DSH `llm/stream` seam 比较父请求与各次维护请求的 system message 和工具定义。

维护自身的 Active/controller、成功事实、未完成读文件判定、取消与 Feature 关闭保护不变。原生 provider run 继续拥有信号转交和 quiescent disposal。轨迹观察不将会话重新发布为模型可管理子 Agent；查看只根据可信 root 与持久父链授权并冷读，不恢复 Agent。

## 验证与边界

- `knowledge-review.test.ts` 扩展现有联合维护用例：不入目录、原版 list_agents 返回无子 Agent、冻结请求前缀、重启后原生轨迹 snapshot/page 保留继承输入和真实工具结果、查看后仍未加载维护 Agent。
- `knowledge-policy.test.ts` 保留原生 provider/step-limit 失败和周期回归；`knowledge.test.ts` 保留单项维护、8192 输出预算、成功事实与 Feature 行为；`trajectory-runs.test.ts` 保留普通/嵌套/后台模型委派运行事实。
- 已有 17 项相关回归通过；扩展后的联合用例单独通过。最终全量检查结果与独立 Context/代码审查记录在 `code-review.md`。
- 测试使用锁定 DSH 与确定性模型 fixture，证明实际模型请求装配及运行链；未把它描述为真实 provider 效果评估。
- 用户尚未验收最终实现，因此本 unit 未归档，canonical 增量保存在 `specs/`。

## 数据、回滚与部署

不修改已存原生日志、目录或数据库布局，旧维护轨迹仍可回溯。旧 E 已登记的历史维护分支不会因本修复自动退出查询；其治理不属于本次未来创建路径修复。回退创建调用即可恢复旧行为，新维护历史和轨迹索引无需删除。不需要一次性数据迁移，不提供或执行生产重启操作。

## 契约增量

- [Gateway delta](specs/gateway/agent-capabilities.md)
- [轨迹 delta](specs/im/agent-work.md)
