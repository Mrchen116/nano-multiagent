# bugfix-683: Agent 初始上下文身份、记忆与异常相关性

## Relations

- Depends on: feat-676
- Related: refactor-679
- Related: feat-677

## 原始报告

2026-10-31，用户在固定 daily 产品预览中查看 `daily-product` 的真实轨迹，逐项指出：

> 先把当前这些我指出的所有问题全部改了。

> 以及你的初始上下文告诉agent他叫P · 产品与体验，他的id是daily-product了吗

> 没有意义就不加，这也不是dsh要求的对吧

> 还有这个，为啥无端要在开始插入一个这个，就算连不上，agent也没调用task啊。不是说了，要把task服务状态和agent context分开吗，哪怕真的不可用，也没影响到当前agent啊。之前我也说过吧？

> Unavailable tools: memory_maintenance. Do not claim a write or automatic maintenance can run without its required tools.
> 这又是什么傻逼东西，你工具压根没给他，为啥要强调

> 这个是memory.md的内容是吗，为啥不给路径。我看本地开源cc的代码，很清晰会给路径，写的很清楚这是啥

> “this Agent’s persistent memory index”不是的，这个作用不是这个，是one page 关键的memory信息给agent你的。如果还需要详细的记忆，则去记忆目录中找

用户还指出无实际备份的 Agent 也收到常驻 `Backup navigation`。明确保留 DSH 原生 `Current runtime context. This snapshot supersedes earlier runtime-context snapshots.`；删除的是自有插件里的 `Agent name: <会话 UUID>`，不另加 Session ID，保留历史恢复需要的窗口 ID。

## 现象与复现

- 基线为 Memory 分支 `unit/feat-676` 的 `5e5d3fcc8`，包含 refactor-679。实施继续以此为基线；main 仅发布本 unit 设计文档，不提前并入 Memory 实现。
- daily 预览中 `daily-product` 会话 `519271cf-6e1e-432f-910e-d90e015e2d6f` 的首次 native 请求：没有显式产品名称/ID，插件将会话 UUID 标为 Agent name；普通输入因 Task 同步失败收到无对象的长限制提醒；Memory 段显示不存在的备份目录、缺少前台工具警告，正文只标 `Current entry`。
- `memory_maintenance` 未暴露给前台属正常工具选择，但 Dreaming 同样以此前台选择拒绝后台维护。

## 影响范围

Global、SingleThread、PA 及其历史恢复输入可能混淆身份、误解记忆用途，或被无关故障提醒打断。后台整理可能被前台工具选择无意关闭。当前未发现本问题造成记忆文件损坏。

## 根因分析（RCA）

1. Node 规范配置保存显示名，但运行时 `AgentConfiguration` 没有传递此字段；自有 `dsh-agent-context@0.3.0-rc.6` 把执行 ID 当名称渲染。
2. `TaskExecutionDriver` 将任何 unavailable 快照直接翻译成泛化 D9，没有先求当前受影响的任务/待消费原文，也没有按实际可见内容去重。后台同步与模型相关性混为一体。
3. `DocumentMemory` 将维护目录和缺工具检查无条件拼到日常 context；`Current entry` 丢失了文件来源和“一页关键记忆”含义。
4. `Dreaming.start` 以 parent 的 read/write/edit/memory_maintenance 可见性判断后台是否可运行，而后台已有独立工具选择、文件边界与来源检查。

## Requirement / Scenario

### Requirement: 模型获得真实且无歧义的产品身份
- **WHEN** Agent 开始回复、改名后开始下一轮，或换窗后继续，**THEN** 模型可见当前配置的产品名称与 Agent ID，窗口导航不把执行 UUID 称为名称。
- **WHEN** 内部 child 执行任务，**THEN** 产品归属标为所属 Agent，不能把 child 冒充为根 Agent 或新增用户授权。

### Requirement: Task 故障按实际影响说明
- **WHEN** 普通输入与 Task 无关，且没有已知在推进的任务或待消费 Task 原文，后台同步/查询不可用，**THEN** 模型不收到 Task 故障提醒；实际调用失败由工具结果说明。
- **WHEN** 故障影响已知当前任务或待消费原文，**THEN** 限制指向具体 Task/原文，不改变任务状态、不扩大为所有工作停工；同一可见限制不逐步重复。
- **WHEN** 权限或同步不可核实，**THEN** 不投递未核实的原文、不以旧状态自动续跑、不绕过 Task 工具拦截；恢复后重新核实并正常消费。

### Requirement: 关键记忆可直接理解且具有来源
- **WHEN** 注入有效 MEMORY.md，**THEN** 明确完整文件路径、内容边界与一页关键记忆用途；详细记忆导航指向该 Agent 固定记忆目录。
- **WHEN** 日常回复不涉及恢复备份或不可用操作，**THEN** 不常驻备份路径或缺工具清单；有效性、更正、仅 Dreaming 写入和真实保存回执规则保留。

### Requirement: 后台 Dreaming 由自身能力和宿主授权决定
- **WHEN** 前台未开放 memory_maintenance 或写入工具，而后台所需能力、配置与来源许可正常，**THEN** 自动 Dreaming 仍可按既有周期运行。
- **WHEN** Dreaming 关闭、维护暂停、来源失效或后台实际能力不可用，**THEN** 按真实限制停止或返回失败，不绕过限制，也不假报保存。

## 修复方向

补齐宿主身份传递；修正自有插件发布并锁定依赖；将 Task 故障限定为具体影响；精简并明确记忆上下文；解除后台启动对前台工具目录的误依赖。根因跨模块，采用 Full、单 M1，独立验证模型输入及产品行为。无 UI 布局变动、无生产操作、无数据迁移，保留用户正在查看的预览及其历史。
