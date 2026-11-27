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
