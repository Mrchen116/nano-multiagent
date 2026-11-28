# bugfix-811 独立代码审查

独立 reviewer 对照 develop 基线 `d0ef590a0` 审查实现 `a2a022669`，并复核最终两个差量至 `ed33f32cb`。源码选择、候选与正式 artifact 的流转、包内兼容性、验收边界和下载说明均已核对，结论为无未关闭的阻塞项。

初审发现旧桌面源码 SHA 可以通过发布 source 阶段，随后因历史 checkout 不含分发脚本报错。`ed33f32cb` 在 source 阶段给出明确诊断并更新操作说明。使用含打包脚本的旧源码条件和完整新源码分别执行条件分支，结果为拒绝、通过。独立复核关闭该问题。

`2b66d100b` 保留原 Mac 宿主 smoke，独立执行从 DMG 拷出的实际应用。与七项合成基线的只读 merge-tree 核对通过。独立定向 Python 检查 8 项通过，shell/Node 语法和 diff 检查通过。

可选公证模式的真实签名产物留待组织 runner 验证。需保留 Apple 返回的 Accepted submission IDs、最终 DMG 哈希和独立 runner 对 app、DMG、首次启动及同 Team 原生模块加载的输出。具体历史产物与对照实验见 [修复记录](fix.md)。
