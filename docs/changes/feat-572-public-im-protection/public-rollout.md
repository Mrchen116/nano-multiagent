# 公网发布与恢复操作单（待上线授权）

本操作单是 feat-572 的发布候选；当前未部署 `im.nanoim.win`。完成独立审查及用户当次上线授权后，在 Mini 源站执行。生产拓扑仍以 [prod-fleet](../../operations/prod-fleet.md) 为准，Gateway 不暴露公网端口。

## 先准备数据与准入

1. 记录当前 commit、IM 进程 cwd/PID、数据库、数据库旁 `message-images/` 私有附件目录及旧 uploads 绝对路径；暂停隧道并停止 IM，保持原目录可恢复。
2. 将 SQLite 文件、完整 `message-images/` 与旧 uploads 目录作为同一次停写快照备份；若存在 WAL，使用 SQLite backup API 或正常关闭后 checkpoint，不只复制仍在写入的主库。备份连同运行配置、JWT secret 和隧道凭据放在访问受限目录，不能入 Git。
3. 新代码首次启动会迁移表结构。历史真人默认 pending；只选择确认的真人 ID 执行 `PYTHONPATH=src python -m IM.cli initialize_company --db-path "$IM_DB_PATH" --admin-id <真人ID> --active-id <另一个真人ID>`。只选管理员时省略 active-id；同一完整清单重跑幂等，另一清单拒绝。不要凭用户名、Gateway 存在或历史 owner 推断准入。
4. 已有 Gateway 需要在各自本机执行 `python -m personal_assistant.main --config <实际配置> bind`，用有效成员接受网页链接，再在本机明确确认。私钥保持本机，交接会保留节点/Agent ID；运行凭据取代账号密码。中断时沿用本机操作文件恢复，不能生成新私钥覆盖既有身份。

## 源站与免费隧道

使用已获授权的 Cloudflare 账号创建 named tunnel，仅映射 `im.nanoim.win` 到 `http://127.0.0.1:8011`，最后一条 ingress 必须是 `service: http_status:404`。DNS 仅创建该 hostname 对应的 tunnel CNAME。发布时核实账号页面所选功能无付费项、无 Cloudflare Access 登录要求，不开启其他 hostname 或远程管理入口。禁止用临时隧道/hosts 记录充当正式域名验证。

源站启动环境：`IM_PUBLIC_URL=https://im.nanoim.win`、`IM_PORT=8011`、持久 `IM_DB_PATH`、`IM_UPLOAD_DIR`、至少 32 字符的随机 `IM_JWT_SECRET`、`WEB_CONCURRENCY=1`。从受审 checkout 执行 `PYTHONPATH=src python -m IM.cli.public_server`；静态前端提前构建。launcher 只监听 loopback，关闭 HTTP access log，脱敏 WS 日志 ticket/token，关闭 Uvicorn 自动信任代理头，只信任本机 tunnel 的 CF-Connecting-IP。不要设置任意 IM_BROWSER_ORIGINS；本地开发跨端口时只增加实际开发 origin。

先 `cloudflared tunnel ingress validate` 并核对 hostname 的匹配规则；再启动 tunnel。检查 `lsof` 的监听地址、进程 cwd/commit、已批准成员和 owner 对齐的在线节点。最后从本机浏览器经真实 HTTPS 域名验证登录、聊天、附件、Work、任务与实时连接；断开 Tailscale 后复验。保留脱敏截图及 HTTP/WS 状态，不能把 merge、HTTP 200 或绿灯当成完整发布成功。

## 回退和旧凭据失效

先停 tunnel、IM 与需要重新登记的机器连接。将同一快照中的数据库、数据库旁 `message-images/` 与旧 uploads 一起恢复到候选副本；确认 SQLite integrity_check、附件文件/元数据对应后切换。回滚到旧代码时继续保持公网关闭，旧版本没有公司保护，不得恢复公网入口。

恢复到本版本后、重新开放前，在停止写入的数据库事务中执行：

```sql
BEGIN IMMEDIATE;
UPDATE users SET auth_epoch=auth_epoch+1 WHERE password_hash IS NOT NULL;
UPDATE auth_sessions SET revoked=1;
DELETE FROM auth_ws_tickets;
UPDATE node_binding_state SET node_epoch=node_epoch+1, runtime_token_hash=NULL;
DELETE FROM node_binding_operations;
COMMIT;
```

重新生成 JWT secret；全体用户重新登录，Gateway 在各自本机重新证明登记，不能恢复旧 token。先在 loopback 验证恢复前 access/refresh/ticket/runtime 均被拒绝、历史聊天任务及附件可读，再开 tunnel。成员清单和管理员角色来自恢复快照，需再次核对，不自动重新批准停用成员。

## 容量处理

管理员从策略页查看账号与服务的已用/预留容量；普通成员保留文字发送能力。容量满不自动删除历史附件或放宽上限。上传临时文件/预留在启动时对账，删除聊天后仅回收不再被引用的文件。维护时备份后按业务确认处理历史内容，避免绕开引用和配额元数据直接删文件。
