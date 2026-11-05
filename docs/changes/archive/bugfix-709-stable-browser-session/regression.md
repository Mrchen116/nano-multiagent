# bugfix-709 — 回归验证

> 对齐: [incident.md](incident.md)、[design.md](design.md)
>
> Validation snapshot: `8ece8ad0ec7b38c97183e4cbd11a93c0bc201984 → 8ece8ad0ec7b38c97183e4cbd11a93c0bc201984`

## Verdict

**pass — 本轮独立 Web 产品验收通过，blocking/major 问题 0。**

2026-11-04 09:20–09:24 +08:00，以真实浏览器观察指定提交的登录、恢复和退出结果。未阅读实现源码，也未以 worker 成功叙述替代实际操作。协议级边界由独立 verifier 的 [verification.md](verification.md) 记录，本报告不宣称已经实测 iOS 或等待过真实 30 天。

## 环境与范围

- 分支 `unit/bugfix-709`；开始时 HEAD 与指定 validated_at 一致，工作树干净。使用 caller 提供的该版本后端构建及生产前端构建；前端产物时间为 09:19，后端构建 09:17。未重建或修改产品实现。
- 入口 `http://127.0.0.1:18173/login`，真实 IM 在 18174，由隔离故障代理转发；专用身份 `stable709` / 显示名 `Session Test`。SQLite `/tmp/im-stable-709-runtime/im.sqlite3`。
- Playwright CLI 独立 headed Chromium session `stable709-review`。首轮 viewport 1280×900；新页面恢复及退出截图 1200×732。
- 按 design 的 auth-only 专项环境验收；没有 P/E/Q、Agent、模型或外部消息调用，无生产访问。
- 只调整 `/tmp/im-stable-709-runtime/server.mjs` 的故障注入代理：原断开响应模式之外，补充“收到上游 200 后返回 503，丢弃上游响应及 Set-Cookie”模式。真实后端路径未 mock。

## 复现验证与回归旅程

| 场景来源 | 实际操作和观察 | 结果 |
|---|---|---|
| design M1 reviewer：真实登录 | 在真实表单输入专用账号与密码，进入 `/chat`；页面显示 Session Test、Messages 与空会话状态。 | pass |
| incident 稳定浏览器凭据：响应丢失 | 登录后设置一次丢弃响应，在 `/login` 触发续期。服务日志 `Dropped refresh response after backend completed 200`；Chromium 透明重试，真实 refresh 返回 200，直接恢复 `/chat`，无需密码。 | pass |
| design M1 reviewer：失败后重试恢复 | 第二轮故障在后端完成 200 后由代理返回 503，不转发后端响应与 Cookie。页面停在 `/login`，显示 `The authentication service is temporarily unavailable. Try again shortly.` 和 `Refresh status`。点击该按钮立即恢复 `/chat`，没有密码输入。 | pass |
| incident 页面重载与接续 | 关闭原产品标签页，保留同一浏览器上下文的空白页，再打开 `/login`，自动进入 `/chat`，显示同一身份。此处验证页面关闭/重开，不声称浏览器进程或操作系统重启。 | pass |
| incident 重启 | 停止原独立服务 PID 29926，用 Node 24.22.1、同一脚本/数据库/secret 启动新进程 PID 42033，再打开 `/login` 自动进入 `/chat`。期间重启命令先因不存在的 Node 路径失败，修正路径后成功；临时连接拒绝是环境尚未启动，不计为产品失败。 | pass |
| incident 主动退出 | 账号菜单显示 `@stable709`，点击 `Sign out` 返回 `/login`；随后直接访问 `/chat` 仍被送回登录表单，Username/Password 为空，未自动恢复。 | pass |

修前故障依据 incident 已记录的生产只读取证；本轮不回退旧版本重新复现。修后确实构造了“服务端已成功续期、浏览器没有收到成功响应”的触发条件，恢复结果与旧问题不同。并发、30 天滚动期限、epoch/撤销/篡改、有效旧 JWT 升级与失步旧凭据拒绝、程序 JSON 轮换属于 design 指定的 worker/verifier 协议验证，不在浏览器中伪造其通过证据。

## 界面与操作观察

登录表单以 Username、Password、Sign in 顺序呈现，退出后密码要求明确；恢复成功后的账号名称和 Chat 导航让用户确认已回到自己的空间。临时错误明确区分服务不可用与密码错误，单一 Refresh status 动作可直接恢复，不迫使用户重新登录。该错误画面沿用简朴的顶端文字和按钮布局，未见遮挡或无法操作；本次没有视觉设计变更，也无 prototype must-match 项。截图实际查看后作出上述判断，没有把 DOM 快照当作视觉验收。

本地证据（不提交截图缓存）：

- `output/playwright/bugfix709-chat.png`：成功恢复后的真实聊天入口，1280×900。
- `output/playwright/bugfix709-retry.png`：故障提示及重试操作，1280×900。
- `output/playwright/bugfix709-logout.png`：退出后再次访问聊天仍要求密码，1200×732。
- `.playwright-cli/page-2026-11-04T01-22-54-344Z.yml`：点击 Refresh status 后 `/chat`。
- `.playwright-cli/page-2026-11-04T01-23-16-998Z.yml`：退出后访问 `/chat` 被送回 `/login`。
- `/tmp/im-stable-709-runtime/service.log`：两次上游成功后丢弃响应的记录以及新服务启动记录；不含会话凭据。

## 自动化测试增量与覆盖边界

本角色未新增或运行源码测试。浏览器通过真实 CLI 操作；长期协议回归增量与 HTTP 测试结果以独立 [verification.md](verification.md) 为准。未操作 iOS UI，未验证真实隔夜、30 天自然过期、生产 HTTPS/Tunnel 或所有历史掉线诱因；本轮通过只证明指定触发条件与明确的浏览器必验旅程。

已关闭本人创建的 `stable709-review` 浏览器会话。按 caller 交接约定保留隔离服务供主 Agent 清理：PID 文件 `/tmp/im-stable-709-runtime/pid`，当前 PID 42033；未停止其他服务。报告未提交或推送，由主 Agent 与并行 verifier 报告统一整合。

## 上层文档同步

- [x] `SPEC.md`：无需更新，未改变跨包架构。
- [x] `docs/specs/im/auth-tenancy.md`：需要同步稳定 Cookie、滚动续期和升级边界；所读 current 已包含该契约，具体一致性由 verifier 核对。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
