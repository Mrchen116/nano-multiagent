# feat-634 Code Review

> 最新结论：Round 3 targeted closure（`50a56c8ccea9`）通过，findings=[]；历史 P2 与产品状态/大字问题均已闭合。各轮原始结论保留为来源。

## Round 1

- reviewer: independent static reviewer; 未参与实现；同时承担 change-verifier，未承担产品体验验收。
- review_mode: full
- executed_base: `18e1af8b1`
- validated_at: `bbc03566a30e9b269857d7369738a231d01e783a`
- scope: `18e1af8b1..bbc03566a` 全部 38 个文件；开始时 HEAD 与 validated_at 一致且 working tree clean。固定快照的产品代码与 `5206db08c` 同树。
- verdict: **request changes — 1 CONFIRMED P2**。

## Findings

```json
[
  {
    "file": "src/IM/ios/NanoIM/Features/Chat/ChatStore.swift",
    "line": 438,
    "summary": "[P2] 确认旧发送时，应独立移除已经发出的附件",
    "failure_scenario": "用户发送带附件的文字，回包丢失或延迟后在 composer 输入新正文，再收到原次发送的成功确认（包括重启后的查询/显式重试）。此时 drafts[id] != attempt.draft.content，436 行条件跳过 438–439 行的附件移除；pending 被清空，而原附件仍留在 attachments[id]。下一次发送新正文会再次携带原附件。修改前 sentIDs 清理独立于正文相等检查。SendRecoveryTests.testNewSessionAndStoreReadFrozenMentionAndAttachmentsBeforeExplicitRetry 已执行附件恢复 + 新正文 + 确认的前提，但只断言新正文保留，没有断言附件移除，因而漏掉此回归。将 sentIDs/removeAll 移到正文条件之外，继续按附件 id 仅移除原次已发送附件；在该现有测试断言已发送附件从 composer 消失且下一次发送没有它。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

直接证据：`ChatStore.swift:435–440` 无 await，成功确认后必定先清 pending，再按正文相等同时控制正文和附件清理；普通发送 `:299` 读取同一 attachments 集合。基线 diff 证明旧版只对清正文做条件判断，附件始终按 sentIDs 清理。上述失败是可达的真实发送恢复路径，无需网络/权限的额外假设。

## Coverage and evidence

- 对齐原生入口 `ConversationView → ChatMessageView → InteractiveCardView/InteractiveRuntime → ChatStore → ChatAPI → Session`；正文、附件和专用审批入口保留。
- 核对 nano-1 全部 83 个注册组件的 SwiftUI switch/父组件数据消费，原生字段/表格/图表/列表/折行/展开/sheet。源码有呈现映射不等于逐组件 GUI 验收；视觉与触摸可达性由独立产品 reviewer 判断。
- 核对随包 JSCore bridge 的公开 lang-core API、反应绑定、Set/Reset/ToAssistant/Mutation 顺序与查询白名单；未将 Agent source eval 成 JavaScript。凭据、网络、磁盘均留在原生宿主；无 DSH private import/第二执行循环。
- 579KB 生成资源按生成脚本、精确依赖版本、许可证、`--check` 与真实资源执行核验，未逐字符审计压缩第三方代码。
- 独立执行 `pnpm check:ios-runtime` 通过；独立执行 `pnpm exec vitest run src/IM/ios/Runtime/interactive-runtime.test.ts`，6/6 通过（01:22:37）。这些测试执行真正随包资源，包含反应式计算、重置、Slider 数组、Form/验证、Set 后快照、隐藏按钮后完成动作、Query 与 Mutation。
- 复用主任务 iOS 测试：`/tmp/nano-feat634-ios-test.log`，43 XCTest + 17 Swift Testing，零失败；xcresult 见 M1 progress。未重复启动 Xcode 或 Simulator。该轮之后有版本/图片/辅助名称变化，最终集成构建仍由主任务闭环。
- 复用 `/tmp/nano-feat634-recovery-evidence.json`：真实服务保存后回包丢失 → 进程终止 → 改名 → 重启 → GET 404 → 原 key/bytes 重试，两次 POST、一条中心消息。它不覆盖上述“旧附件随新正文重发”的缺陷。
- 全量根测试现有证据为 535/537，两个未改动 DSH 测试超时，串行复核由主任务推进；未记全绿。Release/IPA、最终独立验收和合入后手机安装不在静态审查证据内。

审查已覆盖派发范围并收口；不追加假想边界或与本 diff 无关的问题。修复上述问题后按实际 patch 独立复核即可。

## Round 2 — Targeted Closure

- review_mode: closure；scope: `bbc03566a..35a9c0588` 三文件修复，仅核历史 finding 与产品 minor 状态修复，不扩大 full。
- finding_origin_head: `bbc03566a30e9b269857d7369738a231d01e783a`
- executed_base: `18e1af8b1`；validated_at: `35a9c0588dfb3bd9f6c34e678c2d2cfd3396889c`（已独立确认 HEAD）。
- verdict: **PASS — no surviving findings**。

```json
[]
```

### Focus disposition

| Focus | Disposition | Direct evidence |
|---|---|---|
| Round 1 P2：新正文导致已发送附件残留 | closed | `ChatStore.swift:438–439` 已独立于正文相等条件按原 attempt 的附件 id 移除；当前新正文不变，新附件 id 不在 sentIDs，因而保留。 |
| 独立产品 R1 minor：同一卡片未知请求与旧成功提示并存 | closed at implementation seam | `InteractiveCardView.swift:19` 只有 submitted 且 !hasPending 才显示成功提示；pending 期间仍可见原有核对入口。未混淆“服务已保存”和“当前原生已确认”。真实原生画面闭合由产品 reviewer 更新 acceptance。 |

回归保护沿用 `SendRecoveryTests.testNewSessionAndStoreReadFrozenMentionAndAttachmentsBeforeExplicitRetry`：恢复旧附件、改提及/新正文，再加入新附件，确认后断言仅新附件保留，且原次重试 bytes/key 完全相同。该断言保护稳定 composer 待发状态，不窥探私有实现。

已读取 `/tmp/nano-feat634-send-attachment-red.log`：原实现上新增断言明确红测，实际附件 `[kept,new]`，期望 `[new]`；`/tmp/nano-feat634-send-attachment-green.log` 修复后 27/27 XCTest 通过。该 SwiftPM seam 复制真实产品源码和既有测试，验证发送/身份/恢复行为；不当作 iOS UI 测试。`/tmp/nano-feat634-fix-build.log` 显示 Simulator BUILD SUCCEEDED。本轮未启动 Xcode/Simulator，未改实现或测试。

最终 iOS 全套、Release archive/IPA 与产品 acceptance 在主任务推进，当前不将它们写成已完成。该进行中交付边界不影响本次两个指定实现问题已闭合的静态结论。

## Round 3 — Final Layout Closure and W3 Evidence

- review_mode: closure；本轮唯一新产品diff为 `35a9c0588..50a56c8ccea9c004da71a971a8536f47147d2240` 的 `InteractiveNodeView.swift:29` 一行；不重开 full。
- executed_base / effective_base: `18e1af8b1`（caller已fetch、main无新增）；validated_at: `50a56c8ccea9c004da71a971a8536f47147d2240`；已独立确认HEAD。
- verdict: **PASS — 0 surviving findings**。

```json
[]
```

`.fixedSize(horizontal: false, vertical: true)`仅使交互 TextContent/MarkDownRenderer 在既有可用宽度下取得完整内容高度，不改字段、状态、请求或权限。reviewer已实际查看 `/tmp/nano634-390-largefont-truncation.png`、`/tmp/nano634-r3-largefont-full.png`、`/tmp/nano634-r3-default.png`：30分钟结果由省略变为完整两行；默认字号完整一行，原按钮与内容关系保持。独立产品`acceptance.md` Round3记录同390×844/accessibility-medium实际选择/重置操作并判pass，未决blocking/major/minor为0。产品R2 major **closed**；历史附件P2与pending提示minor的Round2闭合结论保留。

### Final delivery evidence

- `/tmp/nano-feat634-final-ios-test.log` / xcresult `Test-NanoIM-2026.10.22_01-57-51-+0800.xcresult`：`35a9c0588` 43 XCTest +17 Swift Testing零失败，包含新增附件断言与最终资源。`50a56c8ccea9`只有上述正文布局一行，行为证据继续适用；新Simulator build（`/tmp/nano-feat634-text-wrap-build.log`）、Release archive（`/tmp/nano-feat634-final-release-archive.log`）与原生GUI补验通过，未声称在50a重跑全套。
- 直接读取最终IPA并核对manifest：`/Users/czj/.codex/artifacts/feat-634-ios/NanoIM-0.2.0-634-50a56c8cc-unsigned.ipa`；SHA256 `7f49eaf23008b540e4e263fc18becadbb55811536bbf82458b1b1d93d4ff4103`，与manifest一致。IPA内Info.plist为bundle`win.nanoim.ios`、0.2.0(634)、source`50a56c8ccea9`，包含InteractiveRuntime.js；archive日志确认arm64。未签名AltStore输入，尚未安装手机。
- 本地其他检查与边界见M1 progress：build/typecheck/docs/runtime、Python62、ruff通过；Web全量947/949且两个未改文件单独65/65通过；DSH正式90秒测试仍有超时，临时诊断上限下161秒完成，不修改正式timeout、不把原命令写为全绿。远端新head CI待PR创建后执行。

W3本地构建/归档、来源、独立静态与产品门禁证据已闭环，可以提交PR；远端CI与合入后手机安装保留各自后续门禁，不声明已经完成。未改源码、测试、配置或设计；报告由caller提交。
