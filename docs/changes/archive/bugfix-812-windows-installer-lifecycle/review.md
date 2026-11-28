# bugfix-812 审查与验证

独立 change-code-review 审查了基线 `1bdc4646c` 至实现 `1933a1621` 的完整改动。确认任务的 SID、动作及版本路径归属检查可区分 Desktop 和独立节点，打包会重新经过 Cargo。初审提出两项阻塞问题。

1. 覆盖安装在检查活动更新任务前停止了 Gateway，可能使正在切换的更新同时失败。修正后，新安装包的维护程序先检查正在执行的更新，再调用旧客户端的停止入口。Windows 验收使用真实运行的调度 worker，检查被拒绝的覆盖和卸载保留当前 shell 和 Gateway。
2. Inno 的 ssPostInstall 异常无法可靠报告安装失败，静默安装时桌面致命错误弹窗也可能阻塞。修正后，PrepareToInstall 使用新安装包内的程序和 seed 在文件替换前执行准备，安装器收到非零退出时可重试。准备阶段保留私有策略，成功写回连接指针后才更新 seed 标记。Windows 验收阻塞缓存文件写入，检查失败后旧安装可识别，再解除故障重试。

本地 Inno、smoke 和发布输入的四项检查通过。依赖图检查在本 worktree 缺少 node_modules；复用同锁文件、同打包脚本和同测试的 feat-805 依赖目录单测通过，product-contracts 在该缓存 checkout 的 exports 有差异。文档完整性与 unit 归档检查通过。Windows 原生执行结果以 PR 的 windows-x64 作业为准。
