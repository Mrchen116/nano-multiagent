# Mini AltServer 准备记录

记录日期：2026-10-05（Asia/Shanghai）。本记录只证明 Mini 软件准备，不证明 iPhone 配对、侧载、自动启动或续签。

- 先前 SSH 超时；本次重新直连既定 Mini 后 `/usr/bin/sw_vers` 成功，系统为 macOS26.5.2 /25F84，GUI console user 为预期用户。
- 原 `/Applications/AltServer.app` 不存在，未发现 AltServer 进程。安装只使用此前不存在的这个精确 App 目标，不覆盖其他应用。
- 从[官方 macOS 安装指南](https://faq.altstore.io/altstore-classic/how-to-install-altstore-macos)给出的 CDN 下载 AltServer ZIP：版本1.8 /build97，bundle `com.rileytestut.AltServer`，最低 macOS11.0，12,687,525 bytes，SHA-256 `1fa0f3ce7d77af70c4995455e713c922b799bcbb641ca9541953498920542c9c`。
- 当前 Mac 解包后 `codesign --verify --deep --strict` 成功，`spctl --assess --type execute --verbose=2` 为 accepted /Notarized Developer ID。ZIP传至Mini后先核对相同SHA，再于临时目录解包；Mini上同样签名验证和Gatekeeper assessment通过，才复制到 `/Applications/AltServer.app`。
- 安装后 Mini 精确目标再次签名验证通过，`open -a` 启动后真实进程来源为 `/Applications/AltServer.app/Contents/MacOS/AltServer`；后续新SSH读回 bundle/build及同一运行来源。未修改生产IM/Gateway或网络节点。

仍待实际 GUI/设备过程：检查菜单和登录启动设置、USB信任与Finder Wi-Fi sync、用户在本地输入Apple账号/验证码、安装AltStore/Nano、同网拔线刷新及自然过期恢复。没有凭进程存在宣称这些已完成；没有操作本 chat 尚未获使用时段的 iPhone。

完整步骤及最终标准见[安装方案](../installation-plan.md)，产物版本见[工具链记录](toolchain-readiness.md)。


## 同网后的只读复核

2026-10-08，用户确认两台电脑和手机同Wi-Fi。既定Mini SSH可达，实际AltServer进程仍来自 `/Applications/AltServer.app/Contents/MacOS/AltServer`。按当前已识别目标手机UDID只检查其精确 `/var/db/lockdown/` 配对文件，未找到；目录具有可遍历权限，因此不是仅由目录无法列出得出的判断。未读取或迁移任何配对密钥。该检查不是实际AltServer设备菜单、USB信任或刷新结果；目标设备的Mini配对仍待官方流程验证。Air的CoreDevice无线安装成功不替代Mini的legacy Wi-Fi同步发现。没有改Mini生产IM/Gateway、现有节点或用户网络设置。
