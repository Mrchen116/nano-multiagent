---
name: nano-ios-install
description: 构建 Nano IM 的 iPhone IPA、经 Mac mini 放到 iCloud Drive、用 AltStore 无线安装或更新，以及排查 AltServer 1200。仅在用户要交付或安装 Nano IM 真机包时使用。
---

# Nano IM iOS 交付与无线安装

## 准备 IPA

1. 核实用户指定的 ref。用户说“最新”且未指定发布分支时，核对仓库当前开发基线的远端分支 HEAD，记录实际构建 commit。若已有该 commit 的可用 IPA，直接复用。
2. 按 [iOS 构建说明](../../../src/IM/ios/README.md#设备产物) 在有完整 Xcode 和 iOS SDK 的 Mac 上隔离构建 Release 真机包。Mac mini 可以只负责交付和侧载，Xcode 不必装在 Mini 上。
3. 用 `unzip -tq` 检查 IPA，读 `Payload/NanoIM.app/Info.plist` 核对 `NanoIMBuildRevision`。用代码版本区分文件，例如 `NanoIM-0.2.0-8323e629cfbc.ipa`。iOS 版本号和 build number 可能相同。若包里有 `._*` 或 `__MACOSX`，用 `ditto --norsrc` 从同一 archive 重新打包。
4. 用户要从 Mini 放到 iCloud 时，确认目标主机和 iCloud Drive 路径。把文件放到 Mini 的 iCloud Drive，比较来源和目标 SHA-256，确认上传状态或在另一台设备读回同一文件。用户只要 IPA 时，到交付即结束。

## 无线安装或更新

- iPhone 已与 Mac 配对且能发现 AltServer 时，在 **AltStore Classic → My Apps → ＋** 选新版 IPA。**Refresh All** 续签现有包。升级用新版 IPA。
- iPhone 已出现 `AltStore.OperationError 1200`，且 Mini 的 AltServer 菜单仍能列出目标 iPhone 时，优先走 **Mini → iPhone**。在 Mini 菜单栏按住 **⌥ Option** 点 AltServer 图标，选 **Sideload .ipa… → 目标 iPhone**，打开已核对的 IPA。普通 **Install AltStore…** 会安装 AltStore 自身。远程工具若无法把 Option 传到 Mini，只请用户打开 **Sideload .ipa…** 文件选择器，然后接手。
- 文件选好后，AltServer 桌面流程会要求 Apple ID。请用户在该窗口用原 AltStore 的同一 Apple ID 输入密码，按需完成验证码。AltServer 不保存密码，每次重新发起桌面安装都可能再弹窗。新出现的设备信任由用户处理。若提示撤销证书，先确认影响再继续。
- Mini 菜单也找不到目标 iPhone 时，先核实两端网络、Finder 的 Wi-Fi 同步和配对状态。用户要求无线时，先查已有无线条件。进程在运行、同网段或另一台 Mac 能解析 Bonjour 广播，都只能证明各自的检查结果。

## 验收

等 AltServer 报告安装完成，重新打开 iPhone 上的 Nano IM，在 **我的 → 提醒与安装 → 代码版本** 核对目标 commit。区分已上传、已安装和已在真机核对版本。桌面直推成功后，手机端的无线发现和自动续签仍需各自验证。

遇到新错误，按实际阶段查详细报错再决定是否重试。比如桌面登录成功后报 `NSURLErrorDomain -1005`，先确认失败的下载 URL 和 Mini 当前能否完整下载，避免只让用户再次登录。

[AltServer 直接侧载](https://faq.altstore.io/release-notes/altserver#direct-ipa-sideloading) · [AltStore 故障排查](https://faq.altstore.io/altstore-classic/troubleshooting-guide)
