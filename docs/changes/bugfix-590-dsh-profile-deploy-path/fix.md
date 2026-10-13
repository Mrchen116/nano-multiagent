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
