# Air 首次安装准备与异地拓扑修正

记录日期：2026-10-06（Asia/Shanghai）。用户补充：Mini 与 iPhone 不在同一城市，iPhone 与当前 Air 在一起，手机已有 Tailscale。用户授权本 chat 接管已连接的 iPhone Mirroring，希望整个流程尽量由 Agent 操作。

## 本次直接观察

- Air 原 `/Applications/AltServer.app` 不存在。复用此前从官方 CDN 下载并验证的 1.8 /build97：先再次验证签名和 Gatekeeper accepted /Notarized Developer ID，再复制到该精确新目标；安装后签名验证通过，实际进程来源为 `/Applications/AltServer.app/Contents/MacOS/AltServer`。未替换其他应用，未修改 Mini 的既有服务。
- 已通过 CUA 连接并查看当前 iPhone Mirroring 主屏幕，随后 Spotlight 搜索 `AltStore` 未找到该应用。镜像控制已获授权，但不能据此宣称具备侧载所需的设备配对。
- Finder 位置列表未显示 iPhone；Xcode 实际 Devices 页列表为空；指定 Xcode 的 `devicectl list devices` 返回 No devices found，同时报告 No provider was found，故该命令不能单独证明配对状态。另查 Air USB 设备树，只有主机控制器、无已接入 USB 设备。
- AltServer 为无普通窗口的菜单栏应用，启动提示关闭后 CUA 再次绑定发生 timeoutReached。没有据此判定 AltServer 不运行；真实进程已独立确认。

目前没有可用于签名安装的已发现手机。首次 USB 配对是当前需要的物理资源，镜像不能执行接线。未读取配对密钥、账号密码或其他 chat 的手机内容。

## 安装与续签边界

首次安装在手机旁的 Air 推进，沿[官方 macOS 安装流程](https://faq.altstore.io/altstore-classic/how-to-install-altstore-macos)完成配对、AltStore、同一 App identity 重签与启动。用户承担无法远程完成的物理操作；其余已授权 UI 操作由本 chat 尽量完成，遇到实际账号、系统授权或设备安全门槛再具体说明。

[普通 AltServer](https://faq.altstore.io/altstore-classic/altserver)要求 USB 或同一 Wi-Fi。手机 Tailscale 在线不证明能够发现异地 Mini 或通过它续签，现有 Mini 同网前提不符合实际拓扑；S30 继续未通过，不能改写成已完成。

本轮核实到 [AltStore Classic 2.3（2026-09-14）](https://faq.altstore.io/release-notes/altstore)新增 [Remote AltServers](https://faq.altstore.io/altstore-classic/remote-altservers)：另需电脑配对、LocalDevVPN 和 Wi-Fi。官方说明不构成此手机实测，也不证明 Mini 上普通 AltServer 可经 Tailscale 使用。首次安装后再核实适用的维护方式及其与现有 Tailscale 的使用关系；不擅自安装第三方 VPN、迁移配对密钥或降低系统安全保护。

本记录不证明签名安装、设备信任、Developer Mode、USB 拔除后刷新或自然过期恢复。产品 revision 和 IPA 保持 `107290abe`，S29/S30 均待实际设备证据。

## USB 接入后的直接观察

用户随后确认已接线，Air USB 树实际出现 iPhone；Finder 显示设备，Xcode Devices 与 `devicectl` 均识别 iPhone 15 Pro Max /iOS26.4。`devicectl` 报 connected (no DDI)，Xcode 明示 Developer Mode disabled。设备标识仅留本机，不写进仓库。

打开 Finder 设备页检查连接时出现“要加密备份吗”提示；用户截图显示同步步骤2/4正在备份。root 未点击“立即备份”，也未选择“加密备份”“不加密”或“不再警告”。Escape、Command-period 和 Command-W 未退出该提示，随后 Finder 文件菜单“全部关闭”实际关闭设备页及提示；重新打开设备页后没有进行中的同步/备份、底部只有“同步”按钮，显示“此Mac上的上次备份：从未”。本地加密复选框及连接时自动同步均为0，iCloud备份为已选中。未改这些选项、未开启Wi-Fi显示、未恢复或删除设备数据。备份环节的确切触发原因未确认，不能把“自动同步触发”推测写成已证实根因，也不能仅凭窗口关闭断言停止；停止状态依据后续设备页。

Xcode Apple Accounts 页面没有已登录账号；已打开官方登录输入页。iPhone Mirroring 已导航到 Settings → Privacy & Security → Developer Mode，实际开关为Off；仅导航，未切换或重启。该页提示开启会降低设备安全性，电脑操作工具要求此类更改在执行时单独确认，已向用户提出该具体动作的确认。账号登录、签名和首次启动尚未完成。

用户核对风险与付费分发区别后自行完成开启，并回复“开好了”。随后直接读取设备详情确认 `pairingState=paired`、`ddiServicesAvailable=true`、`developerModeStatus=enabled`，因此此前开发者模式资源缺口已关闭；未把用户一句回复单独当作运行证据。设备详情原始JSON仅存本机私有临时文件。

Xcode登录页仍停在空的 Email or Phone Number 输入框，尚无签名账号。下一实际门槛为用户在已打开的本机Apple登录界面完成一次普通账号登录；没有向聊天索取密码、读取其他账号凭据或购买开发者会员。S29仍待签名、安装及物理设备启动，S30不变。

## 免费签名与首次安装

用户回复“done”后，Xcode实际账户页显示已登录的免费 Personal Team。为避免将个人签名配置写入仓库，root将产品 revision `107290abe` 的完整 iOS 源码复制到0700私有临时目录，在该临时项目选择实际 Personal Team。Xcode完成 provisioning，面向这台物理iPhone的 Release arm64构建成功，`codesign --verify --deep --strict`通过。该包是同一产品源码重新构建并签名的产物，不宣称与既有unsigned IPA字节相同。

实际嵌入的development profile包含该设备，创建时间为2026-10-06 19:31:19、到期为2026-10-13 19:31:19（Asia/Shanghai）；App bundle为`win.nanoim.ios`，版本0.1.0/build1、最低iOS26.0，Release无ATS exception。账号邮箱、设备标识、个人Team ID与原始profile仅保留在本机私有记录，不提交仓库。

19:33实际`devicectl device install app`返回success，并返回已安装bundle `win.nanoim.ios`。随后在物理iPhone的Spotlight找到图标“Nano IM”，点击后iOS弹出Untrusted Developer，明确要求在设备管理中信任本次Apple Development证书。因此安装已证实，首次运行及登录聊天尚未通过。root未点击信任；已按电脑操作工具的安全权限更改要求提出具体行动确认。

之后镜像的坐标点击与滚动持续返回`noWindowsAvailable`，inventory也曾timeout。重新绑定/重置后截图、键盘及Mac菜单语义操作仍可用，键盘Spotlight打开Settings后实际画面为General；未到达开发者信任页。镜像窗口缩小再恢复原大小未恢复坐标操作；无效PageDown未计作滚动成功。故不笼统声称镜像断连，也不将失败的导航动作记为完成。

这次Xcode USB签名安装不证明AltStore导入、无线续签、Mini异地维护或自然过期恢复；S29仍缺实际运行旅程，S30继续未通过。

暂停本轮手机验证前已终止本次临时Tailscale前台HTTPS Serve，`serve status --json`回到原有`{}`；正常退出本次隔离IM/Gateway，62008监听消失、原PID均退出，fixture SQLite及恢复配置保留。没有改生产或现有用户网络配置；恢复本次fixture即可继续。
