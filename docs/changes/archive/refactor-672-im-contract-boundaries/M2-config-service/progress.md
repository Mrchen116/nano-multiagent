# M2 实施与验证

## 完成范围

- control.ts 保留配置业务、原 asciiJson/candidateFingerprint 算法及名称；HTTP adapter 移到 control-routes.ts。ConfigOperations 仅接收 DatabaseSync、三类配置 RPC 的 request port、commit 后 lifecycle callback，不再接收 ImContext 或全服务对象。
- configuration-input 从 HTTP unknown 解析创建/编辑、route id、source 与 skills migration；保留有效省略/null 及未知额外字段忽略。configuration-records 的固定查询拥有具名 SQLite 行；不向调用者开放任意 SQL 泛型类型声明。
- ConfigurationCandidate、AgentProfileView、AgentProfileRecord、ConfigOperationRecord 与 shared ConfigurationIntent/Result 分开。公开投影不暴露 JSON 列；候选恢复在存储 JSON 边界检查。共享 wire 配置验证属于 product-contracts，HTTP/WS 各自映射错误，不由 transport 持有配置业务规则。
- Node 的现有 ConfigurationOperations 同样消费共享 intent/result 类型，未改其操作顺序或序列化调用。
- malformed 节点回执按未确认处理，继续核对原 operation；既有 pending、二次授权、CAS 补偿、PA restore/名称同步与生命周期投递顺序保留。

## 测试策略与证据

- keep：control、agent-settings、approval-configuration、personal-agent、plugins、agent-lifecycle、e2e/control-work；仅更新路由 import 和窄依赖装配，未削弱断言。
- 新 configuration-boundaries 在 HTTP seam 保护省略/null、额外字段、不合法稳定字段先于持久写入和历史 null skills。现有 control 测试超过 400 行，不继续增加独立测试主题。
- e2e/control-work 扩展一次连贯 malformed receipt→503 pending→原 operation 状态查询→成功恢复链。真实隔离 IM 子进程、HTTP、WS、SQLite；节点为协议测试对端，不声称模型或真实节点配置执行已验。
- type-tests 保护配置服务不可访问 setup RPC，SQL record/公开 View/候选不可互相冒充；纳入 IM typecheck。
- Node 24.22.1：7 文件既有回归 71 passed；最新定向组合（configuration-boundaries、node-rpc、e2e/control-work、PA configuration）16 passed；IM 与 PA typecheck 通过。
- 调试：新增 E2E 初次在 mirror 读取返回 500，定位为投影误拒绝旧节点合法 `skills_json='null'`。保留 null，并让无显式选择仍按 discovery 解释；HTTP 编辑仍保留原 string-list 校验。另一次镜像单测 401 是 fixture 缺 Bearer header，补齐后通过。没有改生产鉴权。
- 全量 CI 等价检查正在进行，最终结果统一记入交付记录。无 schema/部署迁移，无 spec delta。

## 剩余范围与集成交叉点

聊天、Work、Channel 上行业务与其 Row/ImContext 尚未全面迁移，本 unit 不宣称全 IM 已完成类型化。control.ts 仍保留序列化函数原 owner/调用语义，另一聊天的序列化归属变更需在该文件和 product-contracts index.ts 做普通集成；不应重新解释配置指纹。
