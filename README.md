# nano-multiagent

在自己的机器上运行多个长期个人助手，通过 Web IM、原生 iPhone App 或飞书与它们协作。每个 Agent 有独立身份、workspace、能力与配置，可按单聊天或跨聊天的 global 模式工作。

执行运行时使用未修改、锁定版本的 DeepSeek Harness（DSH）；Nano 负责产品身份、消息交付、权限规则、任务图与主动工作策略。旧 Python Kernel 和 Coding CLI 已退役。

## 使用已有的 IM 服务

打开已部署的 IM 地址并注册，即可进入自己的私人空间；加入团队另从账号入口申请，批准后私人助手和历史仍保持私有。

1. 首次设置页提供可交给本机 Agent 的安装说明，也提供一条手动终端命令。
2. 执行安装并在网页确认电脑绑定。页面随后引导连接已有本机代理、登录 Codex 或填写 API，真实测试成功后继续。
3. 选择助手用途、名称与目标，创建后发送可编辑的起步任务。以后可从账号入口重新打开设置，电脑离线时重跑同一安装命令恢复。

普通用户不需要克隆仓库或手写配置。安装与恢复细节见 [Gateway 操作](docs/operations/gateway.md)。

## 自行部署 IM

需要 Node.js 24（或满足 package.json 的版本）和 pnpm 11.7.0。在仓库根目录安装并构建：

```bash
pnpm install --frozen-lockfile
pnpm build
npm --prefix src/IM/frontend ci
npm --prefix src/IM/frontend run build
```

先准备固定的 `IM_JWT_SECRET` 与 IM 数据目录，再初始化首个管理员并启动 IM。已有数据库不重复初始化：

```bash
pnpm im init-admin --username root --password '<strong-password>' --display-name Root
pnpm im serve --host 127.0.0.1 --port 8011
```

默认数据库为 `data/im_service.sqlite3`；生产必须使用持久密钥及明确的数据路径。完整设置见 [本地启动](docs/operations/local-stack.md)。

将含 `node`、`agents`、`im_service` 和 `llm` 的配置保存为 `~/.nanoassistant/config.yaml`，具体字段与模型目录见 [Gateway 配置](docs/operations/gateway.md)，然后启动：

```bash
pnpm pa start --config ~/.nanoassistant/config.yaml
```

首次使用按终端给出的页面完成设备绑定；已绑定节点启动 DSH 并连接 IM。打开 `http://127.0.0.1:8011/`，登录后从在线 Agent 开始聊天。节点页显示连接状态，真实消息往返确认服务可用。

```bash
pnpm pa status --config ~/.nanoassistant/config.yaml
pnpm pa restart --config ~/.nanoassistant/config.yaml
pnpm pa stop --config ~/.nanoassistant/config.yaml
```

macOS 默认使用当前用户的 LaunchAgent；临时环境可在配置中设置 `gateway.autostart: false`。同一配置只管理一个节点进程及其 DSH 子进程，停止与重启始终传同一配置路径。

## 客户端与维护入口

- [Web IM 开发](src/IM/frontend/README.md)；`dist/` 是本地构建产物，不提交。
- [原生 iPhone 客户端](src/IM/ios/README.md)：构建、个人签名和后台边界；[行为契约](docs/specs/im/ios-client.md)。
- [Gateway 与飞书](docs/operations/gateway.md)、[Auto 权限](docs/operations/auto-permissions.md)、[故障排查](docs/operations/troubleshooting.md)。
- [旧环境切换](docs/operations/dsh-migration.md)：保留非聊天资产，从新会话开始。生产部署需独立授权。
- [架构](SPEC.md)、[文档地图](docs/README.md)、[开发环境](docs/development/local-development.md)、[隔离验收](docs/development/worktree-runtime.md)。
