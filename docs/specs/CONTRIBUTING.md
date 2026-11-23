# Nano 长青行为契约

[通用契约编写与归并规范](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/specs/CONTRIBUTING.md) 定义 Requirement/Scenario 和 delta-spec。Nano 单包行为以 [docs/specs](README.md) 为准，跨包职责、依赖方向和部署拓扑以 [SPEC.md](../../SPEC.md) 为准。变更的技术决策记录在对应 unit 的 `design.md`。

## 哪些行为进入长期契约

按 [通用收录判据](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/specs/CONTRIBUTING.md#哪些行为进入长期契约) 确认消费者的保证是否变化。Nano 的消费者包括用户、客户端、对端节点和消费工具或上下文的模型。共享业务规则在判定结果的领域维护，客户端补充该端可观察的保证。

## 契约层目录骨架

- `docs/specs/<包>/spec.md` 记录职责、边界及 `Canonical Areas` 索引，各 area 文件承载具体 Requirement/Scenario。
- 契约正文使用 Purpose 和 Requirement/Scenario，测试映射与验证记录留在测试或 change evidence。
- 每份 spec 的 `> 对齐: <unit-id>` 只记录最近一次实际修改该文件的 unit。包入口 `Canonical Areas` 表记录各 area 的 Requirement 数。
- [docs-check](../../scripts/docs-check) 核验对齐标记、area 登记与 Requirement 数量。

## 接口与跨端行为

接口 Scenario 写实际调用方发起的动作，以及对方能依赖的响应、拒绝或重试结果。协议已有权威 schema 时引用它，另写字段省略、确认、重放等仅靠类型看不出的语义。测试用于核对这些保证。

共享业务规则在负责判定结果的领域写全。客户端引用它，只补该端特有的可观察行为。例如，IM 决定哪些卡片改动随消息一次性消费；iOS 另写发送失败时如何保留正文与本地编辑。

## 契约层增量（delta-spec）

### 放在哪里

`docs/changes/<unit>/specs/<包>/<target>.md` 镜像 `docs/specs/<包>/<target>.md`。目标可以是 area 或包入口。

## delta-spec 归并规则

按 [通用归并规则](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/specs/CONTRIBUTING.md#delta-spec-归并规则) 归并到对应 area。若新增 area 或移动 Requirement，同步修改包入口的 `Canonical Areas` 索引和计数。只在实际变化的文件上更新 `> 对齐:` 标记。
