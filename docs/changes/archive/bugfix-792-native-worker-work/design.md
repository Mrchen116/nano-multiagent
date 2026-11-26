# DSH worker 工作记录恢复（事后设计）

DSH 的 Work 子会话目录在浏览或定向读取时识别原生一级 worker，标记该会话并在其下停止 Work 遍历。PA 复用子会话的持久分页、逻辑轮次及检查点。首批明细入队前先排空父会话派工关系，已登记的 worker 始终使用同一 ID 和 worker scope。原生任务输入及来自父级的追加消息随工具、回复和用量一起投影。

IM 通过当前记录的 node、scope、runtime 和事件类型接受明细，第一条有效明细建立可点击状态。Web 和 iOS 沿用现有记录入口。Web 原生查看器通过 owner、当前执行所属根及 DSH 原生父链验证这次观察。选择一级 worker 时返回其自身运行，内部 helper 继续保持原来的可见范围。

节点有持久子会话时，常规目录扫描可重读历史，已有 checkpoint 和日志事件 ID 用于去重。只有关系或统计且缺少可读历史的条目沿用既有展示。没有数据库迁移。

## 验证定位

- DSH 目录、真实子进程与父链检查见 descendants、global-child-tools、trajectory-catalog 和 trajectory-runs 测试。
- IM 的 work-production-chain 覆盖持久日志、HTTP 同步、派工关联、原生观察准备和重启回读；work-summaries 覆盖外部 CLI。
- Web 的 agent-work-panel 参数化测试从派工图打开四种运行时的记录并展开调用参数、结果，按运行时验证原生轨迹。
