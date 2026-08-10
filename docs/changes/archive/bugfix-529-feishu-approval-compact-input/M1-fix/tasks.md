# bugfix-529-M1: 紧凑展示飞书审批卡工具输入 — Tasks

> 对齐: ../fix.md

## 目标

修复飞书 1:1 工具审批卡的长输入墙：所有工具共用按 value 形态工作的 renderer。短值放在灰底容器中直接显示；长单行和长多行值使用飞书原生灰底折叠面板，header 默认展示字段名、总行数与最多两行紧凑摘要，原生展开后在同一面板内展示完整值。审批状态机与群聊隐私保持不变。

## 退出标准

- [x] 接近原始报告的长 path、oldText、newText 在默认 payload 中高度/可见行数有界，不含反引号、`↵` 或 raw JSON；path 摘要中间省略。
- [x] 长值使用原生 `collapsible_panel`，具备灰底、灰色边框、5px 圆角、稳定 padding/spacing；无自定义详情 action 或详情按钮。
- [x] 短值使用无展开箭头的灰底容器；Tool/Request metadata 不显示反引号。
- [x] renderer 不按 `tool_name` 分支；群聊 values 隐藏、owner 校验、Allow/Deny/Allow for session、拒绝原因、first-wins/resolved 行为保持不变。
- [x] 在真实飞书原生卡片验证长输入默认态与原生展开/收起态，并由 orchestrator 独立确认 mockup 对照；测试敏感写入未点击批准。
- [x] 12 个超长 ASCII/Markdown/emoji values 的最终 UTF-8 卡片 payload 小于 30KB且明确标记截断；正常三字段 fixture 展开 body 保持完整。
- [x] DM Request 按 literal Markdown 显示；群聊 pending/deny 不泄漏 question 中的 path/reason/@；unsafe tool identifier 不能闭合或注入 text_tag。

## 测试策略

- 可观察 seam: 从 `FeishuAdapter.send_permission_request()` 观察最终发送的飞书原生卡片 payload；长值由飞书客户端原生折叠，不再产生产品 callback，审批 callback 仍只接受既有 `permission_decision`。
- 回归样本: 与原始截图等价字段数/长度/行数的 synthetic 长 path + old/new 多行文本，同时参数化 `edit` 和 `custom_transform`，证明通用 renderer 无 tool-name 特判且测试不携带个人日记内容。
- 长值断言: 原生 panel 的 background/border/radius/padding/spacing、`expanded: false`、header 总行数、摘要最多两行且单行宽度保守有界、body 保留完整值；payload 不含 custom detail action/button。
- 短值与不变量: 灰底 `column_set`；保留 owner、approval request、pending/first-wins/resolved、拒绝原因、group privacy regression。
- 落层: `tests/unit/test_feishu_adapter_permission_approval.py`；已删除被 fast-lane 取代的 `tests/unit/test_feishu_permission_input_detail.py`，因为原生折叠没有产品 detail state/authority seam。
- 可选依赖: 沿用 `pytest.importorskip("lark_oapi")`。
- 一次性验收: 受控临时 harness 只经最终 `FeishuPermissionApprovalSurface` + 真实 `FeishuClient` 发卡并持有 pending request；不提交 secret/运行数据，保留 message locator + root textual verdict。包含个人 chat 列表的截图只做本地瞬时检查，不提交原件，结束后清理 listener/runtime。

### 受影响的既有测试处置

| 风险 / 行为 | 处置 | 保护 |
|---|---|---|
| 任意工具逐字段展示 input | rewrite-merge | 短值灰底直显；长值原生折叠；`edit`/非 `edit` payload 同构 |
| 大输入 payload 有界 | keep | 顶层字段、嵌套值预算与 panel 数量上限继续生效 |
| 换行与 Markdown 字面安全 | rewrite-merge | 无 fence/`↵`；真实长 path + old/new 摘要和完整 body |
| 群聊隐藏 values | keep | 群聊不产生 panel，不含 values |
| owner、拒绝原因、first-wins/resolved | keep | 原审批 decision state machine 不变 |
| 自定义详情 action | delete | 原生 panel 展开/收起不回传产品 action，不应存在 detail authority/state |

## UI / Interaction Plan

用户路径分类: `bug-regression`（飞书原生卡片 UI + 原生折叠交互）。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | 短值灰底直显；长值灰底 panel header 显示 label、line count、≤2 行摘要 |
| expanded | 客户端原生展开当前 panel，body 显示完整值；不触发审批 callback |
| collapsed | 客户端原生收起当前 panel，恢复紧凑 header |
| loading / error | N/A：原生折叠由飞书客户端本地托管 |
| disabled / submitting | decision 路径保持既有实现，原生 panel 无产品 pending/detail 状态 |
| permission denied | owner/request/pending decision regression 保持；群聊不显示 values |
| long content | 真实长 path + old/new 多行样本覆盖摘要宽度、行数与完整 body |
| missing / nullable | 保留 no input / non-mapping input 既有路径 |
| mobile / dark | N/A：验收目标为用户原始飞书 macOS light-mode 截图 |
| desktop | 真实飞书 macOS 默认/展开/收起截图，由 orchestrator 独立检查 |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| 用户确认 mockup `exec-49d68bb8-06f5-4ae4-8a12-a793b24185c4.png` | must-match：默认态一屏可扫；字段为灰底圆角分组；path 紧凑中间省略；长多行 header 有总行数与最多两行摘要；原生展开 body 显示全文 | 真实飞书 default/expanded/collapsed message locator + root textual verdict | worker/orchestrator |
| 原始失败截图 `codex-clipboard-29584189-c1f3-4455-8a89-990e972934e7.png` | must-not-match：无反引号、`↵`、raw JSON 或整墙正文 | root 在真实客户端逐项核对并记录 textual verdict | worker/orchestrator |
| 被否决 flat 版本 | must-not-match：不可用 flat div + 右漂自定义按钮拼装 | 保留 root textual finding；含个人 chat 列表的截图不入库 | worker |

## Roadpoints

### R1 — flat renderer + 自定义按钮

- 状态: DONE（失败方案已取证并由 R4 替代）
- 结果: 建立了真实长输入与非 `edit` 红测，但 flat div、视觉换行和右漂按钮与确认 mockup materially mismatch。
- 提交: `a4fda6e6a`。

### R2 — 自定义详情 action

- 状态: DONE（失败方案已删除并由 R4 替代）
- 结果: `permission_input_detail` 的 owner/request/pending 边界与零 decision-submit 曾通过自动化和真实 callback；用户否决整体视觉后，fast lane 已删除该 action、状态和测试。原生 panel 不回传审批 decision。
- 提交: `f59956bc1`，删除见 `43fb87cee`。

### R3 — full-chain 环境尝试

- 状态: DONE（历史 blocker 由获批 product-surface live seam 隔离）
- 结果: 隔离 Gateway 的 Feishu worker 多次超出既有 startup budget，未发卡；未杀其他 unit 进程、未修改 timeout、未用 raw/static direct send 降级。
- 证据: `evidence/live-environment-blocker.md`，提交 `da2295f60`。

### R4 — 原生 panel fast lane 与真实飞书复验

- 状态: DONE
- 步骤: 删除 R2 自定义详情交互；用灰底短值容器和原生 `collapsible_panel` 重建通用 renderer；红绿测后由真实 product approval surface 通过真实 client 发卡；orchestrator 独立检查默认/原生展开/收起视觉。
- 自动化: focused approval + client suite `12 passed`，Ruff 通过；详见 `evidence/native-panel-fast-lane.md`。
- Mechanism proof: message `om_x100b68ac895d48a0ddb314263a75a55` 已由 orchestrator 完成 default → 原生展开 oldText → 收起，展开灰 header + 白 body 且收起恢复；最终停止 decision count 0。该轮 visual-not-passed：短 path 缺 label/line count、panel 无展开 affordance、metadata 层级不足。
- R4 delta: 短值 label/value 拆为两个 element；long header 增加原生右侧旋转 icon；Tool 使用 neutral text_tag 且 metadata 后加 `hr`。新 message `om_x100b68acb95a00a0c0b01dc073d3f2d`，approval `8d35551638734e80811f02e6e726e427`，request `bugfix529-native-panel-r4-request`，executed head `a784ae582`，发送后 pending、decision count 0。
- R4 verdict: 原生层级/容器/箭头/展开收起均成立，但 neutral text_tag 将 `_` 显示成 literal `&#95;`，该卡 visual-not-passed。只修正 tag content escaping 后，最终候选 message `om_x100b68ad457214acc2563d6eea4f6df`，approval `01bd5b5f1f2f438fab47197d7feca834`，request `bugfix529-native-panel-final-request`，executed head `492f283f8`，发送后 pending、decision count 0。
- Final verdict: PASS。真实 message locator 与 root default/expanded/collapsed textual verdict 已保存；含个人 chat 列表的截图仅本地瞬时检查、不入库。final harness 停止时 decision count 仍为 0，未点审批；listener 与临时 harness/log 已清理。
- 提交: `43fb87cee`、`7e11ad594`、`a784ae582`、`492f283f8`。

### R5 — Code-review payload/privacy fix

- 状态: DONE
- 步骤: 恢复 card-wide values 预算；保护 DM/group Request metadata 和 unsafe Tool tag fallback；为 Request question、Tool display、button label 增加 512/80/80 的显示预算且不截断 action identifier/request id；删除含个人数据的截图证据与测试 fixture；保持正常 DM native panel 视觉 payload 不变。
- 验证: 12×5k 混合 values 与 oversized question/tool/option labels 的 pending/deny/resolved 卡按实际 client serializer seam 均 `<30KB` 且截断明确；正常三字段 panel body 和 `custom_transform` metadata/buttons 逐项精确不变；DM literal/group privacy/unsafe tag 回归；focused `15 passed in 9.28s`、expanded `151 passed, 2 third-party warnings`，Ruff/docs/diff 全绿。
- 提交: `378ce9a68`（第一轮实现、测试与截图删除）、`6c9753091`（display metadata budget closure）。
