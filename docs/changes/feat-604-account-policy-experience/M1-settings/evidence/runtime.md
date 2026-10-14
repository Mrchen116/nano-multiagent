# 隔离真实产品验收环境

- Worktree：`/Users/czj/.codex/worktrees/unit-feat-604/nano-multiagent`，branch `codex/feat-604-account-policy-experience`。
- 地址：`http://127.0.0.1:19765/settings/account` 与 `/settings/policies`。
- 当前使用此 worktree 的 `apps/im-server/lib/main.js` 与本次 `npm run build` 生成的 `src/IM/frontend/dist`；IM 直接提供真实静态前端，故不另起 Vite。Gateway/DSH/LLM 未启动。
- 运行数据均在 `/tmp/nano-feat604/`：隔离数据库 `im.sqlite3`、随机 secret 文件 `secret`、测试用户定位 `users.json`。这些不是仓库内容，不提交。
- 本地专用身份：管理员 `admin604`，普通有效团队成员 `member604`，个人未加入 `private604`，个人待批准 `pending604`，个人团队资格停用 `suspended604`；统一测试密码 `nano604test`。不适用于任何生产服务。普通成员模拟旧公司账号，无个人空间；其余测试身份保留个人空间。
- 五个用户用真实 identity 注册逻辑创建，团队资格仅在此临时 DB 配置。电脑摘要有一台测试电脑。容量由此临时 DB 的 `attachment_storage` 样本记录产生：管理员 680MiB、普通成员 1GiB；不声称实际上传了这些体积的文件。管理员可读取两名可见账号。
- 启动：worktree cwd 执行 `IM_JWT_SECRET="$(cat /tmp/nano-feat604/secret)" IM_PUBLIC_URL=http://127.0.0.1:19765 node apps/im-server/lib/main.js serve --db /tmp/nano-feat604/im.sqlite3 --port 19765`。
- 健康：`curl -fsS http://127.0.0.1:19765/health`；进程：`lsof -nP -iTCP:19765 -sTCP:LISTEN`，核实 cwd 为本 worktree 后操作。
- 停止：仅对本次 IM 终端 Ctrl-C 或其已核实 PID 发 SIGTERM。产品 reviewer 可按 runbook 在该临时 DB 改角色/容量或停启此 IM 来实际触发故障，但不能改受审产品文件、测试或生产。
- 浏览器：Cua，实际桌面与 390×844、320×740 viewport；无需 iframe 替代真实响应式。原型服务 `127.0.0.1:19764` 仅用于设计对照，由主 Agent 保持，完成后清理。
