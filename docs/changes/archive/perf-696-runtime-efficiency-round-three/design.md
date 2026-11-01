# perf-696：As-built Design

> 实现后形成，记录实际代码与验证；没有补造事前设计门禁。

## 版本与结构

Base：0e8c468019a909ad362dd338958f8921108c4729。固定 review head 见 code-review.md。现有 PA、DSH 接入、IM schema 与 Web membership hook 内的局部修改。

- KnowledgeUpdates 在 review/fact/单聊 fallback 三处调用已有 bindingForSession。无 child 的 review 原本不产生关联，先跳过再查绑定；历史投影与事实 ACK 仍按原稳定身份重放，不增加 review 游标或持久缓存。
- WorkflowResults 按 parent session 查询绑定；仅 SingleThread 分支读取来源。NodeStore.inputForIds 使用输入 ID 的主键查找与 session 条件，json_each CROSS JOIN 保持从已知 IDs 开始，按 rowid 取最早入站匹配，不按调用方 ID 数组的顺序返回。Global 不读取不会消费的源消息。保留旧会话归属与持久交付后 ACK。
- TrajectoryRuns 的工具钩子只保存工具 ID 与当时的 seq 上界；实际 subagent/start 才从该上界内解析 launchSeq，同一工具上下文仅解析一次，包括未命中的情况。不按工具名过滤，自建工具启动子执行也支持。既有 AsyncLocalStorage 作用域、父/子身份与描述符逻辑不变。
- ModelFallback 将“是否已执行工具”的历史扫描放到 recoverable error、有候选、无新输入且未 stop 的判定后。成功/无 fallback 不扫描；必要的 inputIdsForTurn 回放仍保留，不改变部分工具执行后禁止重试的约束。
- IM 仅增加 pa_source_events(source_event_id,binding_id) 与 agent_work_events(root_agent_id) 两个索引。查询与投影代码不变，启动 schema 自动应用，既有数据无人工迁移需求。
- useMembershipCache 用 hook 内单个在途 promise 和 pending 标记合并突发；新事件在请求期间到来则不应用过期结果，而再次读取。恢复调用等待同一队列。消息缓存按事件即时移除；批量 cancel 后再核对 pending/账号/卸载状态，随后同步应用权威列表与草稿资格。事件触发的共享批次失败仅执行一次既有列表 invalidation；单独恢复失败仍沿原恢复错误路径报告，下次恢复可重试；卸载不写回晚到结果。

## 失败、迁移与复杂度

未增加持久状态、公共运行服务或 DSH 私有依赖。新增 SQL 索引可以随代码回滚保留；瞬时前端队列随 hook 销毁。工作流源查询保留 session 验证和入站次序；知识投影重复恢复仍幂等。没有新增全历史缓存来换取查询速度。模型可见内容与来源判定不改；成员缓存修复对齐已有权限及时失效契约，不是新增产品体验。

## 验证定位

证据：/Users/czj/.codex/reports/perf-696-20261102/，包括三路独立审计报告及旧/新探针。工程验收沿用用户本次后台优化豁免。

- PA 实际消费者：300 reviews/1,000 bindings 的绑定解码300,000→300；20 workflow/3,000旧输入的绑定20,000→20、输入60,000→20，20次交付/ACK与原 external_reply 保持。既有旧会话交付测试增加反序 inputIds，仍选最早实际入站。
- DSH 实际公开 Session/Context hook：25次无子执行工具完整快照25→0；25次成功无fallback的历史 some 访问250,650→0，完成run数量不变。轨迹原生测试覆盖并行、嵌套、重启与原始launchSeq；fallback既有错误/工具/续跑边界回归保留。
- IM：两条索引分别由完整发布/完整view方法和 EXPLAIN 验证；Work 完整JSON前后相等，matching message.created 保留同一 wake。
- Web 原始 React hook 复现100事件→100请求和旧结果恢复removed聊天；新增5项行为测试覆盖突发合并、在途新事件再读、恢复等待、失败重试、共享失败仅一次列表失效与卸载晚回包不应用。
- 初次定向25项中24通过、1失败：测试提供的无child review缺省root，引发SQLite undefined参数。调整为先跳过本就不投影的无child review；知识/工作流7项重跑通过。没有放宽断言或修改预期。
- 构建与类型检查通过；完整门禁、独立审查及主干复核结果见 code-review.md。

## Canonical 文档

无接口/模型可见内容 delta；当前 Web 账号与权限缓存边界保持。无需一次性迁移提示词。Work.query 的已测未修成本和未证明可删除的恢复读取见 motivation.md；不将它们写成已优化。未访问生产或调用真实 provider，未部署。
