---
name: prod-fleet-deploy
description: "用户明确要求部署、更新或重启个人生产双节点舰队的指定服务时使用；不用于只读故障调查或隔离 E2E。"
---

# 生产舰队部署

完成授权范围内的部署/重启，并证明目标版本、拓扑与健康。具体命令、身份、迁移、日志和故障速查在 [runbook](references/runbook.md)，执行相关操作时读取对应节。

## 不变量

- Mini 运行唯一 IM `:8011`、Gateway `mac-mini`、LLM_Bridge；本机只运行 Gateway `macbook-air` 和自己的 LLM_PROXY。两节点 ID 不同、IM owner 为同一真实 UUID；飞书只挂 mini。
- Mini 主仓只安全 fast-forward；本机主仓只 fetch，保留 dirty/untracked，从 detached 的目标 `prod-main-*` worktree 启动 Gateway，共用主仓 `.venv`。
- 常规部署复用 mini 持久 IM signing key；缺失/为空先停止，不自动换钥。Gateway config 先 stop 再改，防运行态回写；稳定环境写 config，不靠一次启动的 inline 设置。
- 若仍是旧 PA 目录布局，先完成 [无覆盖迁移](../../../docs/operations/pa-workspace-layout-migration.md)，备份并保持密钥不变；迁移完成后不重复执行。
- 按授权范围更新；依赖顺序为 IM → 需要更新的代理 → Gateway。涉及前端时重建未入仓的 dist。
- 新版本健康后才回收干净且无进程使用的旧 `prod-main-*`，保留并报告有修改的目录，不 force、不动其他用途 worktree。签名换钥、数据清理与身份迁移不从普通部署推导授权。

完成需核实目标 SHA、live command/state/LaunchAgent 指向目标 checkout，IM HTTP、两 node online、owner 一致、代理和相关真实入口健康，本机无 IM `:8011`。局部操作验证受影响服务及其连接即可；合并不等于部署，进程存在不等于健康。
