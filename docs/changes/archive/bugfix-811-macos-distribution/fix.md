# bugfix-811 macOS 桌面发行包

## 原始报告

> 正式包 LSMinimumSystemVersion 12.0，但正式 runtime 内 Node v24.22.1 arm64 Mach-O LC_BUILD_VERSION minos 13.5.0，统一受支持下限与下载说明，做产物一致性验证。

> 实现/核实现有正式商业发布 Developer ID 签名+公证+staple 和真实分发检查，保留明确区分的 unsigned 测试渠道。

## 已确认的发布策略调整

> 默认无证书也可以按现有统一流程发布 Mac、Windows、Node；Mac 默认产物在按需打开的安装说明和发行说明准确标注「未经 Apple 公证」，区分测试包和可对外分发的未公证包。

需要公证时在发布表单显式选择；凭据缺失或验证失败中止该次发布。可选模式的真实 Apple 回执不作为本次交付条件。

## 现象 / 复现

在 develop 的 1bdc4646c 上，Tauri 配置和打包器各自写死 12.0。官网下载区和安装引导只列芯片型号。正式发布工作流直接从候选构建取 DMG，打包脚本对 app 使用 ad-hoc 签名，未向 Apple 提交公证或检验磁盘映像。记录历史包的实测见下文。

## 根因

feat-790 将宿主和固定 Node 运行时分开构建，以便用户首次启动时离线解包，此后可以按描述文件更新运行时。宿主声明的系统下限没有与种子包里的二进制对照。候选构建验证了宿主启动和 Node 版本，但正式发布复用同一候选，只有大小与哈希校验。需保留离线首装、分包更新和显式版本发布。

## 本次审查安排

核对从候选到正式发布的产物身份、包内系统下限、缺凭据时的失败路径、客户端下载说明和真实 macOS 验证范围。

## 修复

M1-fix 统一 Tauri、包内 Info.plist、公开下载区及电脑接入引导的下限为 Apple Silicon / macOS 15.0。构建取配置里的 deployment target；打包验收另外读取 DMG 和两个归档的实际 Mach-O load commands。默认发行的未公证 DMG 通过包体验证后，发布器可与 Windows 和 Node 一起发布。IM 按已选版本清单提供渠道，公开首页、电脑接入与恢复下载共用 Mac 安装说明，在说明内披露公证状态；GitHub Release 说明也标记渠道。可选的公证链在隔离签名 runner 上重新签署原生代码、重算 OTA 描述文件和种子哈希，分别提交 app 与 DMG 公证、装订票据，最后生成实际 DMG 的大小和 SHA-256。普通 PR 继续生成 unsigned-test artifact。发布器仅接收与所选公开渠道相符的清单；内测 artifact 不能直接上传。

## 验证

- 基线来自 [v2.2.0](https://github.com/Mrchen116/nano-multiagent/releases/tag/v2.2.0) 的公开 DMG，SHA-256 为 `a92b11c59922096292d80e2e8e270cb320b71dc854c47eaf2a754c9b904d8bb9`。macOS 26.5.2 arm64 实测 Info.plist 为 12.0、Rust 宿主为 11.0、Node 24.22.1 为 13.5。DMG 无签名，app 为 ad-hoc，两者均无装订票据；`syspolicy_check distribution` 返回 70。
- 该 DMG 的 runtime 归档 SHA-256 为 `663f716df68a2d3f0efacb672c6166ba5d21e6097b8944e7522d18544d56fa41`。其中 `p/255b57e25139fbf9/prebuilt/darwin-arm64-napi-v9.node` 属于 `node-addon-require-builtin-darwin-arm64@0.1.10`，arm64 的 `LC_BUILD_VERSION minos` 为 **15.0**。对种子内两份归档的原生文件逐个检查，这是最高值。pnpm 附带的 x86_64 专用 reflink 插件不参与 arm64 下限计算。
- 在隔离目录用正式包内的 Node、应用和 runtime 重建依赖，走产品 `prepareProfile → RuntimeClient → dsh --profile nano`。DSH 宿主准备和 Cordis 加载器会用 `node-addon-require-builtin` 读取 Node 的 ESM/CJS 内部加载器。记录实际 `process.dlopen` 发现，成功加载的缓存文件与上述归档成员 SHA-256 同为 `e5a7ffbebf1ca0f837a8c4187156d0d34ffc2cab512330dbf2746677779a4fee`；`initialize` 和 `runtime.health` 成功。唯一对照变量是使该模块的 dlopen 失败，DSH 报 `host preparation failed: No usable native binding found for node-addon-require-builtin-darwin-arm64` 并在初始化前退出，无法用 13.5 声明完整客户端支持范围。
- 在本机用历史二进制和种子、修复后的 Info.plist 生成独立 ad-hoc DMG。验证器从 DMG 拷出应用并卸载映像，核验哈希、架构、系统下限；离线首启、Node 版本、CLI 和 DSH 健康检查通过。保留 12.0 声明的历史 DMG 被拒绝。下载 UI 13 项、Python 定向 8 项通过。
- 无签名身份和公证 profile 时，sign 在写入输出前失败；历史 DMG 在公证版 verify 的签名检查即失败。以 ad-hoc 身份演练公证版脚本的原生重签和归档重算时，Hardened Runtime 阻止加载无有效 Team ID 的 addon；独立 DSH 健康检查据此拒绝该测试包。实际 Developer ID 团队身份、Apple Accepted submission IDs、两处 staple、Gatekeeper 和公证版签名后的 DSH 健康留待具备凭据时验收。未创建 Release 或操作生产。
- 与 #568 的 2163c8956 进行 git merge-tree 无冲突，合成工作流仍执行 Windows 的 `installer-lifecycle.ps1`。
- 与其余七项的合成基线 `b5359389c` 执行 `git merge-tree --write-tree`，实现提交 `ed33f32cb` 对应合成树 `f3c040cc217df2b72b7251cfc404f4a22a881527` 无冲突。#810 的 Mac 与 Windows 原生生命周期调用、#568 的 Windows 安装验证和本项 DMG 独立验证均存在。

## 发布模式回归

- 在 macOS 26.5.2 arm64 下载本 PR 第一次 CI 的真实候选（Actions artifact 15220571925），DMG SHA-256 为 `455db326cf69e9e83c5c695acc7572f202f010d62f03a562d11ff9e6865cc6c8`。移除三个 Apple 配置变量后，`verify --mode unnotarized` 完成最低系统检查、从 DMG 拷出 app、离线首启及 DSH 健康检查，外部清单记录 unnotarized，DMG 字节未改。该次演练使用 CI 候选，未指定新的发行版本。
- 无凭据运行 sign 和公证版 verify 均明确失败，未生成已签产物、未改为公证标记。发布器使用真实入口、版本化的 Mac、Windows desktop、Windows node、Node 测试清单和本地 gh/curl 替身，验证默认发行的说明、全部附件及校验后的清单。选公证却提供未公证包、选默认却提供公证包、直接提供内测包时均在上传前失败。
- 定向前端 16、IM 与 Node 34、Python 4 项通过。下载区与首页主按钮旁提供同一安装说明入口，旧清单沿用历史未公证状态。未向 Apple 提交公证或向 GitHub 发布安装包。
