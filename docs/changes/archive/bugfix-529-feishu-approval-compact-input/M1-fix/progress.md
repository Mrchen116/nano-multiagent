# bugfix-529-M1 — Progress

## 启动基线

- Executed base: `7182db3b65b5d45b40b98520589e765d5c445835`（`origin/unit/bugfix-529`）。
- Context: 完整读取 `fix.md`、archived bugfix-526、current external-channel spec、代码/测试、coding/testing/evidence/worktree-runtime 规范，并对照原始失败截图与用户确认 mockup。
- Baseline: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_feishu_adapter_permission_approval.py tests/unit/test_feishu_client_interactive.py` → `10 passed`。
- Scope clarification: 真实长输入默认/展开态、无 tool-name 特判为硬退出条件，平台能力不满足则 BLOCKED。初版曾允许 pending detail action；用户否决真实 flat card 后，orchestrator 明确 fast lane 必须改用原生 `collapsible_panel` 并删除自定义详情 action/button。

## R1 — 通用紧凑 renderer 红绿（已被视觉验收否决）

- 状态: DONE（失败方案已取证并由 R4 替代）
- Context: bugfix-526 的单个 `div.fields` 会把每个 value 逐物理行包 inline-code，并主动加入 `↵`；字符预算无法约束三个合法长字符串形成的视觉高度。
- Decision: 将通用 input projection 改为每字段一个原生 `div`。短值经 Lark Markdown 字面转义后直接显示；超过 2 行或单行 80 字符的值显示最多 2 行、单行头尾省略、物理总行数和 `Show full value` button；顶层字段/嵌套值的既有预算继续生效。pending 与 deny-reason card 共用 renderer，tool 名也不再使用会在桌面端露出的 inline-code fence。
- Rationale: 规则仅依赖 value 的长度/行形态与字段序号，不读取 `tool_name`；每个长字段默认最多 3 行正文，卡片高度由字段上限而不是原始文本行数决定，同时保留知情审批所需的摘要和进入全文的显式入口。
- Evidence:
  - Tests: Red：focused renderer 组 `5 failed`，失败 payload 仍是单个 fields 容器并完整包含 `↵`/反引号长墙；Green：同组 `5 passed, 4 deselected`。
  - Entry: 真实飞书入口安排在 R3；R1 已从 `FeishuAdapter.send_permission_request()` 的发送 payload seam 验证默认投影。
  - Frontend State Matrix: default/long-content/short-content 已覆盖；loading/error/mobile/dark 为 N/A，理由见 tasks.md。
  - Browser QA: N/A（飞书原生客户端验收在 R3）。
  - E2E/Regression: `tests/unit/test_feishu_adapter_permission_approval.py::{test_permission_cards_render_any_tool_input_as_fields,test_permission_card_bounds_large_generic_input,test_permission_card_compacts_realistic_long_input_for_every_tool,test_permission_card_preserves_newlines_and_markdown_literals_without_fences}`；`5 passed`。
  - Visual/Interaction: 默认 payload 可见文本总换行有界、无反引号/`↵`/顶层 raw JSON；真实截图待 R3。
  - Prototype Comparison: 自动化确认 mockup 的默认摘要、总行数与详情入口结构；真实视觉 match/deviation 待 R3。
- Rollback: 回退本 roadpoint 的 `fix(bugfix-529/M1/R1)` commit。
- Commits: `a4fda6e6a`。
- Visual rejection: root 使用真实飞书客户端检查后确认 flat div 无灰色容器/边界，label 与 line count 拥挤，长文本因客户端视觉换行仍成墙；右漂 `Show full value` 按钮呈现为拼装表单。用户原话：`现在这个效果跟你生成图片的那个效果千差万别，你这个效果丑多了好不好？`
- Durable evidence: `evidence/native-panel-fast-lane.md` 中的 root textual finding；原截图含个人 chat 列表，仅本地瞬时检查，不提交原件。
- Next: R2 历史轨迹保留；最终实现由 R4 的原生 panel 替代。

## R2 — 详情 action 状态边界红绿（已删除）

- 状态: DONE（失败方案已删除并由 R4 替代）
- Context: card button callback 原先只接受 `permission_decision`，详情按钮没有 handler；直接复用 decision action 会误入审批提交状态机，且必须防止群聊或伪造 callback 借展开读取 values。
- Decision: 新增只读 `permission_input_detail` action。handler 要求 approval id、原 request id、字段序号、owner 和 DM privacy 边界全部匹配，并且 request 仍为 pending；它不修改 pending/submitting/decision，也不调用 kernel callback，只基于原 request 返回完整替换卡。展开只展开所选字段，其余字段保持摘要；`Show less` 以同一 action 返回默认卡。resolved/expired/closed 返回既有状态卡，群聊从 renderer 起不生成详情按钮。
- Rationale: 飞书 card callback 原生支持用完整卡片响应替换当前消息；以独立 action namespace 和只读重建保持审批 first-wins 状态机完全不变，同时让 server-side pending request 成为全文唯一数据源，action value 不携带敏感 input。
- Evidence:
  - Tests: Red：`pytest ... -k input_detail` → `2 failed`，当前 handler 对展开与 resolved 详情 action 均返回 `None`；Green：同组 `2 passed, 9 deselected`。
  - Entry: callback response 走产品 `FeishuAdapter._handle_card_action()` → `FeishuPermissionApprovalSurface` 真实 seam；真实平台点击在 R3。
  - Frontend State Matrix: expanded/collapsed、permission-denied、resolved、submitting 边界已覆盖；group privacy 由既有 regression 保持。
  - Browser QA: N/A（飞书原生客户端验收在 R3）。
  - E2E/Regression: `tests/unit/test_feishu_permission_input_detail.py` 覆盖展开/收起、三审批按钮仍在、callback 零提交、非 owner、错 request、resolved；approval + detail + client suite `14 passed`。
  - Visual/Interaction: expanded payload 包含原 newText 末行和 `Show less`，collapsed payload 再次隐藏末行并显示 `Show full value`；真实视觉待 R3。
  - Prototype Comparison: 交互 payload 符合 mockup 的在当前卡查看全文/回到紧凑态；真实平台 match/deviation 待 R3。
- Rollback: 回退本 roadpoint 的 `fix(bugfix-529/M1/R2)` commit。
- Commits: `f59956bc1`。
- Visual rejection: action/state 本身满足 owner/request/pending 与零 decision-submit，但它服务于被否决的 flat button UI，不能作为最终实现保留。
- Removal: `43fb87cee` 删除 `_ACTION_INPUT_DETAIL`、pending detail state、`Show full value` / `Show less` 与 190 行 detail action tests；原生 panel 展开/收起完全由飞书客户端托管，不回传产品 callback。
- Durable evidence: `evidence/native-panel-fast-lane.md` 中的 root textual finding；原截图不入库。
- Next: R4 用原生 `collapsible_panel` 完成同一用户目标，不自行恢复 flat fallback。

## R3 — 真实飞书 full-chain 验收尝试（历史环境阻塞）

- 状态: DONE（历史 blocker 由获批 product-surface live seam 隔离）
- Context: 退出硬条件要求在真实飞书原生卡片上走默认态 → `Show full value` → `Show less`，并与用户确认 mockup 对照；direct product-card send 不能证明 Gateway pending state 与 callback RPC，因此不作为替代。
- Decision: 使用仓库 `e2e-up.sh --feishu`、专用非 default profile 和隔离 worktree runtime。发现 Gateway 的 Feishu worker 在既有 5 秒 ready budget 内初始化失败后，按 `systematic-debugging` 定位并保持超时/代码不变；不杀其他 unit 测试，等待无 pytest 窗口后在受控 tmux 做最后一次 full-chain 启动。
- Rationale: 短 shell 的一次 startup-ready 结果随后因宿主回收而退出，不能承载点击验收；tmux 才是 runtime 文档要求的持久生命周期。最后一次 clean-window tmux 仍失败，继续 direct-send 会降低用户明确的验收目标，修改 startup budget 又超出本 unit 范围。
- Evidence:
  - Tests: R1/R2 focused approval + detail + client suite `14 passed`；本 roadpoint 未声称 live pass。
  - Entry: BLOCKED。最后一次 clean-window `e2e-up.sh --feishu` 在 Gateway 日志报 `ERROR feishu worker did not initialize`，启动器报 `Gateway did not signal readiness within 30s`；未发送 approval card、未点击任何审批或详情 action。
  - Frontend State Matrix: 自动化 payload 已覆盖 default/expanded/collapsed/group privacy/resolved；真实 Feishu desktop 状态未完成。
  - Browser QA: BLOCKED；未进入可操作的飞书原生卡片。
  - E2E/Regression: ingress probe 与长输入 full-chain 均未能在持久栈上执行；不能用 unit/integration 代替。
  - Visual/Interaction: BLOCKED；无 default/expanded/collapsed 真实截图或 message/card locator。
  - Prototype Comparison: BLOCKED；mockup 的默认高度、详情点击和收起态尚未获得真平台对照。
- Rollback: 代码已在 `a4fda6e6a` / `f59956bc1` 独立提交；blocker 现场仅增加文档，不改产品行为。
- Commits: `da2295f60`。
- Next: orchestrator 允许 R4 使用不降级的 product-surface live seam：最终 `FeishuPermissionApprovalSurface` 持有 pending request，并通过真实 `FeishuClient` 发卡；无关 Gateway startup 不再阻塞平台视觉验证。

### Environment blocker audit

- 2026-08-10 15:17–15:47 +08:00：首次启动时 IM ready、Gateway 报 worker init timeout；发现另一个 unit 全量 pytest 与高主机负载。该进程结束后同一命令曾完成 startup ready，证明 config/profile/Bot identity 可用，但短工具 shell 被宿主回收，未能作为持久验收栈。
- 随后按 runtime 文档改用 `tmux=bugfix529-e2e`；两次并发 pytest 窗口内稳定复现同一 worker init timeout，均逐次执行 `e2e-down.sh` 并释放 listener/credentials。
- orchestrator 确认竞争进程属于其他 unit，不得误杀；等待全部已知 pytest 结束后，最后一次 clean-window tmux 启动仍报同一 timeout。因此判定当前 live env 阻塞，而不是平台 capability mismatch 或实现验证通过。
- 清理：`.im.pid`、`.gateway.pid`、`.gateway-config.yaml`、`.e2e-jwt-secret`、`channel-credentials-v1.pem` 已删除；`bugfix529-e2e` tmux session 已关闭；本次 IM 端口无 listener。

## R4 — 原生 panel fast lane 与真实飞书复验

- 状态: DONE
- Context: 飞书原生卡片 `collapsible_panel` 支持 grey background、grey border、圆角、body padding/spacing 与客户端折叠，不需要自定义详情 callback。短值用无展开箭头的灰底 `column_set`，避免退回 flat div。
- Decision:
  - 长值统一投影为默认 `expanded: false` 的原生 panel。header 为 plain text，包含 `label · N line(s)` 与最多两行、每行最多 44 字符的摘要；path 单行使用中间省略。body 保留完整、Markdown-safe 的 value。
  - panel 使用 `background_color: grey`、`border: {color: grey, corner_radius: 5px}`、`padding: 0px 12px 10px 12px`、`vertical_spacing: 4px`；短值使用 `background_style: grey-50` 与 `padding: 8px 12px`。
  - Tool/Request metadata 去掉 inline-code fence；renderer 只看 value 形态，不读 `tool_name`。
  - 不保留任何 `permission_input_detail` action/button/state；只有既有审批按钮能进入 decision handler。
- Platform schema correction: 首次真实发送携带 `header.padding` 被飞书明确拒绝：`code=230099` / `ErrCode: 10002` / `invalid panel header padding`。按真实平台 contract 仅移除无效的 header padding，panel body padding 与全部视觉要求保持；`7e11ad594` 固化该约束。
- Evidence:
  - Red: 五个目标 renderer tests 失败，旧 payload 没有 `inputField*` 原生 container/panel。
  - Green: approval + client focused suite `12 passed in 5.84s`；target native-panel run `2 passed, 7 deselected`；Ruff 与 diff-check 通过。
  - Generic: `test_permission_card_compacts_realistic_long_input_for_every_tool` 参数化 `edit` / `custom_transform`，真实长 path + old/new 样本均生成同构 native panels。
  - Privacy/state: group values 不进入 panel；owner、request、pending/first-wins/resolved、Allow/Deny/Allow for session 和拒绝原因 regression 保持。
  - Live: 受控临时 harness 由最终 product approval surface 持有 pending request，并经真实 `FeishuClient` 发送：message `om_x100b68ac895d48a0ddb314263a75a55`；approval `db4550910f234d57b329eb998280129a`；request `bugfix529-native-panel-request`；executed head `7e11ad594`；发送后 status `pending`、decision count `0`。
  - Native mechanism proof: orchestrator 已在 message `om_x100b68ac895d48a0ddb314263a75a55` 完成 default → 原生展开 oldText → 收起；AX/截图确认展开灰 header + 白 body、收起恢复。旧 harness 最终 `stopped` 且 decision count `0`，未点击审批。
  - Visual delta: 该轮仍不通过：短 path 只渲染值、label/line count 缺失；panel 可点击但无展开 affordance；顶部 Tool/Request 层级与 mockup 不足。
- R4 visual fix loop:
  - Red: `render_any_tool_input_as_fields`、`compacts_realistic_long_input_for_every_tool[edit/custom_transform]`、`preserves_newlines...` 共 `4 failed`，分别暴露旧 payload 仍为单个 short markdown、无 panel icon、无 neutral Tool tag/hr。
  - Implementation: 短值 label 与 value 分成两个独立 markdown elements，label 显式包含物理行数；long panel header 增加 `standard_icon/down-small-ccm_outlined`、right position、expanded angle 180；pending 与 deny metadata 共同使用 neutral `text_tag` + `hr`。
  - Green: target `4 passed, 5 deselected`；approval + client suite `12 passed in 6.18s`；Ruff check/format 与 diff-check 通过。
  - New live: 新 head `a784ae582` 通过同一 product surface seam 发全新卡，未更新旧卡。message `om_x100b68acb95a00a0c0b01dc073d3f2d`；approval `8d35551638734e80811f02e6e726e427`；request `bugfix529-native-panel-r4-request`；pending、decision count `0`。
  - Visual: orchestrator 确认 neutral Tool tag、divider、path label/line count、三块灰色圆角容器、右侧 native arrow、展开 grey header/white full body、arrow rotation 与收起恢复均成立，且未点审批。唯一 blocker 是 Tool tag 把 `_` 渲染为 literal `custom&#95;transform`。
- R4 text-tag fix loop:
  - Red: 真实 identifier target 中 `custom_transform` case `1 failed`（`edit` case passed），payload 仍为 `custom&#95;transform`。
  - Root cause/fix: 通用 Markdown escape 不适用于 `<text_tag>` 内文；改用仅处理 `&`、`<`、`>` 的 tag-content escape，保留内部工具 identifier 的 `_`，同时阻断闭合标签注入。其余视觉 payload 未改。
  - Green: identifier target `2 passed, 7 deselected`；approval + client suite `12 passed in 5.53s`；Ruff check/format 与 diff-check 通过。
  - Final live: head `492f283f8` 经同一 product surface seam 发全新卡，未更新旧卡。message `om_x100b68ad457214acc2563d6eea4f6df`；approval `01bd5b5f1f2f438fab47197d7feca834`；request `bugfix529-native-panel-final-request`；pending、decision count `0`。
  - Visual: PASS。orchestrator 在 final message 独立确认 neutral chip 精确显示 `custom_transform`（无 entity）、divider、path/oldText/newText 灰色圆角分组、line count、摘要、右侧 down arrows 与审批按钮；展开 oldText 显示 up arrow + grey header/white full body，收起恢复。
  - State: 全程未点审批；final harness 停止记录为 decision count `0`，request 在验收期间保持 pending。原生展开/收起未触发产品 decision callback。
  - Durable visual evidence: final message locator + root textual verdict 记录于 `evidence/native-panel-fast-lane.md`；三态截图含个人 chat 列表，仅本地瞬时检查，不提交原件。
  - Cleanup: `bugfix529-native-final` 及所有本 unit live tmux/session、sender 进程与 `/private/tmp/bugfix529-*` harness/log 已清理；未触碰其他 unit 进程。
- Rollback: 回退 `43fb87cee` / `7e11ad594`；不得恢复已被用户否决的 flat button 版本。
- Commits: `43fb87cee`、`7e11ad594`、`a784ae582`、`492f283f8`。
- Next: milestone 实现、证据、门禁、runtime cleanup 与 branch push 均完成；按 orchestrator 最新指令保留 branch/worktree，等待其执行 unit merge。

## Final verification

- Expanded regression: code-review fix 后 19 个 Feishu / permission / managed-channel 相关 test modules → `151 passed, 2 warnings in 115.04s`；warnings 均来自第三方 `lark_oapi` 的 datetime/event-loop deprecation。
- Focused regression: approval + interactive client → `15 passed in 9.28s`。
- Static/docs: Ruff check/format passed；documentation integrity passed（228 maintained Markdown sources, 67 required routes）；`git diff --check` / staged diff-check passed。
- Real product: final message `om_x100b68ad457214acc2563d6eea4f6df` default/expanded/collapsed PASS；停止时 decision count `0`；runtime cleanup complete。
- Current spec: `docs/specs/gateway/external-channels.md` 已同步最终原生折叠与零 decision-submit 行为。
- Handoff: milestone branch 提交并推送后交 orchestrator；按 orchestrator 最新指令保留 branch/worktree，由其执行 unit merge。

## R5 — Code-review payload/privacy fix

- 状态: DONE
- Context: code review 发现 native panel 的 per-field 5000 字符上限可让 12 个转义后 values 将卡片推到 30KB 平台限制之外；group Request 仍原样携带 question 的 path/reason；unsafe tool identifier 在 text_tag 内可能闭合标签；测试和截图证据含个人数据。
- Decision:
  - 复用 `_MAX_INPUT_PREVIEW_CHARS=1200` 作为 card-wide values 预算，按展示字段数分配 `max(1, 1200 // len(items))`，对 `_tool_input_value` 结果先 `_truncate` 再决定 short/panel；panel body 直接使用该已预算值，移除 5000 per-field 上限。
  - DM question 走 literal Markdown escape；group pending/deny 固定 Request 为 `Review details in internal IM.`。仅 `[Unicode alnum, _, ., -]` 内部 identifier 进入 neutral text_tag，含 `&<>`/闭合标签的名称回退普通 escaped Markdown。
  - 将个人日记 fixture 换成同等字段数、行数和长度形态的 synthetic policy 文本；删除 7 张包含个人 chat 列表的历史/最终截图，证据只保留真实 message locator 与 root textual verdict。
  - 不改正常三字段 DM 的 container/panel/header/icon/action 结构；用户已接受的 native 展开/折叠视觉无需重复 live 发卡。
- Evidence:
  - Red: 12×5k values 未明确截断且超预算；DM question 原样 Markdown；group pending 泄漏 question；unsafe tool 名仍嵌入 text_tag。
  - Green: 定向 budget/metadata/generic targets `4 passed, 7 deselected`；focused approval + interactive client 第一轮 `14 passed`。
  - Exactness: 正常 path/old/new 三个 panel body 逐一等于对应完整转义值；budget case 每个 panel body 以 `... truncated` 结尾，整卡 UTF-8 `<30_000` bytes。
  - Privacy: DM/group pending + deny 均覆盖；safe `custom_transform` 保留 neutral chip，unsafe identifier 无 text_tag 注入。
- Rollback: 回退 `378ce9a68`；不得恢复已删除的个人数据截图。
- Commits: `378ce9a68`。
- Verifier closure:
  - Residual finding: 单独 30k-char question 即可让实际 client payload 达到 `31,268` bytes；组合 30k question、oversized unsafe tool、oversized option labels 与 12×5k emoji values 的红测复现为 `395,465` bytes。
  - Decision: Request question、Tool display、button/decision display 分别在渲染前限制为 512/80/80 字符；pending、deny、resolved 一致应用。仅约束显示文本，action decision identifier、request id 与内部 resolved decision 保持原值。
  - Evidence: 使用与 `FeishuClient.send_interactive_message()` 相同的 `json.dumps(card, ensure_ascii=False).encode()` seam；修复后 pending/deny/resolved 均 `<30_000` bytes 且显示 `... truncated`。正常 `custom_transform`、Request、三个按钮 label 与三字段 panel body 逐项精确不变。
  - Tests: verifier target `1 passed, 11 deselected`；focused approval + interactive client `15 passed in 9.28s`。
- Commits: `378ce9a68`、`6c9753091`。
- Next: focused/expanded regression、Ruff/docs/diff 与 evidence cleanup 均完成；提交、推送并向 orchestrator DONE handoff。

## Promotion Candidates

None.
