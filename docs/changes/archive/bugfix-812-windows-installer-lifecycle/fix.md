# bugfix-812 Windows 桌面安装器生命周期

## 原始报告

> Windows Inno 卸载后登录计划任务、Run 项和版本目录里的宿主可能继续启动；修真实卸载链，停进程、移除自己所有的自动启动注册，保护所有用户工作区、配置和独立安装节点。私有版→官方包覆盖仍带上旧 seed-archives/desktop-defaults.json，需正确撤销旧发布源和旧策略；scripts/build-desktop-windows.ps1:60 复用旧release EXE，确保构建可复现。

## 现象与根因

在 develop 的 1bdc4646c 检查三个实际入口：

- Inno 仅在 PrepareToInstall 调用已有桌面程序的 --stop。卸载日志只认识安装器写入的文件与注册项。登录后由 Rust 写入的 HKCU Run 项、C# 创建的每连接登录与更新任务都在日志之外。计划任务的动作指向用户数据目录中的版本宿主，删除 bin 目录后仍可运行。
- feat-799 的宿主支持从官方 seed 撤销私有 defaults；但安装器对缺失的可选源文件直接跳过。私有安装的 seed 副本继续存在，下一次启动会将旧策略重新复制到生效目录。打包输出目录同样只复制可选文件。
- 构建脚本仅在 release EXE 不存在时才运行 Cargo。即使 Rust 输入已经改变，复用构建目录时仍会打包旧程序。

## M1-fix 与审查范围

由 Windows 候选包工作流验证实际安装、覆盖和卸载。独立代码审查核对任务和进程归属、配置与工作区保留、私有策略撤销和 Cargo 增量构建。

## 修复

Inno 在覆盖前使桌面宿主停止，在确认卸载后移除当前安装的运行注册。Windows 任务须同时匹配版本目录、宿主动作、配置路径与当前 SID 生成的任务名。更新正在执行时，卸载保留安装器供重试。清理只删除本安装的 Desktop 接管指针，保留会话、节点配置、工作区和独立节点的指针与任务。

覆盖安装替换 seed 与生效目录中的发行策略。已初始化私有 seed 的节点在安装完成前物化新 seed，让原计划任务下次启动选用新版本。打包调用 Cargo 的锁定增量构建，并清理输出目录中已被撤销的可选策略文件。

## 验证

本地执行 tests/unit/test_desktop_packaging.py 的 Inno 与 smoke 契约检查。原生生命周期验收入口为 Desktop client candidates / windows-x64，包含私有包、复用 release 目录的源码变更探针、官方包、回环 IM 身份绑定、真实任务注册、覆盖和卸载。Windows 10/11 客户机交互和真实重登录不在该 runner 的观察范围。
