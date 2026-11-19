# 跨机预览设计审查

## Round 1

- Reviewer target 为独立 reviewer `/root/design_review`，基线 `75bf0b74e`。
- review_mode 为 full。此次为首轮，范围含首文档、设计、M1 骨架、现有启停及浏览器入口。
- started_at 为 2026-11-20T00:19:20+09:00。completed_at 为 2026-11-20T00:19:42+09:00。duration 为 22 秒。

**Verdict — Issues Found，0 CRITICAL，2 WARNING。**

### 覆盖与证据

两个 worktree 分别映射到 Mini 的源码和运行目录。独立测试 Tunnel 和 Traefik 只承担请求路由，实例归属、版本交付和更新属于开发命令，IM 和 Gateway 继续承担既有登录、注册节点和实时通信职责。单实例锁和独立路由文件支持更新 A 时保留 B 的连接。单一 M1 可整体交付，无并行工作包争用接口。现有 `scripts/e2e-down.sh` 已按运行目录核实进程身份，适合复用。

两项用户场景涉及测试工作流。沿用 IM 身份及 WebSocket 契约，长期使用说明落在开发文档，无产品 delta、视觉原型或生产迁移需求。M1 双实例隔离、数据保留和 B 的既有连接读写均有对应验收。现场通配 TLS、独立 Tunnel 和双机可达性须留待实测。本轮未访问远端。

### Issues

- **R1-W1 · 预览更新缺少可复用的持久启动入口。** `design.md` 第 5、9 行指定复用运行目录和现有 E2E 启停，但当前 `scripts/e2e-up.sh` 第 195–221、262–265、310–315 行会重新生成 JWT、按 PID 派生 node ID、覆盖 Gateway 配置、删除数据库及设备密钥，再初始化管理员和绑定。用该入口执行更新会丢失 A 的已写数据和节点绑定。请确定首次初始化和后续启动的职责边界，交代更新或失败重试时哪些步骤只能在新实例执行，以及如何验证一次失败后的重试仍能读回原记录。现有本地 E2E 仍需要每次从干净状态启动。
- **R1-W2 · 公网浏览器登录与节点内部地址尚未接通。** `design.md` 第 3–5 行指定公网登录并交付 URL。现有 `scripts/e2e-up.sh` 第 188–192、220、278 行把 IM 对外地址及 Gateway 连接地址都指向 loopback。浏览器登录按外部 Origin 校验，见 `apps/im-server/src/identity-routes.ts` 第 84–100 行。沿用该配置，即使脚本通过公网做程序登录，Air 浏览器仍会收到 403。请明确每实例的公开 HTTPS 地址、Gateway 内部地址和如何向操作者交付私有登录凭据，以实际浏览器会话和 WSS 收发验证该路径。

首次审查，无历史问题需要闭环。

### Author Resolutions

- R1-W1 accepted。设计补充新建、更新、失败重试的数据边界和验收。
- R1-W2 accepted。设计补充浏览器公开地址、节点内部地址、凭据交付和真实 WSS 验证。
