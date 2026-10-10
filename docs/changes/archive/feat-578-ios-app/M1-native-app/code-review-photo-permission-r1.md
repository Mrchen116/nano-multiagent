# feat-578 — Photo permission patch review R1

2026-10-08。独立使用 `change-code-review`，遵守 Codex 派发适配；`review_mode: patch`。仅审照片权限声明修正及必要调用方，不重新审整条 iOS 分支。

| Field | Frozen value |
|---|---|
| branch | `codex/feat-578-ios-app` |
| pre_fix_head / executed_base | `5a46968a05d2d78da4c3ac819886397bcfe0e301` |
| validated_at / native source head | `d17e70c4f1b9ca87dddea963711bb6648011ee79` |
| patch | `src/IM/ios/Config/Debug.plist:39-40`、`Release.plist:21-22`；只有 read/write purpose key 改为 add-only key，以及保存图片用途文案 |

## Verdict

**限定静态 patch PASS，0 存活 finding。** 实际调用方不需要直接读取照片库，删除 `NSPhotoLibraryUsageDescription` 符合当前实现。新声明 `NSPhotoLibraryAddUsageDescription` 与用户主动保存图片的用途相符；没有新增全库访问、自动保存或业务权限路径。

Review JSON:

```json
[]
```

## Evidence and reasoning

- 导入：`ConversationView.swift:108,163,248-255` 使用系统 PhotosPicker、读取所选 item 的 transferable data，再进入既有图片上传路径；取消的 nil guard 保留。对 `src/IM/ios` 检索 PhotoKit 授权、照片库读取和保存 API，未发现直接请求照片库 read/write 权限或枚举照片资产的调用。
- 导出：`UI/MediaViews.swift:47-52,55-67` 下载获授权附件到临时文件，经 Quick Look 和 `ShareLink(item: local)` 提供用户主动分享/保存；该 patch 不改变下载、分享入口或临时文件清理。
- Apple 当前 [PhotosPicker 文档](https://developer.apple.com/documentation/swiftui/view/photospicker(ispresented:selection:matching:preferreditemencoding:photolibrary:)) 说明用户只向 App 授予其选取条目的访问，因此无需照片库授权。[read/write purpose key 文档](https://developer.apple.com/documentation/bundleresources/information-property-list/nsphotolibraryusagedescription) 要求只添加、不读取资产的 App 使用 Add key；[Add key 文档](https://developer.apple.com/documentation/bundleresources/information-property-list/nsphotolibraryaddusagedescription) 描述 add-only 用途。2026-10-08 直接读取三份 Apple Markdown；PhotosPicker 可用于 iOS 16+、Add key 可用于 iOS 11+，均覆盖本项目 iOS 26 最低版本。没有看到 iOS 26 改为必须保留 read/write key 的条件。
- Xcode project `project.pbxproj:182-207` 为 App Debug/Release 指定相应 plist，未自动生成覆盖它。独立解析两份源码 plist及私人 Release 包 `signing-phone-r2/build/Build/Products/Release-iphoneos/NanoIM.app/Info.plist`，只含 Add key，值为 `Save images you choose to your photo library.`；包 `MinimumOSVersion=26.0`。
- 私人 `device-private/signed-package-receipt-r2.json` 记录 source head 为上述固定版本。独立核对 ConversationView/MediaViews source hashes和实际包 executable SHA-256均与 receipt 一致；实际 `codesign --verify --deep --strict` exit 0。私有 receipt、包、设备/签名信息不提交到仓库。构建成功沿用 caller 交接，本角色没有重新构建或全测。

## Product acceptance boundary

派发包提供的前置事实是：独立物理 R2 在旧包点击合成附件 ShareLink → Save Image 后出现 full-photo-access 系统弹窗，reviewer 拒绝，保存结果未证，正式 R2 报告仍未完成。本角色没有观察该 UI，也没有用 root 叙述替代 reviewer 报告。

配置与调用方审查只能证明这次收窄声明有依据，不能保证系统分享活动实际使用何种授权请求，或证明新包成功保存。新私人 Release 包尚未安装到手机。独立物理 reviewer 仍需在安装后的固定包上观察 Photos 选择/取消/发送，以及 ShareLink → Save Image 的真实权限请求和保存结果；不需要为此开放全库权限。若系统仍要求 read/write 或保存失败，应据实际现场追加核验，不能仅凭本静态 PASS 关闭旧现象。

36 项既有原生测试和 Simulator R5/R6 只保留未受影响的源码/模拟器范围，不提供此真机权限或保存闭环。没有 GUI、源码、服务或环境操作；保留 caller 的 progress/Air dirty及 unrelated `output/`。本角色仅提交本报告与同轮 verification，无 push。
