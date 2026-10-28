# Mini 同 SHA 生产路径迁移

适用：Mini 当前 IM/Gateway 从 `~/Repos/nano-multiagent` 运行，IM DB/upload 位于其中，Tunnel Python 也来自主仓。目标为固定 `~/.nanoassistant/prod-main/nano-multiagent`、`~/.nanoassistant/im-data/`、`~/.nanoassistant/runtime/tunnel-venv/`。本次用户已同意分离 Mini 生产目录；从 Air 执行，保持现场已部署 SHA，不顺带部署新 main。

## 执行前提

1. 设计门禁通过，本机路径保护与隔离副本测试完成。只读确认 live PID/cwd、CLI、数据库实际路径和当前 SHA。固定 SHA 如与本 unit 记录不同，以真实 live 版本核查差异后记录，不猜测。
2. 盘点现有 launcher/plist 的所有开发主仓引用，区分生产 runtime 与 Agent 用户 workspace。后者保留。目标不存在或有本次有效记录；若来源/内容不明停止，不覆盖。
3. 在权限 0700 的本地迁移记录目录保存原 launcher/plist/config（含秘密不输出）、SHA、依赖版本、服务状态和数据清单。检查磁盘足够容纳新构建、数据库/附件与回退快照。
4. 以当前生产 SHA 新建 detached worktree，自行安装锁定依赖、构建 backend/frontend；不复用可被开发覆盖的构建产物。固定 Node 不变。独立 venv 安装现有 Tunnel 依赖的准确版本；运行 `prod-tunnel.py --ready` 验证。
5. 在临时目录用 SQLite/附件样本演练一致复制、已经完成识别、不覆盖未知目标、失败回退；演练命令和结果写 unit evidence。生产不重跑失败/幂等演练。

## 切换

1. 确认无正在进行的生产 Agent 执行后，停止 Mini Gateway，再卸载原 IM LaunchAgent，确认 IM 已停写。繁忙则等待正常空闲，不强杀业务。
2. 停写状态用 SQLite backup API 复制 DB，复制旁 `message-images` 和 uploads（保留权限/元数据），保留原数据。核对 integrity_check、每表行数、关键身份计数与附件文件清单/哈希一致。signing key、config、设备凭据、DSH state 和 workspace 保持原位置，若其中有开发主仓绝对引用逐一核对用途。
3. 更新既有 IM launcher 和 plist 的 cwd、DB/upload 引用；固定 Node、公网 URL、签名密钥、代理、端口和已有安装包目录均保持。静态资源来自新生产 checkout。把已发布安装目录复制到 `~/.nanoassistant/node-release/` 并显式设置 `IM_NODE_RELEASE_DIR`；与迁移前 manifest 和包文件 SHA256 一致，不使用新 build 生成的候选清单。以原 label 重新 `launchctl bootstrap gui/<uid> <原IM plist>`；确认其 PID/cwd 和 `http://127.0.0.1:8011/health` 返回 200，再进入 Gateway 步骤。启动或健康失败则停止切换，按下文恢复原 IM，不带病继续。
4. 从新 checkout 用固定 Node 启动 Mini Gateway，令原配置对应的 LaunchAgent 重新生成新 CLI/cwd；不 bind、不换 owner、不换 node id。
5. Tunnel 仅改 plist Python 指向独立 venv，原 supervisor 脚本哈希、配置、cloudflared、协议和路由不变；短暂重启同一个受管服务以应用解释器路径。本次属于恢复机制运行依赖变更，完成后执行 600 秒只读 gate（采用后台运行并间隔读取输出），不做故障注入。
6. 在生产 checkout/数据根放 `.nano-production` 标记，checkout 标记加入本地 Git exclude；更新两机 dev-host protected_paths。新路径健康前保留原生产数据，禁止在原主仓启动 E2E。

## 完成与恢复

- 必须核对实际 IM/Gateway/DSH CLI、cwd、Node executable、Tunnel Python 路径均离开开发主仓；允许保留用户原 workspace 路径。两个 node online、owner 一致、通道已有连接健康、HTTPS/API/静态资源与既有安装资产可读；Air 无 IM :8011。
- 数据切换前完整性比对，切换后有限核对身份计数与数据路径、附件样本。只读观察既有数据，不发送消息或创建任务。600 秒 Tunnel gate 零失败才完成。
- 同一迁移已有成功记录且 live 路径/版本/数据一致时跳过，不能重新把旧 DB 覆盖新 DB。中途状态由实际路径与停写状态判断，未确认当前写入目标前不继续复制。
- 新服务接受写入前失败：停止新服务，恢复原配置/launcher/plist 与原数据路径，原 checkout 同 SHA 启动；若新路径已接受写入，先停写并备份新数据，再把最新一致 DB/附件恢复到原路径后启动，绝不退回过期快照丢失消息。
- 迁移健康后将旧主仓生产 data 移入受保护回退目录（不留开发可误删的生产原件），不删除不明用户文件。回退备份与记录遵循现有保留策略，单独注明本次迁移前快照；不复制备份目录自身。保留固定 prod-main。
- 结果记录实际 SHA、路径、备份、切换时间、数据核对及观察范围，秘密保留本机；production skill/runbook/prod-fleet 的 current 路径说明在本次交付同步。
