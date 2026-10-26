# As-built：宿主维护使用原生 fork provider

本文在实现后整理。基线为 `304c59412e8316ef3ea7df9d904a9a450ca618a2`，范围仅为本 unit 的代码、回归与契约增量。

## 最终结构

`KnowledgeRuntime.review` 解析公开 `ctx.subagents.getProvider('fork')`，构造公开的 one-shot descriptor 后调用 provider 的 `start`。它继续使用原生 fork provider 的完整实现，只不经过追加 `subagent/catalog` 的委派服务。没有替换 `list_agents`、修改 Session 日志、导入私有接口或增加执行循环。

`withKnowledgeRun` 在创建前固定父级 launchSeq，创建后把原生 run 交给 `TrajectoryRuns.knowledge` 观察。后者沿用现有 `nano_trajectory_runs` 存储和起止观察，记录显式维护 kind、background、provider=fork、真实会话 ID、起止和终结事实；原始 result/dispose 的执行能力继续由 native run 提供。失败结果不伪装成 completed，拒绝的 result 记录为 failed 并向原调用者传播。

模型委派的普通子 Agent 仍由原生 subagent 服务处理。维护会话保留原生 one-shot descriptor，因此现有轨迹控制器可以通过原生子会话地址只读分页，不需要特殊的 origin 兼容逻辑。

实际 Web 试用进一步发现，IM 的轨迹入口还要求所选会话已在 Work 身份索引中登记；只保留 runtime 的轨迹索引不足以打开页面。`KnowledgeUpdates.reconcile` 因此使用已有 review 元数据，在校验真实 root binding 与 Global Agent 归属后，向现有 Work journal 追加幂等 `session_linked` 身份链接，并通过 `onWork` 通知既有 WorkSync。它不读取维护历史正文，也不写入原生 subagent catalog。即使维护没有知识写入、失败或取消，身份链接仍可恢复，既有 IM/Node/DSH 权限检查保持不变。

维护 childSessionId 持久化后立即发布 `knowledge.changed`，使运行中且尚未产生知识写入的维护也能及时登记，不等待完成事件。既有暂停维护回归核对该通知中已经存在 running 状态和真实 childSessionId。

## Context 与生命周期

维护仍继承原生 provider 选择的已完成父轮次前缀。现有创建监听冻结父请求的 system prompt 和完整工具定义，执行白名单单独拦截；记忆快照、输出预算与策略继承路径不变。代表性联合维护回归在真实 DSH `llm/stream` seam 比较父请求与各次维护请求的 system message 和工具定义。

维护自身的 Active/controller、成功事实、未完成读文件判定、取消与 Feature 关闭保护不变。原生 provider run 继续拥有信号转交和 quiescent disposal。轨迹观察不将会话重新发布为模型可管理子 Agent；查看只根据可信 root 与持久父链授权并冷读，不恢复 Agent。

## 验证与边界

- `knowledge-review.test.ts` 扩展现有联合维护用例：不入目录、原版 list_agents 返回无子 Agent、冻结请求前缀、重启后原生轨迹 snapshot/page 保留继承输入和真实工具结果、查看后仍未加载维护 Agent。
- `knowledge-policy.test.ts` 保留原生 provider/step-limit 失败和周期回归；`knowledge.test.ts` 保留单项维护、8192 输出预算、成功事实与 Feature 行为；`trajectory-runs.test.ts` 保留普通/嵌套/后台模型委派运行事实。
- PA `knowledge.test.ts` 保护无写入/失败/取消维护的 Work 身份链接、可信 root 过滤、重启后幂等恢复及不读取正文；IM `trajectory.test.ts` 通过真实 socket 验证链接登记的维护身份可以进入既有轨迹授权链。
- 已有 17 项相关回归通过；扩展后的联合用例单独通过。最终全量检查结果与独立 Context/代码审查记录在 `code-review.md`。
- 测试使用锁定 DSH 与确定性模型 fixture，证明实际模型请求装配及运行链；未把它描述为真实 provider 效果评估。
- 用户在真实模型/Web 结果与轨迹入口确认后明确指示“merge”。已审 delta 归并 canonical，并将本 unit 归档；未把 Agent 的测试记为用户亲自操作。

2026-10-26 补充实际模型/Web 试用：在隔离 daily 栈中使用 `codexOAuth:gpt-6.1-sol/high`，由 Web 私聊发起核算、普通内部委派和文件交付，再通过真实模型调用原版 `list_agents(scope=descendants)`。主任务交付 64 件及核算文件；只返回 1 个普通助手，2 个已完成 combined 维护不在原生目录中。修正上述 Work 身份链接遗漏后，重启隔离 Node/DSH，再从 Web 发起行进入原维护轨迹成功，可查看继承输入、维护指令、工具读取结果及 `Nothing to save.`。真实代理入口记录了 22 次工作请求（其中5次维护请求），维护的 system/tools 与父请求匹配；未将代理入口日志当成 vendor 转换后 payload 的完整核验。原始截图、日志和只读数据核对保存在本机报告目录，不提交；实际试用未修改生产。

## 数据、回滚与部署

不修改已存原生日志、目录或数据库布局，旧维护轨迹仍可回溯。旧 E 已登记的历史维护分支不会因本修复自动退出查询；其治理不属于本次未来创建路径修复。回退创建调用即可恢复旧行为，新维护历史和轨迹索引无需删除。不需要一次性数据迁移，不提供或执行生产重启操作。

## 契约增量

- [Gateway delta](specs/gateway/agent-capabilities.md)
- [轨迹 delta](specs/im/agent-work.md)
