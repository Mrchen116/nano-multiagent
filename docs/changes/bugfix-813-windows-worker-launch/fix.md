# bugfix-813 Windows 本机 Worker 启动

## 原始报告

> 设置探测 codex.cmd/.bat 可用但实际 spawn('codex',...) 无法运行。
> 对各受支持的受影响 Worker 让探测和实际启动一致，校验含空格路径及参数边界，保持 .exe 与非 Windows 行为。做合法无害 fixture 的 Windows 启动测试，走真实调用链。

## 现象 / 复现

基线 `1bdc4646c`。桌面设置按 PATH 识别 Codex、Claude Code 和 Antigravity 的 Windows 批处理入口，三个驱动均通过 CliProcess 直接 spawn 裸命令。仅安装批处理入口时，设置显示可用，委派无法完成第一个 stdio 握手。

## 根因

feat-790 引入的设置探测（`c75e0415e`）独自枚举后缀，运行时仍使用直接可执行文件的启动契约。Windows 批处理文件需要命令解释器。桌面探测与真实一级委派应选择同一安装，保留 Worker 的独立进程、原生协议和参数内容。现有驱动 fixture 使用 Unix shebang，未覆盖 Windows 包装脚本。

## 本次审查安排

复核 Windows 探测和启动选择、批处理参数边界、原生进程握手及关闭、其他平台调用方式。原生 Windows runner 使用临时 fixture，覆盖三种 Worker。
