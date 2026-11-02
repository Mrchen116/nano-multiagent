# Local Stack

本机开发运行 TypeScript IM + Node + DSH，生产拓扑另见 [fleet](prod-fleet.md)。临时验证用 [worktree 隔离脚本](../development/worktree-runtime.md)，不要占生产 `8011` 或复用生产数据。

## 准备

先按 [开发环境](../development/local-development.md) 安装并构建后端与 Web。配置 `~/.nanoassistant/config.yaml`，字段见 [Gateway](gateway.md)。

为本地 IM 准备持久、私有 JWT secret，并在同一启动环境设置 `IM_JWT_SECRET`。已有数据库重启不能更换此密钥。可设置 `IM_DB_PATH`、`IM_UPLOAD_DIR`、`IM_FRONTEND_DIST_DIR` 为明确的绝对路径；默认分别为 `data/im_service.sqlite3`、`data/uploads` 与仓内 `src/IM/frontend/dist`。

## 发布首次安装包

`pnpm build` 生成本地候选 `dist/node-release/manifest.candidate.json` 与 `nano-node.tgz`，不会发布 GitHub Release，也不会生成可部署的 `manifest.json`。不要把候选清单改名后用于正式安装入口。

只有用户明确要求“发包/发布安装包/创建 Release”时才执行以下步骤；合并、构建、部署、重启或“更新到最新代码”均不隐含发包授权。普通部署保留当前已验证的 `manifest.json`，不因服务源码 SHA 改变而更换安装版本。切换 checkout 时将现有清单带到新的 `IM_NODE_RELEASE_DIR`；缺失时保留“未发布”状态，不能为补齐清单自行发包。若服务变更与已发布安装包存在已确认的不兼容，报告差异并请求用户决定，不能自动发布。

选择已通过 CI 的完整源码 SHA，在 [Publish Node installer](../../.github/workflows/node-release.yml) 工作流中显式填写 `commit` 与 `version`。版本采用 `X.Y.Z`（例如 `0.2.0`，不含 `v` 前缀）；版本未确定时先确认，不用 SHA 代替、不自动递增。工作流构建并测试固定源码，再发布标题 `Nano Node vX.Y.Z`、tag `vX.Y.Z` 及资产 `nano-node.tgz`。源码 SHA 保留在 Release 说明和清单的 `source_commit`，清单 `version` 为版本号。同一版本不能覆盖；现有 `node-<SHA>` Release 不改名、不删除，仍可由旧清单安装。

发布后工作流匿名下载并校验实际包体，成功才生成 `manifest.json`，保存到本次运行的 `node-manifest-X.Y.Z` artifact。

明确发布并选择该版本作为安装入口后，从成功运行下载原始 `manifest.json`，备份当前清单并原子替换到 IM 的 `IM_NODE_RELEASE_DIR`；未配置该变量时默认使用 IM checkout 的 `dist/node-release`。核对版本号、源码 SHA、固定下载地址和 SHA-256。IM 只需这份清单，包体留在 GitHub。普通服务更新或回退继续保留所选安装版本，不自动切换清单。

IM 提供 `/install.sh` 与 `/install/manifest.json`，旧 `/install/nano-node.tgz` 仅重定向到清单中的固定 GitHub 地址。清单缺失或无效时返回未发布状态，不提供失效安装命令。正式开放安装前，还需从公网入口完成匿名下载、真实首次安装、绑定和助手回复；本地候选包或下载 fixture 不能替代这项验收。

`IM_PUBLIC_URL` 必须是用户实际访问的 IM origin，安装材料从该地址生成；不要用请求 Host 代替部署配置。更新 IM 时按变更重建 Web 产物；Node 安装包按上面的独立授权流程发布。首次使用者可直接在网页注册、绑定空节点和配置模型；下文手工 config 启动仍用于开发与运维。

### GitHub 发行说明格式

每版 Release 的正文使用以下三个二级标题，按表中顺序排列。发布者为前两节提供 Markdown 正文，标题和最后一节由[发布脚本](../../scripts/publish-node-release.mjs)生成。

| 标题 | 内容 | 来源 |
|---|---|---|
| 本版变化 | 以上一正式版为基线，分条写用户现在能做什么、哪些问题已修复。涉及配套 IM 或 Web 时标明范围，可附 PR 或完整差异链接。 | 工作流输入 `changes` |
| 升级说明 | 写清受影响的用户、升级顺序、兼容性和必要的迁移操作，复杂步骤链接到该版本的操作文档。无特殊要求时填写“无需额外操作”。 | 工作流输入 `upgrade_notes` |
| 安装包与校验 | 固定版本的安装包下载链接、完整源码提交链接和该包的 SHA-256。 | 当前构建候选 |

## 启动

空库仅执行一次管理员初始化，再启动 IM：

```bash
pnpm im init-admin --username root --password '<strong-password>' --display-name Root
pnpm im serve --host 127.0.0.1 --port 8011
```

保持该 IM 终端运行。`curl -fsS http://127.0.0.1:8011/health` 验证监听；浏览器打开 `http://127.0.0.1:8011/` 登录。

另一个终端启动节点：

```bash
pnpm pa start --config ~/.nanoassistant/config.yaml
```

首次启动通过终端显示的设备绑定页面，以目标 owner 登录并完成确认。`--auto-bind` 只用于配置了测试登录身份的隔离自动化。已有绑定不会重复创建所有者身份。

`Gateway started` 表示 DSH 已完成初始化和持久恢复，IM 与飞书连接仍需分别观察。在节点页面确认 online，再向目标 Agent 发消息，确认真实回复出现在同一聊天。

```text
Web/iOS → IM HTTP/WS → Node 产品路由 → stdio DSH → 产品交付 → 原聊天
```

## 停止和恢复

```bash
pnpm pa status --config ~/.nanoassistant/config.yaml
pnpm pa stop --config ~/.nanoassistant/config.yaml
```

先停节点，让 DSH 排空和刷盘，再在 IM 终端按 Ctrl-C。macOS 登录自启、PID/birth 身份校验、降级处理与恢复见 [Gateway 操作](gateway.md)；消息不通按 [排障顺序](troubleshooting.md) 保存首个错误。
