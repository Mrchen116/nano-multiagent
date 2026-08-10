# bugfix-526: 飞书审批卡展示工具输入

## Relations

- Related: feat-447
- Related: feat-504

## 原始报告

> 飞书 channel，让审批，但是啥input也不显示，和内部IM不一样，这没法审批啊，没信息
>
> 截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-dd326abd-6dc2-49f2-91d2-a5510b6869dc.png`
>
> 开个unit，并走[$change-orchestrator-simple](/Users/czj/Repos/nano-multiagent/.claude/skills/change-orchestrator-simple/SKILL.md) 修

## 澄清记录

- Q1: 飞书是否直接对齐内部 IM，展示完整 `tool_input`，仅对超长内容截断？
  A(原话): 开个unit，并走[$change-orchestrator-simple](/Users/czj/Repos/nano-multiagent/.claude/skills/change-orchestrator-simple/SKILL.md) 修
  Agent 解读: 用户在收到推荐方案后直接要求立项并实施，确认按推荐方向修复。

## 现象 / 复现

飞书消息触发的 agent run 进入工具权限审批后，原飞书对话里的 interactive approval card 会显示工具名、审批问题和操作按钮，但 `Input` 只显示参数数量及参数名。例如 `edit` 只显示 `3 parameters: newText, oldText, path`，看不到目标路径、待替换内容和新内容。用户无法据此判断 Agent 将修改哪个文件、把什么改成什么，因而不能做知情审批；同一请求在内部 IM 审批卡中能够看到完整输入，两端信息不一致。

稳定复现：从飞书触发一次需要人工授权的 `edit` 工具调用，等待飞书原生审批卡出现。当前每次都只显示参数名。修复后，飞书审批卡必须像内部 IM 一样展示本次工具调用的完整输入；超长输入可以明确截断，但不得退化为只显示字段名。空输入仍应明确显示无输入，审批按钮、拒绝原因、owner 限制和两端 first-wins 行为保持不变。

## 根因

上游权限事件没有丢失数据。Gateway observer 将 kernel 事件中的完整 `tool_input` 复制进 permission request，并把同一 request 同时交给内部 IM 与飞书审批面；内部 IM 直接渲染该输入。数据只在飞书卡片渲染边界被压缩：`FeishuPermissionApprovalSurface` 构建 pending/deny card 时调用 `_tool_input_summary()`，该函数对 mapping 只提取 key 和数量，主动丢弃所有 value。因此截图中的参数名摘要是飞书 adapter 生成的最终展示，不是飞书客户端折叠，也不是 kernel/Gateway 传输缺失。

原始设计来自 `feat-447`：让飞书用户不必切到内部 IM，也能在原对话看见并完成同一个 kernel 工具审批；必须保住 interactive card、owner 校验、拒绝原因、两端 first-wins 和 resolved 状态同步。最初实现曾在卡片中展示截断后的完整 JSON 输入。回归由 commit `f566f3d395746fd5f4604f0c44975074f107955d`（`fix(feat-447): address feishu review blockers`）引入：它把完整 JSON preview 改成仅参数名摘要，并增加测试强制任何 value 都不可见。该修订只验证“值没有泄露”，没有覆盖审批者能否理解将执行的具体操作，也没有在 current spec 中形成这一产品约束，所以一个安全方向的局部 review 修订把审批卡的信息价值整体清空了。

本修复仍保持单 milestone、单一飞书展示边界和既有 request 数据流，不引入新的审批协议、权限状态机或通用脱敏机制；敏感值的跨工具统一保护继续由相关安全 change unit 独立处理。

## 修复

## 验证
