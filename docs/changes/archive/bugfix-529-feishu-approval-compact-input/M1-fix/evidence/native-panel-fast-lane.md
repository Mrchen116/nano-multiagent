# bugfix-529-M1 native panel fast-lane evidence

## Verdict

PASS。自动化与真实发卡、默认态、原生展开态、收起态、pending/零 decision-submit 和 runtime cleanup 均已完成；视觉结论由 orchestrator 在飞书 macOS 客户端独立给出，不是从 payload 推断。

## 被否决的 flat 版本

- 用户反馈：`现在这个效果跟你生成图片的那个效果千差万别，你这个效果丑多了好不好？`
- Root finding：flat div 无灰色容器/边界；label 与 line count 挤在一起；摘要因客户端视觉换行仍形成正文墙；三个右漂详情按钮像拼装表单，和用户确认 mockup materially mismatch。
- Evidence handling：root 在真实飞书客户端现场检查 default/expanded/collapsed 并给出上述 textual verdict；原截图包含个人 chat 列表，只用于本地瞬时检查，不提交原件，也不生成替代假截图。

因此 `a4fda6e6a` / `f59956bc1` 的实现被标记为 REJECTED；失败轨迹保留，但 `permission_input_detail`、`Show full value` / `Show less`、pending detail state 和独立 detail tests 已在 `43fb87cee` 删除。

## Native panel implementation

- Executed base: `7182db3b65b5d45b40b98520589e765d5c445835`
- Implementation commits: `43fb87cee`、`7e11ad594`
- Renderer contract:
  - 所有工具共用按 value 形态工作的 renderer，无 `tool_name` 分支。
  - 长值为默认折叠的原生 `collapsible_panel`；灰底、灰色 5px 圆角边框、panel body padding 和 vertical spacing 均进入发送 payload。
  - header 含 label、物理总行数与最多两行紧凑摘要；摘要每行最多 44 字符，长 path 使用中间省略。
  - 展开 body 携带完整、Markdown-safe 的 value；原生展开/收起不发送产品 callback，也不能提交审批 decision。
  - 短值为无展开箭头的灰底 `column_set`；Tool/Request metadata 无 inline-code fence。
  - 群聊继续只显示字段名与 privacy notice，不发送 values 或 panel。

## Red → Green

- Red：五个目标 renderer tests 失败，旧 payload 没有 `inputField*` 原生 container/panel，不能满足背景、边框、圆角和 native-collapse contract。
- Green：
  - `pytest -q tests/unit/test_feishu_adapter_permission_approval.py tests/unit/test_feishu_client_interactive.py` → `12 passed in 5.84s`
  - native long-panel target → `2 passed, 7 deselected`
  - Ruff → passed
  - `git diff --check` → passed
- 样本：接近用户截图的长 path、三行 oldText、八行 newText；同一测试参数化 `edit` 与 `custom_transform`。
- Assertions：panel background/border/radius/padding/spacing、默认折叠、header 行数与摘要宽度、body 完整值、无 backtick/`↵`/raw JSON、无 custom detail action/buttons；group privacy 与既有审批状态 regression 保持。

## Real platform schema correction

首次 native-panel 发送被飞书拒绝：

```text
code=230099
ErrCode: 10002
ErrMsg: invalid panel header padding
```

这证明 `collapsible_panel.header.padding` 不是当前真实飞书原生卡片 API 可接受字段。`7e11ad594` 只移除了 header padding；panel 本身的 grey background、grey border、5px radius、body padding 与 spacing 保留。第二次发送成功。

## Real message locator

- Product seam: 最终 `FeishuPermissionApprovalSurface` 持有真实 pending request，由真实 `FeishuClient` 发送 interactive card；没有 raw/static card direct send。
- App/profile: 专用 `feishu:e2e` App/Bot/profile；secret 与运行数据未进入仓库。
- Executed head: `7e11ad594`
- Message ID: `om_x100b68ac895d48a0ddb314263a75a55`
- Approval ID: `db4550910f234d57b329eb998280129a`
- Request ID: `bugfix529-native-panel-request`
- Send result: `pending`
- Decision count after send: `0`
- Approval buttons: 未点击。

## Native mechanism proof / visual delta

Orchestrator 在第一张 native-panel 卡完成 default → 原生展开 oldText → 收起；真实客户端现场确认展开后为灰 header + 白 body，收起后恢复。旧 harness 停止记录仍为 decision count `0`，未点击审批。这证明原生折叠机制成立，但该轮不等于视觉通过：

- short path 的 label/line count 没有渲染，只剩 path 值；
- panel 可点击但完全没有展开 affordance；
- Tool/Request metadata 层级和确认 mockup 仍有差距。

## R4 visual fix loop

- Red：四个目标 case 失败；旧 payload 没有分开的 short label/value elements、没有 panel header icon、没有 neutral Tool text_tag / `hr`。
- Fix：
  - 每个 short container 含两个独立 markdown elements，第一行显式 `label · N line(s)`，第二行 value；
  - 每个 long panel header 增加 `icon: {tag: standard_icon, token: down-small-ccm_outlined, size: 16px 16px}`、`icon_position: right`、`icon_expanded_angle: 180`；
  - Tool value 使用 tool-neutral 的 neutral `text_tag`，Tool/Request metadata 后增加 `hr`；仍无 tool-name 分支。
- Green：target `4 passed, 5 deselected`；approval + client focused suite `12 passed in 6.18s`；Ruff check/format 与 diff-check 通过。
- Commit: `a784ae582`

## New real message locator

- Executed head: `a784ae582`
- Message ID: `om_x100b68acb95a00a0c0b01dc073d3f2d`
- Approval ID: `8d35551638734e80811f02e6e726e427`
- Request ID: `bugfix529-native-panel-r4-request`
- Send result: `pending`
- Decision count after send: `0`
- Old message was not updated.

## R4 real verdict / final candidate

Orchestrator 确认 R4 卡的 neutral Tool tag、divider、path label + line count、三块灰色圆角容器、每块右侧 native down arrow 均已渲染；展开 oldText 后 arrow up、灰 header + 白色完整 body，收起恢复，且未点审批。唯一剩余 blocker 是 neutral text_tag 把 `_` 显示成 literal `custom&#95;transform`。

- Red: 真实 `custom_transform` identifier case failed；`edit` case passed。
- Fix: text_tag 内文不再走会实体化 `_` 的通用 Markdown escape；只转义 `&`、`<`、`>` 以防闭合标签，其余视觉 payload 不变。
- Green: identifier target `2 passed, 7 deselected`；focused suite `12 passed in 5.53s`；Ruff/format/diff-check passed。
- Commit: `492f283f8`
- Final candidate message: `om_x100b68ad457214acc2563d6eea4f6df`
- Approval: `01bd5b5f1f2f438fab47197d7feca834`
- Request: `bugfix529-native-panel-final-request`
- Send state: pending, decision count `0`
- Old R4 card was not updated; its harness stopped at decision count `0`.
- Verdict: PASS。orchestrator 确认 Tool 精确渲染 `custom_transform`，无 entity。

## Final visual evidence

- Message locator: `om_x100b68ad457214acc2563d6eea4f6df`；approval `01bd5b5f1f2f438fab47197d7feca834`；request `bugfix529-native-panel-final-request`。
- Orchestrator textual verdict: PASS。default 真实显示 neutral `custom_transform` chip、divider、path/oldText/newText 灰色圆角分组、line count、有界摘要、右侧 down arrows 和审批按钮；oldText 展开显示 up arrow + grey header/white full body，收起恢复。
- Evidence handling: 三态截图包含个人 chat 列表，只用于 root 当场本地检查，不提交原件；不生成或提交替代假截图。
- State: 全程未点审批；final harness ready 为 pending/decision count `0`，停止时 decision count 仍为 `0`。
- Cleanup: 所有 `bugfix529-*` tmux sender、进程、临时 harness 与 log 已清理；没有提交 secret 或运行数据。

## Code-review fix round

- Card-wide value budget: 对最终 `_tool_input_value` 输出按已展示字段数分配 `_MAX_INPUT_PREVIEW_CHARS=1200`，每字段先明确截断再选择 short/panel；移除独立的 5000 字符 per-panel 上限。12 个 5k ASCII/Markdown/emoji values 经 Markdown 转义和 UTF-8 序列化后仍 `< 30_000` bytes，每个 panel body 明确以 `... truncated` 结尾；正常三字段 fixture 的每个 panel body 则精确等于对应完整转义值。
- Metadata privacy: DM 的 Request 走 literal Markdown escape；group pending/deny 固定显示 `Review details in internal IM.`，不携带 question 中的 reason/path/@。安全内部 identifier 继续使用 neutral text_tag；包含 `&<>` 或可闭合标签的名称回退为普通 escaped Markdown，不把 entity 放进 text_tag。
- Fixture privacy: 长 path/old/new regression 改为同等字段数、行数和长度形态的 synthetic tool-neutral 文本。
- Red → Green: budget、metadata privacy/tag injection targets 先失败后 `4 passed, 7 deselected`；focused approval + interactive client `14 passed in 24.70s`；expanded related regression `151 passed, 2 third-party warnings in 115.04s`。
- Commit: `378ce9a68`。

## Verifier metadata-budget closure

- Residual finding: 30k-char question alone produced an actual client payload of `31,268` bytes. The combined regression with an oversized question, unsafe tool name, oversized option labels, and 12×5k emoji values reproduced `395,465` bytes before the fix.
- Display-only budgets: Request question `512`, Tool display `80`, and button/resolved decision display `80` characters. Pending, deny, and resolved cards share these bounds; action decision identifiers, request id, and internal resolved state are not truncated.
- Serializer evidence: the regression uses the same `json.dumps(card, ensure_ascii=False).encode()` seam as `FeishuClient.send_interactive_message()`; all three states serialize below `30_000` bytes and visibly include `... truncated`.
- Visual non-regression: the normal accepted fixture still has exact `custom_transform`, Request, three option labels, and per-panel bodies. No live card was resent because this closure does not change that accepted payload.
- Red → Green: oversized metadata target failed at `395,465` bytes, then passed (`1 passed, 11 deselected`); focused approval + interactive client suite `15 passed in 9.28s`.
- Commit: `6c9753091`。

## Final gates

- Focused approval + interactive client: `15 passed in 9.28s`
- Expanded Feishu / permission / managed-channel regression: `151 passed, 2 warnings in 115.04s`
- Ruff check/format: passed
- Documentation integrity: passed（228 maintained Markdown sources, 67 required routes）
- Diff checks: passed

若真实客户端没有显示灰底分组、header 摘要无法紧凑承载，或原生展开 body 不能完整显示值，则本 milestone 按目标 BLOCKED，不回退到 flat buttons。
