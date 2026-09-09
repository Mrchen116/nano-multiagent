# kernel runs Specification (delta for feat-546)

> 目标增量；实施校正后归并 current。

## ADDED Requirements

### Requirement: 消费者可原子地只在 Session 空闲时提交输入

消费者可以提交带稳定 submission identity 的空闲运行请求。Session 有已经受理、运行或尚未完成清理的执行，以及串行生命周期操作时，该请求不注入消息、不创建排队运行。正常 submit 与后台通知的默认行为保持兼容。

#### Scenario: 忙碌时零副作用拒绝
- **GIVEN** Session 已经有受理中的执行或压缩操作
- **WHEN** 消费者调用空闲提交
- **THEN** 得到未受理结果，Session 不增加输入或运行

#### Scenario: 同时到达的请求
- **WHEN** 两个空闲提交或空闲提交与后台通知竞争同一 Session
- **THEN** 每个被受理的输入都有准确的执行身份，Session 不并行运行
- **AND** 同一 submission identity 的重试不会创建第二个运行

#### Scenario: 进程重启后查提交收据
- **WHEN** 消费者按原 Session 与 submission identity 查询收据
- **THEN** 可以判断输入是否已经持久写入，以及其实际 turn identity
- **AND** 未持久写入的受理不被报告为已进入上下文

### Requirement: SDK 消费者可同步观察 Session 级执行事实

SDK 消费者可注册和关闭进程内事件观察器，按发布顺序取得稳定 event identity、时间与实际 Session／Turn identity。普通子执行没有顶层 run identity 不影响其消息、工具、usage 和终态的可观察性；子归属与后台 task 类型来自真实执行记录。

#### Scenario: 普通子执行无顶层 run identity
- **WHEN** 子 Session 执行工具并完成
- **THEN** 观察器收到同一真实 child 的工具开始／结束、轮次统计和终态
- **AND** 不需要为它伪造顶层 run identity

#### Scenario: 子创建与补充关联
- **WHEN** 消费者的主 Session 创建子执行或给已有 child 补充输入
- **THEN** 可以观察真实 parent/child 关联与实际接收的补充，不从描述文字推断身份

#### Scenario: 关闭或异常观察器
- **WHEN** 消费者关闭自己的观察器，或该观察器处理事件发生异常
- **THEN** 不改写工具的模型可见结果，不重放工具副作用
- **AND** 正常关闭等待已经进入的回调结束，后续不再向该观察器投递

### Requirement: 持久输入边界可被观察而不冒充消息消费

消费者可观察实际输入持久写入的边界，带该提交的身份。初始唤醒输入持久化与之后工具返回正文的持久化是不同事件，不能将前者解释为已经读完后者。

#### Scenario: 工具读取之前收到唤醒收据
- **WHEN** 一个仅含通知提示的初始输入被持久写入
- **THEN** 观察器只能据此确认该提示已进入 Session，不能得出其引用正文已被读取的结论

### Requirement: 消费者可核对实际持久写入的工具正文

SDK 观察器可获得某个工具结果实际持久写入后的证明，含真实 Session、Turn、工具调用及消息身份、最终内容摘要和序列化状态。证明描述实际保存并用于模型上下文的内容，而不是原始工具对象或 UI 展示；序列化回退仍可维持原模型行为，但必须与正常序列化区分。

#### Scenario: 正常序列化正文可核对
- **WHEN** 工具结果正常序列化并成功持久写入
- **THEN** 消费者收到同一工具调用的持久证明，内容摘要对应实际模型内容
- **AND** 当前轮模型使用的工具内容与持久内容一致，消费者不需要读取内核私有存储

#### Scenario: 序列化回退不会冒充正常结果
- **WHEN** 工具序列化失败并以既有回退内容成功持久写入
- **THEN** 消费者可辨认回退状态和实际回退内容摘要，不能误认为原目标正文已正常持久化
- **AND** 不因此改变既有工具的参数或回退结果

#### Scenario: 持久失败不产生成功证明
- **WHEN** 工具消息未能完成持久写入
- **THEN** 消费者不会收到该消息的成功持久证明，不能提前确认其引用内容已摄取
