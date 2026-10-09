# feat-578 当前版本交付决定

2026-10-09，用户在已被告知中文 IME、VoiceOver 和免费续签仍有实证缺口后明确要求：

> 先提pr吧，我觉得差不多了，可以先合一个版本

据此接受当前版本作为本次交付，收尾既有 PR #324，归并客户端行为契约并归档整套 unit。此决定允许当前版本先合入，不把原 S1–S30 全部改成通过，也不补造 reviewer 的 Full accepted。原始需求、设计、独立验收和失败历史完整保留。

## 本版证据

- 原生 36 项测试、Simulator 与 arm64 Release archive，Python 4,120 / Web 808 的有效版本证据保留；此前公开 head `b6605d4dd82fe2431097b43189e413dd7e833331` 的五项 required CI 全部 SUCCESS，见 [run 37663638984](https://github.com/Mrchen116/nano-multiagent/actions/runs/37663638984)。本次最终发布 head 另等自己的 CI，不沿用旧 head 的绿灯冒充新结果。
- [Simulator R5](M1-native-app/acceptance-simulator-r5.md)/[R6](M1-native-app/acceptance-simulator-r6.md) 完成当前可达范围；[Device R2](M1-native-app/acceptance-device-r2.md)/[R3](M1-native-app/acceptance-device-r3.md) 记录真实账号/聊天/管理代表页及仅添加照片权限的媒体闭环。
- [Device R4](M1-native-app/acceptance-device-r4.md) 补齐代码/整消息/图片实际原生粘贴、英文软件键盘布局及大字号已测页面。没有新增消息，原四条 native full rows 保持；待发图片正常上传资源 13→15。临时字体/辅助开关、网络状态和快捷指令还原，隔离服务停止；原剪贴板未保存及 VoiceOver 通知拒绝的例外照实记录。
- 已有 [code review](M1-native-app/code-review-simulator-r4.md) 与 [delta validity](M1-native-app/verification-simulator-r4.md) 保留范围，以及 [照片权限 review](M1-native-app/code-review-photo-permission-r1.md)/[verification](M1-native-app/verification-photo-permission-r1.md) 的限定结论未失效。本轮仅文档归并/索引/归档，没有产品、API、测试、权限或签名修改，不机械触发全量重审。

## 剩余工作

[后续验收 #327](https://github.com/Mrchen116/nano-multiagent/issues/327) 保留手机中文组合/候选提交、持续 VoiceOver 操作、S29 完整范围及 S30 Mini 同网刷新/自然到期恢复。已观察子范围和未验证条件分开记录。开始后续修改时另按仓库 change 流程推进。

当前 Personal Team 安装保留，首次 AltStore mapping 不当作对原 Xcode App 的无损续签接管；不卸载、不清数据、不伪造过期。合入代码不等于生产部署，也不延长手机 profile 到期时间。

## 契约归并与归档依据

最终 delta 仍为五项 Requirements，与已有独立 validity 核对一致；将其归入 `docs/specs/im/ios-client.md`，同步 IM/全仓入口。canonical 描述当前客户端行为契约，不充当所有物理前置均已验过的证明；剩余验收由上方 issue 负责。

本 unit 按用户当前版本接受决定完整归档，原报告的 fail/inconclusive 不变。相对内部链接保持，外部入口更新到 archive；新提交不包含截图、runtime、凭据、数据库或构建产物。最终 PR 使用 exact head 的 CI 和 merge 检查，远端 main 已通过 HTTPS fetch 确认仍为 `d87ffa3d19160d45d309f281b0ace4ff92f55a38`，候选没有缺失 main commit。
