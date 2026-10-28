# Gateway agent-capabilities Specification (delta for feat-676)

## MODIFIED Requirements

### Requirement: 知识维护按长期价值与明确归属保存内容

Gateway 的文档记忆保存长期理解，Skill 保存成熟可复用方法；个人偏好、专业经验、环境与项目背景按主体角色归入当前文档，保留来源、条件、反例与未知部分。完整知识只在一处维护。默认暂停旧条目记忆及其复盘，仅文件显式 legacy 回退时保留旧规则，不与新文档模式同时写入。

#### Scenario: 重复信息及明确纠正
- **GIVEN** 用户已保存一项事实或偏好
- **WHEN** 用户重复表达或明确纠正该内容
- **THEN** 文档模式当轮修正相关正文和入口；当前会话下一次相关判断及受影响的原执行者采用新内容，不生成同义副本；legacy 保留原新会话消费保证。

#### Scenario: 经验证的方法与临时应对
- **WHEN** 一次任务产生可复用的方法、失败尝试或临时应对方式
- **THEN** 知识保留真实结果、条件和必要原因，不把失败尝试写成可靠方法；成熟方法可以在任务中通过 skill-creator 保存为 Skill。
- **AND** 临时资源规则保留条件与退出责任，Agent 选择不冒充用户要求，普通经验不强制发布 Skill。

#### Scenario: 单项和联合维护的知识归属一致
- **WHEN** 同一纠正涉及 Memory 和 Skill
- **THEN** 完整规则保存在正确位置，不因某链路缺少另一种工具而重复保存或改变归属。
- **AND** 自动 Skill 复盘及联合复盘中的 Skill 部分暂停；普通前台维护仍遵守工具权限与真实结果要求。

#### Scenario: 后台维护读取当前持久知识
- **GIVEN** 前台或前次维护已保存新内容
- **WHEN** 后台准备修改该知识
- **THEN** 通过获准读取取得当前完整内容并核对版本，不能依赖父快照覆盖较新的文件；读取失败或未完成不写依赖该内容的修改。

#### Scenario: Memory 读取未完成但模型正常停止
- **WHEN** 后台读取被拒绝、失败或未读完整，随后模型正常停止
- **THEN** 该部分仍为未完成，不推进对应处理位置或旧维护周期；实际已保存内容与历史回执保留，不误报整体成功。

### Requirement: self-evolution 创建的 Skill 跨前台 terminal 仍完成配置调和

历史已成功的知识更新事实保持 session 级消费，重放不重复调和、不修改禁用选择。后台 Skill 自进化及 combined 触发暂停，历史成功事实不被抹掉。显式文件 legacy 回退中的 Memory review 继续父前缀/快照和完成后计数规则；默认 document 使用当前入口和版本失效机制，Dreaming 用独立受限会话、持久源流进度，不继承父 prompt。

#### Scenario: fast review 与 slow review 使用同一调和结果
- **GIVEN** 已有 self-evolution review 成功创建 agent-scope 或 global-scope Skill 的持久事实
- **WHEN** 事实在前台 terminal 之前或之后完成调和
- **THEN** 按真实结果保留历史事件和可发现资产，已存在的同名禁用选择不被覆盖；不因此恢复后台 Skill fork。

#### Scenario: 后续前台轮次与 stream 重连不重复调和
- **GIVEN** 同一 session 的持久事件消费已建立
- **WHEN** 历史创建事件被实时接收或重放
- **THEN** 同一结果不重复处理，未禁用的新 Skill 在后续 session 可用。

### Requirement: Feature可独立启停并撤销其后续影响

#### Scenario: 关闭和重新开启单项能力
- **WHEN** 用户合法关闭再开启 Task Graphs、Skill Creation、Cron 或 Heartbeat
- **THEN** 原有依赖、工作保护和工具选择规则保持，其他 Feature/Agent 不受影响，不累积重复监听；Skill Creation 只控制任务中创建指导，不恢复后台自进化。
- **AND** 记忆是内置能力，旧 Memory Curation 不出现在客户端；document 的 Dreaming 独立控制自动整理，关闭不关闭正常记忆操作。

#### Scenario: 关闭期间重启与在途工作
- **WHEN** 已关闭的 Feature 经历节点重启，或在工作已接受后尝试关闭
- **THEN** 不擅自重新启用；业务 Feature 仍按既有在途责任拒绝不合法关闭。Dreaming 允许停用新自动准入并取消未应用的自动部分，保留实际已保存结果及未完成范围。
- **AND** 配置持久化但应用尚未确认时显示 pending，不伪报 effective 或回滚。

### Requirement: Feature SHALL 保证完整依赖并与独立工具行为分离

#### Scenario: 开启 Feature 展开完整依赖
- **WHEN** 用户开启 Feature 或创建采用默认 Feature 的 Agent
- **THEN** 交互式回复需要 send_message、skill 和 nano-interactive-ui；Task 需要 task_graph 与 Cron Feature；Skill 创建需要 skill_manage、skill、read；随包 skill-creator 按既有 Skill 选择可选加载，缺少该可选指导不使原合法配置变为启动错误；Cron 需要 schedule_create/list/update/delete/run/history；Heartbeat 需要 read。
- **AND** 内置 document 消费不依赖旧 memory 条目工具；普通记忆写入继续遵守已选文件工具。Dreaming 使用自己的受限维护工具集，不暗中开启父业务工具；缺少可运行所需资源须显示不可用，不能假报运行。
- **AND** 默认开启 Task 的初始配置同时开启 Cron；依赖缺失时显式启用动作失败，已关闭 Skill 不冒充可加载。

#### Scenario: 合法关闭与共享依赖
- **WHEN** 用户关闭没有需要者的 Feature
- **THEN** 取消其直接关联资源，仍被其他 Feature 需要或属于基础固定的能力保留；Dreaming 停用不撤销普通文件工具/内置记忆。
- **AND** 不级联关闭依赖 Feature，关闭 Task 后 Cron 保持开启；随后单独打开工具或 Skill 不反向打开 Feature。

#### Scenario: 独立工具不恢复 Feature 行为
- **GIVEN** Feature 关闭而工具仍被合法独立选中
- **WHEN** Agent 调用 task_graph、skill_manage、schedule 工具，或 legacy 模式下可用的 memory
- **THEN** 操作按原授权与业务前置条件执行，不恢复 Feature 额外行为；document 不提供旧 memory 条目工具，Skill 工具不恢复自动 fork。

## ADDED Requirements

### Requirement: 角色化文档记忆可及时消费且不扩大权限

#### Scenario: PA 与独立专家
- **WHEN** 长期 Agent 处理跨聊天相关事项
- **THEN** PA 使用主人相关背景，独立专家按实际人物、项目和专业职责使用知识，内部执行者仍属于原长期主体；不串用不同人的偏好。
- **AND** 当前信息充分时可直接回答，检索不足、部分读取和未知项如实说明；旧记忆、观察和第三方材料不增加业务授权。

#### Scenario: 人工保存与入口滞后
- **WHEN** 当前记忆正文已被保存但尚未提交 Git 或入口仍旧
- **THEN** 保存后的正文立即可用，后续相关判断重读变化部分，旧入口概括不继续作为当前知识；明确区分正文保存、入口同步和版本记录结果。

### Requirement: Dreaming 处理持续历史的合格增量并保持安静

#### Scenario: 跨窗口且主体仍持续工作
- **WHEN** 自动 Dreaming 已开启、到期且存在合格增量
- **THEN** 可整理当前和旧窗口已完整保存的经历，不要求根会话结束、不截断正在进行的模型/工具；无增量不调用模型，资源不足保留积压。
- **AND** 去重重复消息、继承历史与报告，区分观察、自述与实际结果；不消费主 Inbox、不扫描未授权源、不执行业务动作或发布 Skill。

#### Scenario: 失败、冲突、预算不足与重启
- **WHEN** 整理只完成部分材料或部分保存，或保存期间发生较新更正/来源撤销
- **THEN** 保留真实成功结果，不覆盖较新内容；仅确认已完整核对并应用的连续范围，剩余材料可继续，恢复不重复追加同一记录。
- **AND** 已有工作视图显示实际处理范围、变更、延期和未完成结果；普通成功不发聊天通知，模型正常停止不等于全部完成。

#### Scenario: 关闭与手动整理
- **WHEN** 用户关闭 Dreaming 或明确请求手动整理
- **THEN** 关闭阻止自动运行但不关闭内置记忆；手动整理不等自动周期，仍遵守主体停用、权限、预算与并发限制。

### Requirement: 旧记忆可备份导入，临时旧模式仅经文件选择

#### Scenario: 升级、导入和回切
- **WHEN** 已有 Agent 升级或用户要求整理旧记忆
- **THEN** 默认采用文档记忆并开启 Dreaming，逐字保留旧备份；收到明确导入请求后才把备份整理进角色文档，保留原义与来源，重复执行不产生同义副本。
- **AND** 文件可选 legacy，切换时仅所选机制运行，两库独立保存而不双向自动转换；默认历史处理从启用点开始，不暗中扫描全部旧聊天。

### Requirement: 停止使用和撤销来源不得被后台复活

#### Scenario: 排除已有知识或来源
- **WHEN** 用户明确停止使用知识或来源资格被撤销
- **THEN** 当前知识与入口不继续采用被排除内容，后台从源资格和当前排除范围核对，不能从旧材料重新引入。
- **AND** 对未完成的派生清理如实报告，不把当前文件删除称为清除 Git、备份、原始消息和所有系统副本。

### Requirement: 后台 Skill 自进化暂停，任务中创建能力保留

#### Scenario: 自动 Skill 维护暂停期间
- **WHEN** 任一运行模式积累 Skill 使用记录、达到旧 F3/F4/combined 门槛或节点重启
- **THEN** 不启动后台 Skill fork 或自动归档，不消费待维护证据冒充已完成；保留已有 Skill、使用统计与历史结果。
- **AND** 普通 Agent 按任务需要使用迁移适配的 Codex skill-creator 创建/维护 Skill，仍遵守现有范围、权限和真实操作回执；Dreaming 不发布 Skill。

## REMOVED Requirements

### Requirement: F4 仅在非 Global 模式下依据跨会话证据修补目标自动技能

### Requirement: Memory 与 Skill 同时到期时使用一次联合复盘
