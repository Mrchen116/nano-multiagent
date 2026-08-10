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

稳定复现：从飞书 1:1 对话触发一次需要人工授权的 `edit` 工具调用，等待飞书原生审批卡出现。当前每次都只显示参数名。修复后，1:1 飞书审批卡必须像内部 IM 一样展示本次工具调用的完整输入；超长输入可以明确截断，但不得退化为只显示字段名。群聊卡沿用同一字段布局但不向全群暴露 values，并明确提示到内部 IM 查看完整输入。空输入仍应明确显示无输入，审批按钮、拒绝原因、owner 限制和两端 first-wins 行为保持不变。

## 根因

上游权限事件没有丢失数据。Gateway observer 将 kernel 事件中的完整 `tool_input` 复制进 permission request，并把同一 request 同时交给内部 IM 与飞书审批面；内部 IM 直接渲染该输入。数据只在飞书卡片渲染边界被压缩：`FeishuPermissionApprovalSurface` 构建 pending/deny card 时调用 `_tool_input_summary()`，该函数对 mapping 只提取 key 和数量，主动丢弃所有 value。因此截图中的参数名摘要是飞书 adapter 生成的最终展示，不是飞书客户端折叠，也不是 kernel/Gateway 传输缺失。

原始设计来自 `feat-447`：让飞书用户不必切到内部 IM，也能在原对话看见并完成同一个 kernel 工具审批；必须保住 interactive card、owner 校验、拒绝原因、两端 first-wins 和 resolved 状态同步。最初实现曾在卡片中展示截断后的完整 JSON 输入。回归由 commit `f566f3d395746fd5f4604f0c44975074f107955d`（`fix(feat-447): address feishu review blockers`）引入：它把完整 JSON preview 改成仅参数名摘要，并增加测试强制任何 value 都不可见。该修订只验证“值没有泄露”，没有覆盖审批者能否理解将执行的具体操作，也没有在 current spec 中形成这一产品约束，所以一个安全方向的局部 review 修订把审批卡的信息价值整体清空了。

本修复仍保持单 milestone、单一飞书展示边界和既有 request 数据流，不引入新的审批协议或权限状态机。由于飞书群卡对全群成员可读，通用 renderer 只在 owner 的 1:1 对话展示 values；群聊保留字段名和审批按钮，但 values 统一隐藏，避免 owner 点击校验之前泄露 token、私钥或其他敏感内容。

## 修复

- 将飞书审批卡的 input renderer 从“参数数量 + 参数名”改为通用字段区，pending card 与拒绝原因 card 共用同一展示逻辑。任意工具的 mapping input 都按原始参数顺序逐字段显示粗体 label 和代码样式 value；非 mapping input 统一落在 `value` 字段，不按 `tool_name` 硬编码卡片。
- 字符串按原始行展示，并用 `↵` 明确标记换行；嵌套对象先限制为 3 层、每层 8 项，再格式化展示。顶层最多展示 12 个字段，label 最长 80 字符，1200 字符 value 预算按字段均分并明确标记截断，避免卡片超出飞书大小限制。
- 参数 label 对 Lark Markdown 特殊字符做实体编码，value 复用 Feishu client 的动态 code fence；1:1 对话展示完整 values，群聊统一显示 `hidden in group chat` 并引导到内部 IM 查看详情。该规则按会话隐私边界生效，不按工具名特判。
- 保留既有 interactive card 按钮、owner 校验、拒绝原因、内部 IM / 飞书 first-wins 和 resolved card 更新路径，不修改权限请求协议或状态机。
- 把原先强制隐藏 values 的单测改为验证任意工具的参数被渲染为原生 `div.fields`，且不再出现整段 JSON 外壳；另覆盖群聊隐藏 values、超大通用输入有界、换行可辨、Markdown label 与反引号保持字面量。

## 验证

- Red：在旧实现上运行 `test_permission_cards_show_tool_input_values`，断言 `cat ~/.ssh/id_rsa`、`.gitconfig` 和 `secret-token-value` 可见；测试按预期失败，实际卡片仅含 `3 parameters: command, path, token`。
- Green：最终通用字段实现运行 approval + client + 权限 pipeline，共 `21 passed`；扩大到 `tests/unit/test_feishu_*.py` 和权限 pipeline，共 `81 passed`。
- 静态检查：相关 Python 文件 `ruff check` 通过，`git diff --check` 通过。
- 真实入口：在 `39084f01f` 上通过隔离 IM + Gateway 完整跑通“飞书消息 → kernel 权限请求 → native card”，并完成飞书桌面端视觉检查；最终 head `4cb7980d2` 的同一 product card builder 再直接发送真实飞书卡片，平台返回 `interactive`，仍按 `path` / `oldText` / `newText` 展示并保留三个按钮。最终 head 的完整 Gateway 启动受同机其他 worktree 高负载影响，Feishu worker 连续超过既有 5 秒初始化门槛；未把该独立启动预算问题混入本 unit。取证见 [`M1-fix/evidence/feishu-approval-input.md`](M1-fix/evidence/feishu-approval-input.md)。
- Code review：full 模式 finder 产生的 6 个候选全部经 verifier 确认并修复；closure 模式逐项返回 `closed`，最终 finding 数组为 `[]`。
