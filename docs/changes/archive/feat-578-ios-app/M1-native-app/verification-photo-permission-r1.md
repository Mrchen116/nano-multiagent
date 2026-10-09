# Verification Report: Photo permission delta R1

> Validation snapshot: `5a46968a05d2d78da4c3ac819886397bcfe0e301 → d17e70c4f1b9ca87dddea963711bb6648011ee79`

2026-10-08。独立使用 `change-verifier`，已读模板、handoff及 Codex 适配。`verification_mode: delta`；`branch: codex/feat-578-ios-app`；`executed_base/pre_fix_head: 5a46968a05d2d78da4c3ac819886397bcfe0e301`；`validated_at: d17e70c4f1b9ca87dddea963711bb6648011ee79`。仅两份 Config plist 权限修正和必要媒体调用方。`requires_full_verification: false`。

## Summary

| Dimension | Result |
|---|---|
| Completeness | 两配置均只声明用户主动保存图片的 Add 权限用途；新包真机安装及保存闭环仍由独立产品 reviewer 完成 |
| Correctness | 0 CRITICAL / 0 WARNING / 0 SUGGESTION；限定静态 delta PASS |
| Coherence | 系统选择、预览与分享技术路线保留；IM 授权及上传/缓存生命周期未改 |
| Delta validity | 既有 5 Requirements 没有增删；媒体 Requirement 受影响边界 aligned，其余有效范围 retained |

## Completeness and correctness

| Contract | Implementation and evidence | Outcome |
|---|---|---|
| `spec.md` R4/S10、`specs/im/ios-client.md` 媒体选择与分享：选择/取消、用户主动保存/分享 | `ConversationView.swift:108,163,248-255` 系统 PhotosPicker 和 selected item data，nil 不发送；`MediaViews.swift:47-52` 用户主动 Quick Look / ShareLink。两个 plist 的 Add key 和保存用途已解析，read/write key 均不在源码/Release 包 | aligned（静态）；新包系统授权弹窗与实际保存未产品接受 |
| 媒体撤权与账号隔离：受保护缓存不继续分享，已主动另存不误删 | `MediaViews.swift:53,55-67` 既有同源授权读取、scope 临时文件及清理未改；本 delta 不触会话撤权/账号生命周期 | retained；不把照片库 Add 权限当 IM 聊天权限 |
| 免费个人安装维护 | 新签名包 receipt 固定 source head；独立核 executable hash 和两媒体 source hashes匹配、实际严格 codesign exit 0；包最低 iOS 26.0 | retained validity；构建/签名检查不证明安装、续期或自然到期恢复 |

当前 IM `docs/specs/im/spec.md`、`web-chat-ux.md` 与 `SPEC.md` 不要求原生客户端拥有全照片库权限。active delta 承诺系统媒体操作和既有业务权限；该修正不会新增 IM→agent 依赖，也不改 HTTP/API 或 Gateway 边界。`M1-native-app/tasks.md` 明确 iOS 26+ 和实际 native UI 不能由 mock/static 替代，本报告遵守该限制。

## Coherence

`design.md:54,92` 的 PhotosPicker / Quick Look / Share 路线、受保护附件以及用户已主动另存文件的边界均保留。调用方没有需要直接读取照片库的 PHAsset/PhotoKit 授权流程。Apple 当前 [PhotosPicker 契约](https://developer.apple.com/documentation/swiftui/view/photospicker(ispresented:selection:matching:preferreditemencoding:photolibrary:)) 允许只访问选择条目而无需全库授权；[read/write key 契约](https://developer.apple.com/documentation/bundleresources/information-property-list/nsphotolibraryusagedescription) 与 [Add key 契约](https://developer.apple.com/documentation/bundleresources/information-property-list/nsphotolibraryaddusagedescription) 支持只添加的用途声明。2026-10-08 独立读取 Apple Markdown，API availability 覆盖 iOS 26，未见该版本要求恢复 read/write key 的依据。

Prototype/reference：本 delta 不改 UI 布局或导航，P1–P6 既有未失效视觉结论保留原范围；系统权限弹窗的实际内容仍需物理产品观察，本角色不做视觉评分。

## Existing delta validity and evidence limits

已读完整 iOS delta 的 5 Requirements。业务入口/辅助访问、会话恢复与隔离、前台提醒与后台限制的实现均不在本 patch；媒体导入/导出能力路径未删，安装维护说明未改。无需静默改 spec 或减少 S10，未发现真实新偏离，也没有共享边界影响需要重新全量验证。

复用 [Simulator R2 verification](verification-simulator-r2.md) 中原生命令、36 项（26 XCTest +10 Swift Testing）通过日志及其原 scope；[Simulator R5](acceptance-simulator-r5.md) / [R6](acceptance-simulator-r6.md) 只保留未失效模拟器旅程，旧代码测试不扩大为 Add key 或物理保存验收。本角色独立解析源码及实际签名包 plist、核 receipt 源码/可执行 hash、运行严格 codesign；构建成功来自 caller 交接，未重新构建、全测或写机械镜像测试。

本轮独立物理 R2 正式报告尚未完成。caller 提供的旧包 ShareLink → Save Image full-access 弹窗与拒绝事实不由本报告独立确认，保存结果仍未证。`d17e70c4` 新 Release 包尚未安装到手机；静态 aligned 不关闭旧现象，也不等于 S10 真机通过。后续产品 reviewer 应记录安装包归属、PhotosPicker 选择/取消/发送、Save Image 实际请求级别、拒绝后可恢复行为及允许 add-only 后的真实保存结果；若系统仍要求更宽权限或发生实际失败，应按现场证据定向续查。

## Issues and handoff

CRITICAL: 0。WARNING: 0。SUGGESTION: 0。

Outcome: **aligned（限定静态 delta），产品物理闭环 pending**。本结论不代表 Full accepted、Ready PR、canonical 归并、archive、merge 或部署。没有 GUI、源码、环境或产品配置修改；仅提交本报告和 [patch review](code-review-photo-permission-r1.md)，保留 root progress/Air dirty及 unrelated `output/`，不 push。
