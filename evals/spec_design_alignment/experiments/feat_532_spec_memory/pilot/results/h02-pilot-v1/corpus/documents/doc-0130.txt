# bugfix-363 change-impl-worker 开工报信过早

## 原始报告

> 我期望change-worker是在调研完代码，之后再上报有没有问题。这个日志中，他还没开始就发了。你看下是不是skill有歧义

worker 实际首信原话:

> bugfix-362-M1 reconcile-on-register 开工，正在读取 design.md 和相关代码，随后开始 TDD 三提交循环。

## 现象 / 复现

worker 收到 orchestrator 派发包后,在 §2.3 读上下文、§2.4 跑基线之前就发"开工"信。orchestrator 收到的是一句"我开始干了"的未完成态报信,无法据此判断 worker 是否真的读懂了 milestone 范围,§3.1.1 的澄清回路失去意义。

## 根因

`change-impl-worker` §2.5 + `change-orchestrator` §3.1.1 三处暗示性歧义,叠加导致 worker 把报信时点理解成"收到派发即发":

1. worker §2.5 标题 `开工报信` —— "开工" 字面 = kickoff,易当成"收到任务那一刻"。内文虽写"读完上下文、基线绿之后",但要看完才能注意到时序。
2. orchestrator §3.1.1 描述 "worker / reviewer **启动后**会先给你报一个信" + 案例分类 "**报 '开始干了'**" —— "启动后" / "开始干了" 都是未完成态语言,反向强化 (1) 的误读。
3. worker §2.5 "没疑问"模板只有正例,没有反例禁止 `"正在读取" / "即将开始"` 这类未完成态。

## 修复

`.claude/skills/change-impl-worker/SKILL.md`:

- §2.5 标题改成 `读完上下文后报信(不准提前发)`
- §2.5 首句换成显式禁令:在 §2.3 / §2.4 完成前发视为违规,orchestrator 会要求回到 §2.3
- §2.5 "没疑问"模板补 `影响文件 = <X>` 字段 + 反例 `❌ "开工,正在读 design.md" / "收到,即将开始"`

`.claude/skills/change-orchestrator/SKILL.md`:

- §3.1.1 描述改成 "worker / reviewer **读完上下文 / 跑完基线后**会先给你报一个信",加一句 "未完成态就退回去"
- §3.1.1 案例 "报 '开始干了'" → "报 '已读懂,范围 = X,开始实施'"
- §4 状态表 `开始干了 / 澄清问题` → `已读懂 / 澄清问题`

总改动 ~3 行净增长,无新增章节。

## 验证

下次 orchestrator 派 worker 时,worker 第一信应是 `"已读懂 M<N>,范围 = …,影响文件 = …,开始实施"`,不再出现 `"正在读取" / "即将开始"` 这类未完成态。如果出现,orchestrator 按 §3.1.1 新增的退回指令处理。
