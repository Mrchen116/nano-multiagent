# refactor-570: Shadow publication boundary

## Relations

- Related: refactor-564, refactor-568

## 原始诉求

> 我已经合入了，还有没有非常值得修改的问题

> 新开个unit直接改。

## 澄清记录

用户授权直接实施上一轮推荐的第一项：解除 MessageDelivery 与 IMShadowConversationSync 的双向依赖。Agent 解读：本 unit 只整理 shadow 回复发布边界，保留已有产品行为，完成独立验证和 PR。

## 现状痛点

基线 499774a56：shadow_sync.py 的 reconcile_snapshot、mirror_prepared_agent_output、recover_pending 把自身传给 MessageDelivery；message_delivery.py 的两个 shadow 方法读取其私有 token、HTTP 配置、saga store 和 publish hooks。改变 shadow 内部实现需要同步理解交付模块，测试也必须组装互相回调的对象。

## 目标状态

交付 owner 保留冻结回复投影和交付记录；shadow HTTP 协议与 durable 回执归明确组件，依赖单向。删除失去用途的旧接口，不增加行为、数据库或兼容路线。

## 用户侧验收标准（不变性）

外部聊天的用户消息和 Agent 回复当前会同步到 IM shadow；断线后以相同身份恢复。以下保持不变。

### Requirement: Shadow 对话内容与回复状态保持一致

#### Scenario: 回复与更新可见
- **WHEN** 外部聊天产生用户消息、Agent 回复及工具/完成状态
- **THEN** IM shadow 中仍看到对应用户消息、回复正文、工具与完成状态；同一回复更新不新增重复气泡。

### Requirement: 已接受回复可以恢复

#### Scenario: 暂时失败后重试
- **WHEN** IM 同步暂时失败，连接恢复后重试已接受的文本或图片回复
- **THEN** 原 shadow 会话出现相同回复且不重复；图片仍来自已冻结的内容。

### Requirement: 已失效 run 不晚发正文

#### Scenario: 取消后的旧回复
- **WHEN** 用户停止 run 后旧回复进入发送机会
- **THEN** 不再出现该旧回复正文，既有停止状态清理仍可完成。

## 影响范围

Gateway shadow 同步、MessageDelivery、composition 及相关测试；不修改 Feishu 协议、内核、IM API、stop/reset 状态机或前端。

## 迁移与回滚策略

原 SQLite、output key、幂等键及回执格式原样复用，无数据迁移。复用现有恢复、图片和鉴权回归，补足新边界的接线验证；出现行为偏差可回退整个代码提交，持久数据仍可由旧版本读取。
