# M1 在线安全通道 — 真栈浏览器证据

## 环境

- 日期：2026-07-15（Asia/Shanghai）
- 入口：隔离 worktree 的 ephemeral IM + 真 Gateway foreground 进程，1440 × 1000 headed Chromium。
- 用户路径：登录 → `default-agent` → 通道 → 新增飞书 → 在线连接 → 编辑并保留现有密钥。
- 凭据：从 worktree 隔离配置直接注入浏览器；命令输出、报告和 HTTP response 均不记录 App Secret。
- Gateway credential key：`channel-credentials-v1.pem` 权限 `0600`。

## 原型锚点对账

| 锚点 | 真入口观察 | 截图 | 结果 |
|---|---|---|---|
| `#channels-empty` | 显示“外部通道”“还没有外部通道”和两个添加入口；DOM 不含 `Web IM` | `output/playwright/channels-empty.png` | PASS |
| `#add-feishu` | 向导仅显示简短准备说明和指定开放平台链接；空提交同时显示 App ID / App Secret required；新增后 picker 的飞书显示“已添加”且 disabled；编辑默认勾选 keep，DOM 不含 secret textbox，keep/replace 均显式 | `add-feishu-required.png`、`add-feishu-already-added.png`、`edit-feishu-keep-replace.png` | PASS |
| `#channel-connecting` | POST 201 后卡片显示“正在连接”“配置与凭据已安全保存”；同时已有 Gateway observed status 时间，证明不是注入静态 DOM | `output/playwright/channel-connecting.png` | PASS |
| `#channel-connected` | 同一页面自动轮询为“已连接”“运行状态已同步 · 当前配置已应用”并显示最近状态时间；DOM 不含 revision/版本号 | `output/playwright/channel-connected.png` | PASS |

指定飞书链接：`https://open.feishu.cn/page/launcher?from=backend_oneclick`。

## 网络与运行时证据

- 浏览器 console：`0 errors / 0 warnings`。
- 新增：`POST /im/v1/agents/default-agent/channels → 201 Created`。
- 编辑 keep：`PATCH /im/v1/agents/default-agent/channels/<channel_id> → 200 OK`；编辑表单没有读取或提交明文回显值。
- 轮询：两次 mutation 后均由 `GET /im/v1/agents/default-agent/channels → 200 OK` 收敛到 connected。
- SQLite 最终投影：`provider=feishu, channel_revision=2, manifest=2, applied_manifest=2, connection_state=connected, status_sequence=3`。
- 第一次连接后的 worker PID 为 `84409`；keep 编辑触发 stop-old/start-new 后 worker PID 为 `91135`，Gateway 下只保留 `1` 个 `spawn_main` Feishu worker 子进程。
- 浏览器截图中的 App ID 列表卡片始终脱敏；App Secret 不出现在 DOM snapshot、截图或本报告。

## Screenshot SHA-256

```text
0e1b0589eb14c637952b3d05e4590ff78d86ea0ee4fea17fa8bdda84b2c02c0c  add-feishu-already-added.png
4221f74d1e3fb80515a31cc54ed84142a1c5c93c30c0f66b42da5c0983320eb9  add-feishu-required.png
a82c6242f76a3a7ca655f26273ec49e10b073558c3a2cd21c22e4997c182371d  channel-connected.png
8f4043dfbec86123cb9b56a45730bf093d61d4391d1c1a1cd74ed1105baa1f8f  channel-connecting.png
de6df599191b22af3d2256803a05e1e69c02745cb907868e668d9115af19083a  channels-empty.png
93d8c777258d33ba0a79f9eb9da6f73df1818edf47a83da8f3b35832acd74bc5  edit-feishu-keep-replace.png
```

## 清理证明

验收结束后已关闭 Playwright session，并由 `scripts/e2e-down.sh` 按 Gateway → IM 顺序停止服务。最终检查结果：ephemeral IM 监听端口 `0`、Gateway 进程 `0`、其 `spawn_main` worker 子进程 `0`、PID 文件 `0`、`.e2e-ports.env/.e2e-jwt-secret/.gateway-config.yaml` `0`。
