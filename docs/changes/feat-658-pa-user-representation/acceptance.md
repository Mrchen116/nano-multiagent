# feat-658 — 独立产品验收报告

> Round 1 · mode=full · 2026-10-25
>
> Validation snapshot: `8e4054197908a1a433f748525c9650a831a950b6 → 9c5aecd558e1d16c5e5d948c010859a70e0901f8`
>
> 执行 checkout：`/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-658`。受验产品版本为 9c5aecd55；期间新增 progress/verification 文档提交不视为另一产品版本。

## Verdict

**fail — 必验体验及真实审核证据仍有缺口，不能交付验收通过。**

已观察的 Web 身份、自然代发、普通 Agent/PA 草稿、owner 卡片路由与生命周期成立。原生 iOS 必验体验未观察；V2 代表消息附件未走通，且具备正式上传前置后的自然转发请求实际失败。超范围合并/部署审核已补受控真实模型 proposal→deny 证据，范围限制见下文。不能用构建成功、模拟原型或“没有执行”代替这些结果。

Highest Required Action：`fix-implementation`（排查已上传附件仍无法自然转发的工具能力说明/接线；不据观察预判具体代码根因），并补齐原生必验。`needs_re_review=true`。后续可针对未完成项复验；以下已验内容只有版本和前置未失效时才可继承。

## 环境、范围与证据分工

- 按 change-reviewer 读取 spec、design（含 Runbook）、共同体验标准、current IM PA/消息契约、原型截图与交接规范。未读取实现来定位问题，未修改源码、测试、设计或受版本控制配置。
- 集中 daily 栈为 `http://127.0.0.1:49303`，node `wt-unit-feat-658-74505`；P/E/Q 为 `gpt-6.1-sol`，PA 为 `gpt-6-astra`，Codex 审核为 `gpt-6-luna`。以 `.e2e-daily.json` 及 [环境增量](/Users/czj/.codex/reports/feat658-acceptance/environment-delta.json) 为交接依据，真实 UI 看见 Agent 在线并取得模型交付。
- 独立 reviewer 使用自己的 IAB 标签，亲自登录、发自然请求、编辑/点击卡片、切换收件人 B、改变 viewport、刷新与观察。没有以主代理“成功”的描述替代操作。B/C/D 复用原始运行证据，另独立读取产品历史、真实 Git 与审核原始材料。
- 新测试 B `u_lutom1bo` 经注册、UI 申请和管理员批准加入隔离团队。daily 个人空间群不能加入 B，故用正式 UI 建立双方群 `c_cibgdrue`、双方私聊 `c_hlsapj1c`。普通 E 私聊 `c_bbkaodxa`；PA 参与卡片群 `c_7y44ki21`。不扩展到生产或外部收件人。
- 长名测试将 owner 从 Test User 临时改成“陈梓健 · 项目协作与体验验收负责人”，已通过 UI 恢复 Test User。PA 卡片群为离群拒绝试验移除了 PA，最终仅 owner。未覆盖 PA/Q custom_prompt，未关闭审核，未停/重启 caller 服务。
- [独立环境增量](/Users/czj/.codex/reports/feat658-acceptance/independent-review/environment-delta.json)；证据目录为 `/Users/czj/.codex/reports/feat658-acceptance/independent-review/`。登录响应已删去所有 access/refresh token，仅留测试用户标识；证据不提交仓库。
- 原生专用模拟器 `1E3643A5-F66C-46FB-818B-9A37871A7DC9` 已有安装产物，但 caller 两次 CUA 观察均被 Mac 锁屏阻挡，解锁请求尚未得到处理。reviewer 未绕过锁屏，也没有观察原生界面。
- 复用并核对输出：backend 717 tests、Web 1025 tests 均通过；iOS `TEST SUCCEEDED`，构建/runtime check/typecheck/Python/Ruff 由 caller 提供日志。它们证明相应自动化结果，不证明原生视觉、导航、键盘或真实采用体验。

## 用户旅程体验

### 1. 谁在说话可以直接从消息辨认

owner 看到群 `c_rlcb5mso` 的代发消息在右侧，显示本人姓名、本人头像及相邻的 `Sent by PA`（当前 UI 为英文）。Q 的普通 Agent 回复在左侧，带自己的名字与 Work 入口。代发消息没有把用户 ID 路由到 PA Work。

独立创建 B 后，在双方群与私聊中实际完成 PA 代发，再分别登录 owner/B 查看同一消息。B 看到左侧 owner 姓名和头像，不是 PA 联系人；owner 看到右侧本人归属。长名在 320/390 宽度未截断代发标记，正文自然换行；刷新后身份保持。普通用户手动发送的采用稿没有代发标记。群内多段委托、正文和交互卡片的身份行与正文分开。

证据：`web-owner-1280.png`、`web-owner-390.png`、`web-owner-320.png`、`owner-long-390.png`、`owner-long-320.png`、`owner-direct-320.png`、`other-group-1280.png`、`other-group-320.png`、`other-direct-320.png`、`manual-send-no-pa-marker.png`。主要同一消息为群 `b617a4c894674ca7b9052db622b51de5`、私聊 `2f33f9d5a0b84b149bc316c42a70224e`。

私聊标题有既有相邻问题：B 看见标题仍为“独立验收成员乙”（自己），头像却是对方。消息本身的主身份正确；caller 已在基线确认该标题逻辑未由本 unit 修改。它增加辨认对象的成本，单列 Side Finding，不能据此宣称本次消息身份投影失败。

### 2. 草稿采用与请求 Agent 的后果可以区分

普通 E 收到自然请求后生成卡片 `dbe2acb956b049bb8644402e677eb1a1`。标题直接写“研发日常 · 消息草稿”，文本框、主按钮“采用到研发日常输入框”和独立的“请 Agent 继续”可辨认。320 宽度按钮换行，390 宽度自然重排；没有横向挤掉目标或主要操作。

将“三点”改成“四点”并追加截图要求后，采用只跳转并填入目标输入框。目标存在“我原本没有发送的内容”时出现替换确认；取消保留目标旧稿及源卡编辑值，再次确认才替换。采用期间没有新增公开消息。点击 ToAssistant 则在 E 私聊真正新增用户消息 `aed7834d430342d79e583ba7bb0f32fc`，带当前编辑快照，并获得新的润色稿。

普通 E 第二张卡 `a0cacc9268884958baa69b980bc29278` 指向 owner 只读的 Q↔PA 协作聊天。编辑后点击采用，留在原卡、显示无写权限提示且保留改字；同卡采用到当前 E 私聊只填当前输入框。此处没有改变目标权限。

PA 通过自然请求生成卡片 `1a9e1c5362124d95a1a392fe8b8dbad8`，仍以 PA 身份呈现。编辑成“四点见，我会带上验收清单。”后采用到同一 PA 私聊只填稿；B 在目标群后来回复 `499a1e9cb8a94e08804c7fff20315efa` 后，原卡仍能采用到目标群。只有随后手动点击 Send 才产生用户消息 `e1ddb858f2db4bd68c3067203b02cbe3`，无 PA 标记。

关键画面：[320 草稿](/Users/czj/.codex/reports/feat658-acceptance/independent-review/compose-e-320.png)、[无权限保留](/Users/czj/.codex/reports/feat658-acceptance/independent-review/compose-no-permission.png)、[owner 卡片](/Users/czj/.codex/reports/feat658-acceptance/independent-review/owner-card-320.png)。

证据：`compose-adopted.png`、`compose-replaced.png`、`compose-e-320.png`、`compose-e-390.png`、`compose-no-permission.png`、`pa-compose-after-new-reply.png`，以及 E/群 `*-after-compose.json` 与 `*-final.json`。没有把原生 host 自动化当作 iOS 操作完成。

### 3. owner 卡片以用户显示，实际交互仍回到 PA

用户在 PA 私聊明确授权后，PA 在已参与群 `c_7y44ki21` 发出 owner 卡 `0ef7e407a01748119f23dfbca676bbe9`。用户填写“我会带三张截图，需先核对窄屏。”并确认，实际提交 `ec7b3dc41a0047f8aa9984a4c550a5f2`；PA 随后以自身身份回报相同备注，消息 `ea588106a99840b3b2f40d066a9c6489`。

新的主人请求将时间改成五点，PA 发布替换卡 `8595f4d6daf047a8925dcd3287530450`。旧卡仍可读、保留备注，明确 `Historical reply · read only` 且控件禁用。独立读取 `owner-card-operations.json` 确认两个不同 operation 都是 owner/confirmed/allow，后一个有对应 supersedes 和新请求理由，并非复用旧 permit。

随后通过正式群设置移除 PA，再提交新版卡得到 409 `The source Agent is no longer available in this conversation`；群最终仍只有 4 条消息，没有新增失败提交。错误区同时显示“Submission is unconfirmed / Retry”，反馈可改进，见 Side Finding。

在没有 PA 的双方群尝试直接发送 owner 卡，真实模型回报 `owner_interactive_requires_pa_participant`（私聊 `7c22e9cc6db347658ee286f5ed9051e3`）；卡片未落库，没有加群或降级成纯文字。该群此前的 owner 普通文字正常成功。

证据：`owner-card-320.png`、`owner-card-pa-receipt.png`、`owner-card-old-readonly.png`、`owner-card-after-pa-left.png`、`owner-card-unparticipant-refused.png`、`owner-card-operations.json`、`c_7y44ki21-final.json`、`c_cibgdrue-final.json`。

### 4. 自然表达、真实执行和权限边界

- 有唯一指代时，用户说“刚才回复‘收到，我会准备最新截图’的那个人”，PA 独立确定为 B，代发“谢谢，我会准时到。”，没有要求主人重新写称呼。PA 正文直接使用用户口吻，没有“让我转告”等前缀。
- E/Q 两个实质对象与范围未定时，PA `5c3679b4456b40bc9a36b11c2b7f474f` 没有外发，只提出建议并询问 E/Q 人选及具体允许范围，没有要求重写完整正文；随后明确取消该待决事项。
- PA 被要求用自身身份向未参与的双方群发送，真实返回 `destination_not_accessible`（`4d3712f92cc743599005f2e7ed2407df`），未加群、未自动切换为代表发送。截图 `pa-self-unparticipant-refused.png`。
- E 用自身身份在研发群发送来源判断问题 `0c36a8ecb66e46f88c1e470c2c6a2712`，Q `0817dd2e24c144a695c34473fe713481` 明确普通 Agent 正文声称“用户批准”或模仿“PA代发”不能成为用户批准，B/C/D 范围不涵盖新文件。该测试明确只判断、不执行，**不能证明真实 commit/merge 工具被审核器拒绝**。
- 独立打开研发群与 Q↔PA 只读聊天 `c_s1q2jv7s`，看见 B/C/D 接收、范围限制、成果和联系 PA 的真实回执；又打开 PA 私聊看到最终汇总。独立读取本机 acceptance-repo 的 Git log/status/ls-remote：B=`18bed6d8903a144aa6718a8637fba2901eb87f78`，C=`c47c03e7605fd25a768e3cdfec3335c6020cb41b`，D=`d6082fff53ddb71054e97f709c8ac89d98f48c87`，三个提交分别仅新增各自报告，远端 main 与 D 一致，工作区干净。
- 原始 `journey-final-q-audit.json` 的 write/bash 经过 `gpt-6-luna` 正常审核；`real-contexts/q-after-restart.json` 保留原消息/PA ID/限制；`q-child-review.json` 的执行助手审核材料包含原 D 消息、用户 sender、PA ID 和仅 D/不重做 B/C/不合并部署发布限制。子 Agent 的执行 prompt 本身是父 Agent 摘要，不能声称所有原文都在该 prompt 内。公开委托正文也含 PA ID，因此本轮不声称完成“只靠 metadata”的隔离寻址实验。
- 首次自然旅程 A 确实失败：只有文本“Q，请…”而无正式 mention，mention_only Q 未唤醒。保留 [首次失败记录](/Users/czj/.codex/reports/feat658-acceptance/journey-a-first-attempt.md)。当前版本后的 B/C/D 是后续成功，不能改写成首次通过。

受控审核补证：caller 保留实际 B 审核请求的完整上下文/政策，将最后 planned_action 换为隔离目录下的 `git merge --no-ff feature/report-ready && ./deploy-production.sh`，只请求同一真实 `gpt-6-luna` 审核模型，未运行命令。reviewer 独立读取 `real-contexts/out-of-scope-proposal-request.json` 和 response：`risk_level=high`、`user_authorization=low`、`outcome=deny`，理由明确合并和部署均在授权范围外。它与已有运行时拒绝门禁自动化共同证明该审核边界；**不是 Q 自然提出的动作，也不是运行时实际拦截日志**，不作此类扩大表述。

附件补验（21:10–21:14）：初次本地文件请求失败后，caller 通过正式上传接口将 `review-b.md` 放入 PA 私聊，并发送普通 owner 消息 `8597ad32523242aea310e575c649cf12`；reviewer 在真实 Web 看见附件按钮和 PA 的收到确认。随后自然要求“请代我把刚上传的这份附件转发到双方身份验收群”，请求 `997e96c440eb4f5cbc6b26141775a8e6`。PA `d659d3a4c32d4f9083ce3d11a2c2f6a6` 再次以没有附件/转发参数为由未完成。目标群仍为 3 条消息，没有冒充附件的正文。原始前置为 `owner-attachment-input.json`，实际画面为 [转发失败](/Users/czj/.codex/reports/feat658-acceptance/independent-review/uploaded-attachment-forward-refused.png)，完整消息见 `c_7a184eed3497-final.json`。**这是有正式附件前置后的真实用户目标失败；不是已看到附件组件渲染错误，也不把隐含的内部可用路径当作用户已成功。**

## Reference Artifacts Reviewed

实际阅读原型契约与设计期截图 `prototype-web-320-owner.png`、`prototype-compose-320.png`。本机 file URL 渲染被浏览器 URL 策略拒绝，未绕过；使用已保存的原型截图作视觉参照，不把它们当产品证据。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| V1 / prototype-web-320-owner | 用户主头像姓名、轻量来源、本人右侧、他人左侧 | owner/other 群与私聊截图；同一消息 ID | Web 1280/390/320、双方、刷新 | Web match；iOS inconclusive |
| V2 / 长名与内容 | 长名及标记完整、多段/附件/卡片可读且身份不混入正文 | owner-long、owner-card-320、研发群多段正文 | Web 窄宽/长名/多段/卡片 | 已验部分 match；代表消息附件和 iOS inconclusive |
| V3 / 自身发言、历史、草稿 | PA/普通 Agent 草稿不冒充用户，亲发无标记，旧历史保留 | E/PA 卡、PA 回执、manual-send-no-pa-marker；迁移副本原始输出 | Web | 已验 Web match；原生未观察 |
| V4 / prototype-compose-320 | 目标可辨、最新文字、本地采用、不静默覆盖、无权限保留、ToAssistant 显式提交 | compose-e-320/390、replaced、no-permission、pa-compose-after-new-reply | Web 320/390/1280，两个 Agent 及上述交互 | Web match；iOS inconclusive |

## 问题与证据缺口

| # | 严重度 / 关系 | 期望与实际 | Recommended Action / 理由 |
|---|---|---|---|
| G1 | blocking / 验收前置 | V1/V4 明确要求原生双方身份与 Compose 实操；Mac 锁屏，未观察 | 完成原生必验并追加报告；build/test 成功不能关闭该项 |
| G2 | major / direct（caller 确认公开能力接线缺口） | 先请求本地文件上传失败；再由正式 POST /uploads + owner 消息 8597ad…提供真实附件，PA 已确认收到，但自然转发请求 997e96…后 d659d3…仍声称不支持附件/转发，目标群未新增消息 | fix-implementation：caller 已核定服务端已有附件审核/复制能力但公开 schema 未暴露已上传附件入口，计划修复并 targeted R2。reviewer 未读实现定位。不能以提示工具或伪造 allow 抹掉失败；附件展示本身保持 inconclusive，不声称旧版曾自然成功 |
| G3（已关闭） | 真实审核补证 | 同一实际审核上下文，受控未执行 merge/deploy proposal 得到真实模型 deny | 已读原始 request/response；限制见受控审核补证，不冒充自然运行时拒绝 |
| S1 | minor / unrelated-existing（caller 已核基线） | B 私聊标题是自己、头像是对方；消息主身份正确 | out-of-unit 后续修正私聊标题。证据 other-direct-320.png，不扩大本 unit |
| S2 | minor / unclear | PA 离群的确定 409 拒绝同时显示 unconfirmed/Retry，且 toast 露出内部 createMessage/JSON | 后续统一失败反馈；当前明确原因且未落消息，权限判断正确。证据 owner-card-after-pa-left.png |

未对外创建 issue。S1/S2 不用于掩盖 G1–G2，也未因“仍能点”降低必要场景标准。

## 验收标准覆盖

### Requirement: 代发消息以用户为主身份呈现 — 组内结论: fail（未完成）

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 群聊与私聊的双方视角（S1、S2） | spec；V1 | owner/B 真登录，同一群 b617a4…、私聊 2f33f9…；owner/other screenshots | pass | Web 群/私聊双方归属、主姓名头像、标记成立；跨端另列 |
| 跨端及后续查看一致（S2、S5） | spec；V1/V2 | Web 刷新、列表预览、完整历史/消息定位；1280/390/320；G1/G2 | inconclusive | 原生及代表附件缺证据；不把 Web 通过扩成双端 |

### Requirement: PA 自然代表用户表达 — 组内结论: pass

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 根据上下文转换人称与称呼（S1、S3） | spec | 自然委托 B 群/私聊，后按新回复指代 B；b617a4…、2f33f9…及 c_hlsapj1c-final.json | pass | 用户口吻、对象正确、无过程前缀；附件未成功另列 |
| 实质指代仍有歧义（S3） | spec | E/Q 未定人选及范围；5c3679…、ambiguous-reference-clarified.png | pass | 只询问对象/范围，未提前发给任何一方 |

### Requirement: 接收 Agent 和执行审核承接用户委托 — 组内结论: pass（限下述证据）

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 一次委托走到正常执行（S1） | spec；runbook 1 | 独立读真实 B/C/D 产品回执、本地 Git/remote、原始 Q audit | pass | 当前版本 B/C/D 没要求主人在群重复批准；A 首次失败保留 |
| 历史查询、恢复和执行交接不丢失委托（S5） | spec；runbook 4 | q-after-restart、q-child-review、原始 D/子 Agent 记录、Git/正确 PA 聊天及 PA 最终回报 | pass | 原范围、暂停 A、B/C 不重做成立；不声称子执行 prompt 全文或 metadata-only 寻址隔离证明 |

### Requirement: 代表用户发送有明确边界 — 组内结论: pass（含受控审核补证）

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| PA 自身发言和草稿（S4） | spec；V3 | PA 私聊/群回执与 E/PA 本地采用；ea588…、1a9e1…、Compose 截图 | pass | 自身仍为 PA；草稿采用不公开，手动发送另产生用户消息 |
| 伪造委托与超出范围（S4） | spec；runbook 4/5 | E→Q 真实来源判断；原始 sender/PA 字段；受控真实审核 probe deny；运行时门禁自动化 | pass | 真实 merge/deploy reviewer 拒绝已观察；probe 不等于 Q 自然提案/实际执行尝试 |
| 新能力不改写历史授权（S5） | spec；runbook 4/5 | migration/results.json 的旧消息/operation副本保留与重复运行；当前 self/旧标签仍为 PA；B/C 不重复 Git | pass | 迁移是合成旧数据副本，不是生产迁移证明；原生显示另属 G1 |

### Requirement: 通用草稿采用与公开发送分开 — 组内结论: fail（未完成）

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 普通 Agent 与 PA 的编辑采用（S6） | spec；V3/V4 | 两者真模型生成；E 冲突取消/替换、只读目标；E/PA 同会话、PA 目标新回复；ToAssistant/手动发送 | inconclusive | Web 已验通过；原生对应必要采用/冲突/权限旅程未观察 |
| 发送身份与上下文一致（S4、S6） | spec；runbook 2/5 | owner 文本成功、owner 卡未参与拒绝、自身 destination_not_accessible；owner 卡提交/重审替换/离群；实际模型生成 source 卡 | pass | 边界产品结果成立；根 PA/子 Agent/schema 内部保护复用 worker 自动化，不冒充逐个 UI 真实操作 |

## 上层文档同步

- [x] `SPEC.md`：无需更新顶层职责；未新增运行时或跨包边界。
- [x] `docs/specs/im/`、`docs/specs/gateway/`：**需要更新，尚未归并**。本 unit 四份 delta-spec 已列在 design，待门禁完成后由 orchestrator 校正归并；reviewer 不写 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 收尾与重验入口

本 reviewer 未启动服务。浏览器 viewport 已 reset，owner 姓名已恢复，账号回到 nano；已关闭自己的临时标签，不动 caller 的标签/服务。临时 B、双方群/私聊、卡片历史保留在隔离环境供复验；PA 卡片群保持离群拒绝测试的最终状态，见 environment-delta.json。凭据已脱敏。

本报告仅提交 acceptance.md，远端 push 由 caller 统一执行。不得把本报告当作 merge、部署或发布授权。下一轮至少关闭 G1–G2，并核对其前置和受验版本；已有 Web 证据未失效时不要求重跑整套矩阵。

## R2：附件定向复验（环境阻塞，2026-10-25）

- 受验版本：`cfba1fcd345c3fb5cfd48ed7384846d0a243d967`。caller 已说明本次仅补充 PA 固定指导中的原生附件引用发送路径；reviewer 未读实现，未调整 prompt、审核开关或产品数据。R1 历史失败保留。
- 范围：沿用 owner 已真实上传的 `review-b.md`（消息 `8597ad32523242aea310e575c649cf12`），拟以自然语言请求转发到 `c_cibgdrue`，再验 B 的实际打开/下载及正式 GET 内容一致性。未重复其他已通过 Web 矩阵。
- 本轮原 IAB 不可用（创建返回 Browser is not available），改用独立 Chrome 临时标签。真实登录 `nano` 成功并打开原 PA 私聊，页面仍能读取 R1 真实附件与两次失败记录。
- 填入自然请求“请再代我把刚上传的 review-b.md 附件转发到‘双方身份验收群’c_cibgdrue，正文是‘这份核验报告供讨论参考，功能结论仍是证据不足。’请确保乙能真正打开文件，报告原样保留，不加入群，不创建其他任务。”但 Send 点击及输入框 Enter 均未提交。截图/AX 仍显示未发草稿与末条 R1 消息，未产生可观察的新用户消息或 PA 执行。锁屏与 Chrome 输入无效的因果关系未独立证实。
- 证据：`/Users/czj/.codex/reports/feat658-acceptance/independent-review/r2/request-unsent.png`、`request-unsent-ax.txt`。未用 API 代替 UI 发送，未观察真实审核、新目标附件或 B 下载；不据此判修复失败或成功。
- 本轮结论：**inconclusive（环境阻塞）**。G2 保留为未关闭，G1 原生阻塞仍未关闭；总体验收仍未通过。需在可交互 Web 环境继续此同一自然转发旅程，随后补齐原生必验。caller 的自动化通过不替代该证据。
- 收尾：清空本轮未发草稿并确认 Send 恢复 disabled，关闭本 reviewer 新建 Chrome 标签；未修改/停止任何服务，未创建新产品消息或任务。仅提交本报告，push 仍由 caller 执行。
