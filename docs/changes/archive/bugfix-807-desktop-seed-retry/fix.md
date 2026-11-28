# bugfix-807-desktop-seed-retry 桌面首次准备恢复损坏的缓存

## Relations

- Related: [Desktop 首次接入与失败恢复契约](../../../specs/im/desktop-client.md)

## 原始报告

> 跨平台首次准备留下半份 runtime/app 缓存后，GUI 重试反复使用坏缓存。apps/desktop/src/local_node.rs:317 和 host_server.rs:1045。使正常首启和中断/损坏后的重试均可从完好的随包源恢复，不损及已安装版本或用户数据，用实际解包入口验证。

## 现象 / 复现

在隔离的 desktop/cache 中预置文件名正确但内容截断的归档，并提供完整的随包归档。首次准备与准备页的重试均进入 `ensure_seed_bundle_installed`，持续将同一份本地缓存交给系统 tar。

## 根因

`c75e0415e6` 引入分离归档以离线准备受管 Node 并为后续更新复用缓存。复制直接写最终路径，后续仅以文件存在判定可用，未验证描述文件及归档内容是否匹配发布摘要。重试状态机已经重新派发工作，故障发生在缓存的读取与发布。

## 本次审查安排

核对两个平台共用的缓存恢复与失败行为，通过真实 tar、打包布局脚本和隔离数据目录验证。保留原有已就绪版本快路径、会话和工作区。

## 修复

`ea158bdbf` 在读取描述文件及解压 runtime、app 前校验缓存的 SHA-256。缓存缺失或摘要不匹配时，从安装包复制到同目录的暂存文件，校验完整副本后再重命名替换。进程中断后的下一次准备会重新使用该暂存路径。随包源校验失败时沿用原准备页的错误与重试处理。

## 验证

macOS arm64 上运行 `cargo test --locked --manifest-path apps/desktop/Cargo.toml --lib seed_retry_repairs_cached_archives_from_bundle`。

- 基线 `dfe7ebdc4` 成功完成干净首启，但恢复随包源后通过准备页的 HTTP 入口重试仍得到系统 tar 的 `Unrecognized archive format`。
- 修复版本先在干净目录解包；在另一个目录预置截断 runtime、与原件等长的坏 app 及截断描述文件。在随包 app 损坏时，错误包含归档名和摘要不匹配原因，目标版本尚未发布。恢复源文件后，从 bootstrap 取得能力 cookie，通过准备页同一 POST 入口重试并到达 ready。用例检查解出的布局及 app 内容、缓存、原有版本标记、会话和工作区文件。
- macOS 桌面库全部 10 个测试通过。用例使用小型 tar.gz、发行用布局脚本和系统 tar；macOS fixture 经脚本调用测试机的 Node，Windows fixture 包含运行器上的 node.exe。真实安装包与内置 Node 由 PR 的平台候选包工作流验证。

## Windows 安装包冷启动补充

八项改动的合成运行在 Windows Server 2022 首次准备失败，宿主仍可响应。错误在启动后约 12 秒已经写入日志，旧 smoke 等到 300 秒超时才报错。该次日志仅有错误码 5。[合成运行](https://github.com/Mrchen116/nano-multiagent/actions/runs/46043736174)

在 #569 的相同原生 runner 上，前 6 次隔离冷启动成功，第 7 次记录了明确的失败操作。解包和运行布局脚本已完成，将 `runtimes/.seed-rt-8048` 重命名为正式 runtime 目录时出现 `Access is denied. (os error 5)`。受控用例确认，子文件仍有打开的句柄时，重命名返回同一错误，释放句柄后可以成功。另一个用例通过 NTFS ACL 拒绝删除对象和父目录删除子项的权限，也得到错误 5。日志不能识别原始运行中的占用进程。[原生复现及用例](https://github.com/Mrchen116/nano-multiagent/actions/runs/46047529634/job/140670414959)

`6a90a4eab` 仅在 Windows 发布已完成的种子目录遇到错误 5 时重试同一次重命名，最多额外 6 次，总退避 1.575 秒。持续拒绝仍返回源路径、目标路径和原始系统错误；其他错误立即返回。Windows smoke 从已认证的宿主状态读取准备结果，遇到终态错误立即失败。

该退避通过临时句柄与真实 ACL 两个受控用例，但安装包的第 9 次隔离冷启动仍在同一 runtime 目录重命名处失败，前 8 次成功。[退避修复的 Windows 记录](https://github.com/Mrchen116/nano-multiagent/actions/runs/46048840838/job/140674801173)

Windows 随包 runtime 现在在独占的物理目录中完成解包与布局。写入 `.ready` 后，由内置 Node 建立目录联接（junction），宿主原子地将联接发布到原有的 `runtimes/<sha>`。已打开的子文件可以一直留在原目录。每个已发布联接保有自己的物理目录，后续准备不会按进程号复用或删除它。已安装的普通 runtime 目录继续走原就绪检查，既有 OTA 地址、版本布局和活动指针格式均兼容。暂时占用与永久拒绝的受控测试保留。

## 原生验收

- Windows Server 2022 x64 对 PR head `4d9eb3447` 连续执行 10 次安装包冷启动。每次使用新目录，从随包归档解包，达到就绪状态，再验证内置 Node 24.22.1 和 CLI；第 10 次还完成 DSH 探测。13 个库测试与 1 个独立实例锁测试均通过，覆盖子文件持续打开时发布 junction、临时锁释放、真实 ACL 拒绝，以及解除权限后通过准备页 HTTP 重试恢复并保留数据。[Windows 原生运行](https://github.com/Mrchen116/nano-multiagent/actions/runs/46051438881/job/140683465714)
- macOS arm64 的 10 个库测试、1 个独立实例锁测试和实际应用包 smoke 均通过。[macOS 原生运行](https://github.com/Mrchen116/nano-multiagent/actions/runs/46051438881/job/140683465447)
- 运行时代码提交为 `722fc1b16`。后续提交只涉及测试与文档，日常 Windows CI 执行一次完整 smoke，保留准备失败即时报错与受控回归。准备页验证经过实际 HTTP 入口，未手动操作 WebView。
