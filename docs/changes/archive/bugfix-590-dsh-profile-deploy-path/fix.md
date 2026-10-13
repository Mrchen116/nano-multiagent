# bugfix-590: DSH profile 链接随部署更新

## Relations

- Related: refactor-581

## 原始报告

- “刚才 DSH profile 还指向旧 worktree 的问题为何发生，下次是否还会出现”
- “其实是不是应该把部署目录固化下来，不要每次都不同名字”
- “直接去掉SHA不方便吗”
- “profile 的链接检查仍应修复，ok没问题。那你开始统一收口吧”

## 现象 / 复现

正式 MacBook Air Gateway 从旧 prod-main-e13d2aeab 切到 prod-main-b75ae90fa，持久 nano profile 的 dsh-integration 与 dsh-base 链接仍指向旧 checkout。新 DSH 入口加载旧 bundle/依赖，启动报 web_fetch 重复注册，节点离线。停止后仅更新两个链接即恢复 ready。Mini 主仓路径固定，未触发。

运维者要求生产 worktree 固定命名 prod-main，版本由 Git SHA 和部署记录追踪；开发主仓已有改动必须保留。

## 根因

prepareProfile() 的 link() 对 symlink() 返回的 EEXIST 无条件忽略，未比较既有目标与当前锁定安装。持久 DSH_HOME 在升级间复用，而 Air 每次部署更换 checkout；入口与 profile 因此分属两次安装。已有 runtime-profile/supervisor 测试只用新临时 home 或在同一安装重启，没有覆盖带旧链接的持久 profile。

该逻辑由 c67e07a699（refactor-581）引入，原意是将官方 DSH profile 与当前锁定依赖绑定，同时保持会话、状态和身份持久化；修复必须保留这些数据，不能删除整个 DSH_HOME 或改上游源码。产品只维护自己生成的两个软链接，遇到同名普通文件/目录明确失败并保留内容。固定生产目录减少路径漂移，但仍须自动刷新依赖路径变化后的链接。

范围为单个 M1-fix：修复链接检查及回归、统一部署 skill/runbook/拓扑文档的固定 prod-main 契约，并迁移当前 Air 运行路径验证。Mini 已固定的主仓、IM 数据和 Tunnel 路径保持既有部署方式。

## 修复

- prepareProfile 对两个受管软链接比较解析后的目标；保留正确链接，替换过期或悬空链接。readlink 对普通文件/目录失败，原内容不被覆盖。只修改 Nano 集成层，不修改 DSH 上游；Gateway 生命周期锁保证同一 config 启动串行。
- 修复提交 58192fa32；71ad063c3 明确首次迁移先构建新 checkout、从旧 live checkout stop，再在新目录 restart。
- 部署 skill、runbook、生产拓扑统一固定 prod-main、精确 SHA 记录、停止后更新、同目录回退。Mini 保留固定主仓。Gateway current lifecycle 补充升级后加载当前安装并保留状态的场景。

## 验证

- Red：原实现 runtime-profile 4 个测试中 3 个失败，暴露旧/悬空链接不刷新及普通 entry 冲突不报错。
- Green：runtime-profile 与 supervisor 共 5 测试通过，包含真实锁定 DSH 启动、冷恢复及进程恢复；扩展既有 owner 测试，无平行测试文件。
- pnpm build、pnpm typecheck 通过；pnpm test 全部 62 文件/197 测试通过；pytest -m "not e2e" 共 54 通过/31 deselected；Ruff check/format 通过。
- 独立代码审查覆盖 bb3d27184..58192fa32，首次迁移文档 P2 在 71ad063c3 闭环，无存活 finding。
- Air 已从固定 ~/.codex/worktrees/prod-main/nano-multiagent 启动；LaunchAgent/live cwd/DSH 入口与两个 profile 链接均属于该目录，ready=true。此次固定目录上线 bb3d27184（相较已上线 b75ae90fa 仅增加首文档），自动链接修复代码仍在 PR 分支，未冒充已在正式 main 生效。
- Air Gateway config、设备凭据和通道 manifest 与迁移前逐字一致，持久 DSH_HOME 继续复用；本机无 IM 8011。Mini IM/前端/Tunnel 未改，沿用此前已验证部署。受限部署备份与私密 runtime 记录仅在本机，不入 Git。
- Web/iOS 源码、依赖、数据库迁移均未变；本地不重复此前相同产品树的 Web/iOS 验收，远端 CI 仍执行全部门禁。
