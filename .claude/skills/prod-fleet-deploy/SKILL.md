---
name: prod-fleet-deploy
description: "用户明确要求部署、更新或重启个人生产公网 IM 或双节点舰队的指定服务时使用；不用于只读故障调查或隔离 E2E。"
---

# 生产舰队部署

完成授权范围内的部署/重启，并证明目标版本、拓扑与健康。具体命令、身份、迁移、日志和故障速查在 [runbook](references/runbook.md)，执行相关操作时读取对应节。

## 不变量

- 当前拓扑与入口以 [生产舰队](../../../docs/operations/prod-fleet.md) 为准：官网经 Cloudflare Tunnel 到 Mini 的唯一 loopback IM；MacBook Air 不运行 IM。普通部署更新这套源站即更新官网，不另建公网实例。
- Mini 主仓只安全 fast-forward；MacBook Air 主仓只 fetch，保留 dirty/untracked，从 detached 的目标 `prod-main-*` worktree 启动 Gateway，共用主仓 `.venv`。
- 复用现有 IM/Tunnel LaunchAgent 和公网 launcher；不退回旧 `nohup uvicorn`、内网访问入口或全网卡监听。保留 Cloudflare HTTPS 重定向，公网模式必须使用 `IM.cli.public_server`。
- 常规部署复用 mini 持久 IM signing key、数据库、附件和各 Gateway 设备密钥/运行凭据；缺失先停止，不自动换钥、重新 bind 或初始化公司。Gateway config 先 stop 再改，防运行态回写；稳定环境写 config，不靠一次启动的 inline 设置。
- 若仍是旧 PA 目录布局，先完成 [无覆盖迁移](../../../docs/operations/pa-workspace-layout-migration.md)，备份并保持密钥不变；迁移完成后不重复执行。
- 按授权范围更新；依赖顺序为 IM → 需要更新的代理 → Gateway。涉及前端时重建未入仓的 dist。
- 新版本健康后才回收干净且无进程使用的旧 `prod-main-*`，保留并报告有修改的目录，不 force、不动其他用途 worktree。签名换钥、数据清理与身份迁移不从普通部署推导授权。

完成需核实目标 SHA、live command/state/LaunchAgent 指向目标 checkout，公网 HTTPS 页面/API、HTTP→HTTPS 跳转、Tunnel、loopback 监听、两 node online、owner 一致、代理和相关真实入口健康，MacBook Air 无 IM `:8011`。局部操作验证受影响服务及其连接即可；合并不等于部署，进程存在不等于健康。

若本次授权变更了生产入口、启动方式或身份流程，交付前同步本 Skill、runbook 与生产拓扑文档；不能只在对话或一次性部署记录中保存新流程。
