# gateway/task-graphs Specification (delta for feat-785)

## ADDED Requirements

### Requirement: 定时类 Task waiting 支持跨天未来复查，待人决策类 waiting 静默挂起

#### Scenario: 跨天或跨周定时复查安排校验
- **WHEN** Agent 为等待外部进展或未来时间窗口的任务提交定时类 `waiting`（`kind: "scheduled"`）关联
- **THEN** 系统核实原生 Schedule 归属当前负责人与根会话、处于启用状态且下次执行时间在未来有效范围内（支持跨天及多周周期，不再拒绝超过一小时的合理跟进间隔）；过期、无效或无法核实的安排明确拒绝且任务保持原状

#### Scenario: 待人决策类 waiting 不要求轮询定时器
- **WHEN** Agent 已向所属聊天发出明确问题并确认送达，需要将任务暂停在等待真人回答或拍板（`kind: "decision"`）
- **THEN** 系统保存等待原因与待决问题并使任务进入安静等待，不要求创建或绑定周期轮询 Schedule，也不将该节点列入安排失效修复催促

## MODIFIED Requirements

### Requirement: 任务工具公布动作与参数契约

#### Scenario: Agent 获取任务工具定义
- **WHEN** 已启用任务工具的 Agent 获取模型可见的 `task_graph` 定义
- **THEN** 工具及参数描述明确五动作字段归属：`create` 默认创建轻量独立单卡根（`mode: "none"`），同时支持显式建立 `dag` 或 `explore` 根并可选附带初始原子 `operations`；支持 `proposed`、`backlog` 状态、提议说明元数据、通用来源会话引用（`source_conversation_ids`）、节点准备草稿以及两类 `waiting` 参数
- **AND** `update`（`apply`）支持在保留原节点标识与记录的前提下将无子节点的 `mode: "none"` 节点原位展开为 `dag` 或 `explore`；变更说明字段必填，普通修改允许空说明，重新开启已完成工作仍要求原因
- **AND** 批内节点定义与引用、仅引用此前定义的节点，以及依赖 `from` 为前置、`to` 为后续的方向有就近说明与可用示例
- **AND** 描述不改变资源归属、权限、原子修改或幂等；图依赖不自动调度后继，仅直接分配给 Agent 且进入 `doing` 的节点承担持续推进责任，`proposed` 与 `backlog` 绝不触发自动执行

### Requirement: Agent SHALL 持续推进全部本人 doing 任务

#### Scenario: 各合法入口开工与提议态隔离
- **WHEN** 任一合法入口（包括真人在界面批准、或真人在当轮对话明确同意后由 Agent 凭当轮真实真人消息凭据批准无未完成前置依赖的 `proposed` 提议卡）使任务进入 `doing` 且负责人为 Agent
- **THEN** 该 Agent 按产品会话范围承担持续推进责任，一轮回复结束仍有下一步时继续；`proposed`、`todo`、`backlog` 均不自动开工，且无当轮真实真人消息凭据的后台会话不得将 `proposed` 自行改为 `doing` 或 `todo`，也不得继承已结束历史轮次的真人消息凭据
- **AND** 责任涵盖跨图和各层级直接分配给本人的任务，可查看他人任务不等于负责

#### Scenario: 多项责任与结束条件
- **WHEN** Agent 再次推进现有责任
- **THEN** 可获全部本人 `doing` 与 `waiting` 的区分清单，正文及讨论按需读取，自主安排推进顺序
- **AND** `proposed`、`backlog`、`in_review`、`done`、`paused`、`closed` 不要求该项自动续跑；返工注明原因并恢复 `doing`；子结果不自动完成父任务或启动后继依赖

#### Scenario: 改派
- **WHEN** 任务改变负责人
- **THEN** 状态保持，旧负责人不再续跑，新负责人承担 `doing`；定时类 `waiting` 保留且由新负责人核对并修复不属于自己的后续安排，`paused`、`backlog` 与 `proposed` 不自动恢复

### Requirement: waiting SHALL 关联有效原生安排并允许主动恢复

#### Scenario: 首次等待及校验失败
- **WHEN** Agent 已完成必要提问或交办并核实实际送达，为无可执行下一步的任务提交定时类 `waiting`（带有效原生安排）或待人决策类 `waiting`（带明确待决问题）
- **THEN** 系统对定时类核实真实安排的负责人、根会话、启用及未来执行有效性，对待人决策类核实明确问题说明，成功后原子保存等待原因及关联
- **AND** 无效或无法核实则明确拒绝并保留原状态；未获送达确认不能声称正在等用户答复；不设最少交互轮数或独立阻塞审核模型

#### Scenario: 安静等待与安排失效
- **WHEN** 没有 `doing` 且所有定时类 `waiting` 均有有效安排（或仅有待人决策类 `waiting`）
- **THEN** Task 允许暂时空闲，其他 `doing` 存在时仍继续工作；定时类关联后来失效须触发处理或明确显示运行限制，不静默失联或重复刷屏

#### Scenario: 关联 Schedule 被删除
- **WHEN** 用户或 Agent 删除 Schedule 后，具体定时类 `waiting` 任务失去有效的关联安排
- **THEN** Agent 获得指出该 Task 标题、唯一标识、所属聊天与入口的 reminder，说明无法按原计划唤醒，要求检查是否已结束、能继续则推进、仍需等待则建立新的有效检查
- **AND** 此 Task reminder 不因删除者是 Agent 而省略，不能由删除工具回执或 Schedule 自身变化通知代替；删除不会仅因 waiting 引用被拒绝，提醒不自动改变 Task 状态
- **AND** 多项受影响任务逐项可定位，已经换用有效安排或离开 waiting 的任务不再要求修复；未知检查结果不冒充确认删除

#### Scenario: 提前答复与定时复查
- **WHEN** 相关答复、协作结果或定时提醒实际到达
- **THEN** Agent 读取当前状态与外部事实判断是否恢复 `doing`，重新考虑阻塞必要性和授权内替代路径；定时到期不是授权或默认同意，仍需定时等待时先安排有效的下一次检查（间隔按真实任务周期判断，支持跨天安排）
- **AND** 离开 `waiting` 清除关联，旧定时输入不能重新打开 `paused`、`backlog`、`proposed`、`closed`、`done` 或 `in_review`；同一正常到期已安排复查处理时不另加一轮相同原因的修复催促

### Requirement: 自动续跑 SHALL 包含必要行动规则及当前本人任务概要

#### Scenario: 一轮结束仍有可执行责任并注入北极星目标锚点
- **WHEN** 主会话按现有任务续跑条件继续执行
- **THEN** 获得全部本人 `doing`／`waiting` 概要、所属顶层北极星大目标标题与终局目标摘要、上级路径、任务详情与讨论入口，以及核对当前事实、取得并验证进展、围绕顶层大目标一致行动且完成前检查整个目标的必要指导
- **AND** 等待前核实阻塞及实际送达、尝试授权内替代办法并建立有效检查（或明确待人决策问题）；其他 `doing` 继续，暂停和被拒绝动作的限制保留，提醒不构成新授权
- **AND** 普通新消息与无变化内部重建不因此追加整份续跑 prompt，任务完整正文和历史讨论按需读取

## REMOVED Requirements

### Requirement: Task waiting 的下次复查 SHALL 在未来一小时以内
