# bugfix-529: 飞书审批卡紧凑展示长工具输入

## Relations

- Depends on: bugfix-526
- Related: feat-447

## 原始报告

> 这符合你的预期？？
>
> 截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-29584189-c1f3-4455-8a89-990e972934e7.png`
>
> show me吧，干说我知道效果是啥
>
> 真能这个效果，肯定ok啊

## 澄清记录

- Q1: 长多行参数按“紧凑摘要 + 可展开全文”的通用方案修，可以吗？
  A(原话): 真能这个效果，肯定ok啊
  Agent 解读: 用户在看到基于真实截图生成的高保真 mockup 后确认该方向可作为验收目标；展示规则按值的形态和长度统一生效，不按工具名定制。

## 现象 / 复现

bugfix-526 合入后，飞书 1:1 审批卡已经能看到任意工具的 input values，但真实长多行输入仍无法高效审批。以 `edit` 调用为复现样本：`path`、`oldText`、`newText` 全部直接铺在卡片正文中，每一物理行都显示可见反引号，并在行尾显示 `↵`；合法的多行值即使没有超过字符预算，也会把卡片拉成长墙，审批按钮被推到页面底部。用户需要先穿过大量格式噪声和重复正文，才能判断实际操作。

稳定复现：从飞书 1:1 对话触发任意包含长多行 string 参数的工具审批。短值也会露出反引号；长值按原始行数无限制展开。修复后的通用卡片按值形态展示：短值紧凑直显；长多行值默认只显示少量可读摘要、总行数和明确的“查看完整值”入口，展开后能够看到未经丢失的完整内容。默认卡片在一屏内可扫描完，不显示反引号、`↵` 或 raw JSON。该规则只依赖字段值的形态与长度，对所有工具一致生效；群聊隐藏 values、owner 校验、审批按钮、拒绝原因、first-wins 和 resolved 状态保持不变。

## 根因

数据仍完整到达飞书 adapter，问题位于 bugfix-526 新增的展示投影。`_tool_input_elements()` 把每个 value 交给 `_code_lines()`；后者把多行字符串拆成物理行，为每一行调用 inline-code fence，并在除末行外的每行主动拼入 `↵`。飞书桌面端在该卡片字段中把 inline-code fence 作为普通字符呈现，而 `↵` 本来就是 payload 内容，所以两者都会直接暴露给用户。与此同时，`_MAX_INPUT_PREVIEW_CHARS` 只限制序列化字符数，没有限制展开行数或卡片视觉高度；多个未超字符预算的多行字段仍会全部展开。

回归由 bugfix-526 的两个提交共同引入：`39084f01ff40aa396ac216c9f1159248db6a869c` 建立逐字段 `lark_md` + 逐行 inline-code 展示；`4cb7980d2ad49b55897bc35c1be550e00d8de34c` 又把 `↵` 加进每个换行并补测试精确断言这些字符串。自动化测试只验证 payload 大小、字段数量和 Markdown 字面安全，没有验证飞书实际渲染后的高度与可扫描性；真实验收使用单行短 `.gitconfig`，没有覆盖用户此次截图中的长多行场景，因此错误体验被误判为可交付。

原始设计意图来自 feat-447 与 bugfix-526：审批者应在飞书原对话完成知情审批；任意工具共用一个 renderer，不按工具名硬编码；群聊不能向非 owner 泄露 values；既有审批状态机和按钮行为不变。本次修复必须保住这些不变量，只替换 values 的通用视觉投影和长值展开交互，不能退回参数名摘要或整段 JSON。

## 修复

- 将 1:1 approval card 的 input renderer 改为只依赖 value 形态的通用投影，不读取 `tool_name` 做分支。短值用灰底 `column_set` 分组，label/物理行数和 value 使用两个独立 element，避免客户端吞掉软换行层级。
- 长单行或多行值用默认收起的原生 `collapsible_panel`。灰底、灰色 5px 圆角边框、稳定 padding/spacing 与右侧原生旋转箭头由飞书原生卡片 payload 承载；header 显示 label、总行数和最多两行、每行最多 44 字符的摘要，长 path 中间省略；展开 body 显示平台预算内的完整值，收起恢复紧凑态。
- 删除初版自造的 `permission_input_detail` action、`Show full value` / `Show less` buttons、pending detail state 与对应复杂测试。原生 panel 展开/收起不回传审批 decision，不进入 owner/request/pending decision state machine。
- Tool metadata 对安全内部 identifier 使用 neutral `text_tag` 胶囊，含 `&<>` 或可闭合标签的名称回退为普通 literal-safe Markdown；Tool/Request 后用原生 divider 分层。DM Request 按 literal Markdown 转义，群聊 pending/deny 使用不含 question path/reason/@ 的固定安全提示。Tool/Request 和 values 不再产生可见 backtick、`↵` 或 raw JSON 墙。
- Values 恢复 card-wide 1200 字符预算，按最多 12 个展示字段均分；每个 value 在 Markdown 转义和 short/panel 选择前明确截断，避免转义膨胀后超过飞书 30KB。正常三字段样本仍在预算内，展开 body 保持完整。
- 保留既有 input 字段/嵌套预算、群聊 values 隐藏、owner 校验、Allow/Deny/Allow for session、拒绝原因、first-wins/resolved 行为；pending 与 deny-reason 卡共用同一 renderer。
- 同步 current external-channel spec，明确短值灰底直显、长值原生折叠和“展开/收起不等于审批 decision”的 current behavior。

## 验证

- Executed base: `7182db3b65b5d45b40b98520589e765d5c445835`（`origin/unit/bugfix-529`）。最终真实视觉执行 head: `492f283f8`；最终文档/证据 head 以 milestone branch handoff commit 为准。
- TDD：native container/panel 第一轮目标 `5 failed` 后转绿；视觉 delta 目标 `4 failed` 后 `4 passed`；真实 identifier seam 的 `custom_transform` case `1 failed` 后 target `2 passed, 7 deselected`；code-review budget/metadata/tag targets 红后 `4 passed, 7 deselected`。
- Regression：`pytest -q tests/unit/test_feishu_adapter_permission_approval.py tests/unit/test_feishu_client_interactive.py` → `14 passed in 24.70s`；覆盖 synthetic 长 path + 三行 oldText + 八行 newText、`edit` 与 `custom_transform`、原生 panel 样式/摘要/完整 body、card-wide budget、无 custom detail action/button、短值双 element、neutral Tool tag/divider、group metadata/input privacy 与既有审批状态机。
- Expanded regression：19 个 Feishu / permission / managed-channel 相关 test modules → `151 passed, 2 warnings in 115.04s`；两条 warning 均来自第三方 `lark_oapi` deprecation。
- 真实飞书：最终 message `om_x100b68ad457214acc2563d6eea4f6df`，approval `01bd5b5f1f2f438fab47197d7feca834`，request `bugfix529-native-panel-final-request`。orchestrator 独立确认 default、展开 oldText、收起三态与 mockup 契约一致；root textual verdict 见 `M1-fix/evidence/native-panel-fast-lane.md`。三态截图因包含个人 chat 列表只做本地瞬时检查，不提交原件。
- Code-review regression：12 个 5k ASCII/Markdown/emoji values 经转义与 UTF-8 序列化后 `<30_000` bytes 且每个 body 明确 truncated；正常三字段 body 逐一等于完整转义值；DM/group pending + deny 的 question privacy 与 unsafe tag injection 均有回归保护。
- 审批安全：验收全程未点 Allow/Deny/Allow for session；final product surface request 保持 pending，harness 停止时 decision count `0`，证明原生展开/收起没有提交 decision。
- 平台契约：真实 API 曾明确拒绝无效的 `header.padding`（`code=230099` / `ErrCode: 10002` / `invalid panel header padding`）；最终 payload 只保留平台接受的 panel body padding，并成功渲染。
- 质量门禁：focused tests、Ruff check/format、`scripts/docs-check` 与 `git diff --check` 均通过；最终扩大验证结果见 `M1-fix/progress.md`。
