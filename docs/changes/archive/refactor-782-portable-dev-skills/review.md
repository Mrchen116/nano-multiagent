# 实施审查与验收

## 范围

Nano 的受审改动从 `ac275ecc7` 到 `20e54455e`。独立库受审版本为 `bcc82e8`，补入迁出测试和编号修复后的提交为 `cf46b1d`。迁出 21 个已有 skill，新增统一入口，Nano 保留三个项目专属 skill。无产品行为契约增量。

## 独立代码审查

Sol 独立审查安装来源、项目/库路径、技能和流程文档归属、Nano 引用和 CI。发现新旧 worktree 在全新 clone 第一次取号可能分别创建计数器。外库 cf46b1d 改为始终使用同一 Git common dir 锁和计数文件，补充首次保留断言，reviewer 已复核关闭。审查时列为待验的远端 clone 和跨会话识别由下列交付试验补足。

## 使用证据

- 在已有 Git 项目中以 gpt-6.2-sol、low 运行简单 README 拼写修复。项目没有安装步骤。该次会话同时将一个小修核查约定直接写入已加载 skill 的真实源码；业务 diff 和独立库 diff 分属各自 checkout。
- 从新的 Nano worktree 开另一个同型号只读会话，正确指出独立库的实际 skill 路径、新约定的 `git diff --check` 和本仓 PR base `develop`。未运行其他模型试用。
- 已从独立库提交并推送，再以已授权 Git 身份从 GitHub 做全新浅 clone。在隔离注册目录中 22 个 skill 全部加载自该 clone；本机 Codex/Claude 用户级注册重复执行零新增。Claude 仅检查文件注册，原生 Windows 未实测。
- 外库 8 个测试通过，覆盖同源幂等、同名冲突、编号脚本及通用文档契约。Statechart 仓外运行，在最小 TLA+ 模型中检出预设反例。
- Nano 在无用户 skills 的环境通过文档检查和 42 个相关测试；全量非 E2E Python 测试 136 passed。前端 1246 项测试、生产构建、后端构建、类型检查和原生交互资源检查通过。运行中有前后端并发时，部分本地 DSH 集成用例超过等待时间；完整服务端结果以交付时的实测和 PR CI 为准。

## 交付

库版本和后续改进由独立 Git 仓管理，项目通过目标环境安装读取。Nano 的 CI 可以在没有该用户级安装的 checkout 中运行。PR、CI 的实际状态见本次 GitHub checks。
