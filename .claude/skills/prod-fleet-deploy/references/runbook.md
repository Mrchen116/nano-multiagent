# 生产舰队部署（公网 IM + 双 Gateway）

当前域名、节点地址、进程管理与通道归属只在 [生产舰队](../../../../docs/operations/prod-fleet.md) 维护。先读该文档；本操作单负责如何更新与验证。官网由 Mini 同一套生产 IM 提供，不是另一个需要上传的站点。

## 部署前

1. 确认用户授权范围、目标 `origin/main` 精确 SHA、CI、两机 checkout/status 和 live PID/cwd。Mini 主仓只安全 fast-forward；MacBook Air 主仓只 fetch，保留全部无关 dirty/untracked。
2. 记录现有 IM/Tunnel/Gateway 的 LaunchAgent、launcher、数据库及附件绝对路径、节点 ID、owner、凭据文件位置和通道归属；不输出密钥/token。不要从历史部署记录猜当前 PID，也不按端口批量 kill。
3. 常规更新复用持久 JWT signing key、公司准入、Gateway 私钥及节点运行凭据；缺失或身份不匹配先查原因。不要例行 `initialize_company`、重新 bind、重新批准成员、创建新 Tunnel 或迁移飞书。
4. 涉及数据库迁移或运行配置修改时先备份。SQLite 使用 backup API，或正常停写后复制完整快照；不要只复制仍在写入的主库。数据库旁 `message-images/`、旧 uploads、配置及密钥一并备份到权限受限目录，不入 Git。
5. 若本次首次从 Python Gateway 切到 DSH，先按 [DSH 迁移](../../../../docs/operations/dsh-migration.md) 完成每节点最终快照、未决外发核对和资产切换；普通版本重启不能绕过该步骤。
6. 若仍使用旧 PA 目录，先执行 [无覆盖迁移](../../../../docs/operations/pa-workspace-layout-migration.md)。完成迁移后不重复执行。

MacBook Air Gateway 用目标 `prod-main-<short-sha>` detached worktree，各自安装锁定的 Node/pnpm 依赖并构建。新版本健康后才回收干净且无进程使用的旧 `prod-main-*`；不 force、不动其他 worktree。

## 更新 Mini 代码和前端

以下是按需执行的命令，不是整段盲跑脚本。首先确认 Mini 当前分支为 main、已跟踪改动不会被覆盖，并确认远端目标 SHA 是本次授权版本。

```bash
ssh mini 'cd ~/Repos/nano-multiagent && git status -sb && git fetch origin && git rev-parse origin/main'
# 核对目标后，只快进到已确认的 SHA，避免部署期间 main 又前进而漂移。
# 在 Mini 执行：git merge --ff-only <已确认目标SHA>
ssh mini 'zsh -lc "cd ~/Repos/nano-multiagent && pnpm install --frozen-lockfile && pnpm build && npm --prefix src/IM/frontend ci && npm --prefix src/IM/frontend run build"'
```

前端或其依赖变更必须重建 `src/IM/frontend/dist`，它是未入仓的产物。记录本次 build 的资源文件名，随后确认官网 HTML 引用这些资源且请求成功；仅 pull 不等于官网前端更新。

## IM 与 Tunnel 的受管启动

使用 [生产舰队](../../../../docs/operations/prod-fleet.md#源站与隧道) 中的现有 LaunchAgent。部署前读取实际 plist/launcher 并核对：

- IM launcher 从 Mini 目标主仓启动 `node apps/im-server/lib/main.js public-server`，保持 `IM_PUBLIC_URL` 为官网 HTTPS origin、`WEB_CONCURRENCY=1`，`IM_DB_PATH`/`IM_UPLOAD_DIR` 指向原生产数据。
- 从 `~/.nanoassistant/im-jwt-secret` 读取非空持久密钥；不打印值，不临时生成。public-server 设置公网模式、loopback 监听、可信 loopback tunnel 及请求边界；不得绕过它直接裸起 uvicorn。
- Tunnel ingress 只将官网主机映射到 Mini loopback 源站，最后兜底 `http_status:404`；保留 Tunnel 身份、凭据、DNS 和边缘 HTTPS 规则。

```bash
# Mini：只读核对服务定义和运行状态；缺失时先定位，不另起临时进程替代。
ssh mini 'launchctl print "gui/$(id -u)/io.github.mrchen116.nano-multiagent.public-im"'
ssh mini 'launchctl print "gui/$(id -u)/io.github.mrchen116.nano-multiagent.public-tunnel"'
ssh mini 'test -s ~/.nanoassistant/im-jwt-secret && test -x ~/.nanoassistant/bin/run-public-im.sh'
ssh mini '/opt/homebrew/bin/cloudflared tunnel --config ~/.cloudflared/nano-im-public.yml ingress validate'

# 前置检查、必要备份与构建完成后，重启已加载的 IM 服务。
ssh mini 'launchctl kickstart -k "gui/$(id -u)/io.github.mrchen116.nano-multiagent.public-im"'
```

普通代码发布不必重启 Tunnel。若它未加载或配置确需更新，先校验原 plist 和 ingress，再在已有配置上使用 `launchctl bootstrap` / `kickstart`；不要重建 DNS/Tunnel。KeepAlive 服务不能只 kill PID，否则 launchd 会重新拉起；需要保持停写时先 bootout 对应服务，恢复时 bootstrap 原 plist。停公网维护时先停 Tunnel，恢复时先验证 loopback IM，再启动 Tunnel。

不要把 loopback 源站改成 HTTPS 来解决公网 HTTPS；TLS 在 Cloudflare 边缘终止，Tunnel 到Mini loopback 源站仍用 HTTP。公网重定向由 Cloudflare 规则负责；常规代码发布应验证它仍有效。

## Gateway 与代理

顺序：IM 健康 → 需要更新的 LLM 代理 → 受影响 Gateway。两机各用自己的 `~/.nanoassistant/config.yaml`，Gateway CLI 裸跑是 start，显式子命令是 `stop` / `restart`。

- 修改 Gateway config 必须先 stop，避免运行态回写覆盖；稳定环境写入 `gateway.environment`。保留节点身份、设备密钥、已绑定的机器运行凭据；不把人类账号密码写回 config 作为常规恢复方式。
- Mini Gateway 的 IM URL 是 Mini loopback；MacBook Air Gateway 使用官网 HTTPS URL，具体值见拓扑文档。人类登录 token 与 Gateway 运行凭据不可互换。
- 代理仅在本次授权范围需要时更新或重启。先核对实际 base_url、监听、进程 cwd/PID 与管理方式；不要根据旧端口示例杀服务，也不要为符合旧文档擅改可用配置。SearXNG 稳定地址继续写各机 config。
- `ssh mini 'zsh -lc "…"'` 可取得 npm/docker 的 login PATH；Node 使用已经核实的绝对可执行路径，两个目标 checkout 都先安装锁定依赖并构建。

```bash
# Mini Gateway
ssh mini 'cd ~/Repos/nano-multiagent && pnpm pa restart --config ~/.nanoassistant/config.yaml'

# MacBook Air：仅 fetch；将 target 固定为本次已确认、与 Mini 相同的 SHA。
cd ~/Repos/nano-multiagent
git fetch origin
repo_root=$PWD
# target=<已确认目标SHA>
: "${target:?set the reviewed deployment SHA}"
short=$(git rev-parse --short "$target")
prod_worktree="$repo_root/.worktrees/prod-main-$short"
if [[ -e "$prod_worktree" ]]; then
  [[ $(git -C "$prod_worktree" rev-parse HEAD) == "$target" ]] || exit 1
else
  git worktree add --detach "$prod_worktree" "$target"
fi
git -C "$prod_worktree" status --short
# 若有未预期修改，先核实；不得覆盖。
if lsof -tiTCP:8011 -sTCP:LISTEN; then
  print -u2 -r -- "ABORT: local IM listener exists; identify its owner"
  exit 1
fi
cd "$prod_worktree"
pnpm install --frozen-lockfile
pnpm build
pnpm pa restart --config ~/.nanoassistant/config.yaml
```

新 Gateway 健康后核对两机 LaunchAgent label（用 `apps/node/lib/lifecycle.js` 的 `gatewayLabel(config绝对路径)` 计算）、plist 工作目录、`.gateway-state.json` 的 PID/process birth、live cwd、DSH ready/runtime_pid 与目标 SHA。旧 production worktree 逐路径检查无 dirty/untracked、无 live cwd 引用后才 `git worktree remove`，最后 `git worktree prune`。

## 部署完成验收

必须从官网验证，不能只用源站 200 或节点绿灯代替：

1. Mini IM 监听地址为 loopback `127.0.0.1:8011`；MacBook Air 没有 IM `:8011`。IM/Tunnel LaunchAgent 已加载，live PID、cwd、启动参数与目标 checkout 一致。
2. 官网 HTTPS 首页返回 200，TLS 验证开启；不使用 `curl -k`。HTTP 首页、带 query 的路径及假凭据登录 POST 返回到同主机 HTTPS 的 308，路径/query 保留。HTTP POST 不应返回应用登录结果。
3. 官网实际静态资源属于本次 build；从真实浏览器检查本次变更相关页面和行为。使用现有真实账号验证登录、历史数据和实时连接；相关附件/聊天功能变更按授权范围做真实验收，保留脱敏证据。不得拿测试账号、测试数据库或隔离端口充当生产。
4. 经官网认证读取 `/im/v1/me`、`/im/v1/nodes`：两生产节点均 online、心跳新鲜，owner 与 config 中真人 UUID 对齐。取人类有效会话用于这些 API，不使用机器凭据冒充用户；不打印 token，不在命令历史中拼接真实密码。
5. 两 Gateway 的 LaunchAgent、live process、state 都指向目标版本，日志无持续认证/owner/重连错误。受影响代理和既有外部通道健康；本地 200 但官网/Tunnel 失败，不能报告部署成功。
6. 保留数据、附件、签名密钥、设备身份、成员准入；发现漂移先核实，普通更新不隐含迁移授权。验证完成后再清理旧生产 worktree。

无凭据公网检查示例（只读，不跟随重定向，以便看到真实状态）：

```bash
curl --noproxy '*' --max-time 15 -sS -o /dev/null -w '%{http_code}\n' https://im.nanoim.win/
curl --noproxy '*' --max-time 15 -sS -D - -o /dev/null 'http://im.nanoim.win/login?deploy_check=1'
curl --noproxy '*' --max-time 15 -sS -D - -o /dev/null \
  -H 'Content-Type: application/json' \
  --data '{"username":"deploy_https_probe_nonexistent","password":"FAKE_NOT_A_REAL_PASSWORD"}' \
  http://im.nanoim.win/im/v1/auth/login
```

如果官网规则失败，上述 POST 可能触发一次假账号认证；绝不发送真实凭据测试明文入口。

## 局部动作

| 用户意图 | 动作与完成条件 |
|---|---|
| 只重启 IM | 复用 public-im LaunchAgent，验证 loopback、官网与双节点重连；无需例行重新 bind |
| 只重建前端 | Mini 构建 dist，从官网核对资源和实际页面；通常无需重启 IM |
| 只更新某一 Gateway | 只操作目标机，验证目标 SHA、LaunchAgent/state、官网中的该节点在线及受影响入口 |
| 只更新 LLM 代理 | 核实该机真实管理方式与 base_url，保留配置；验证健康及受影响 Gateway 调用 |
| 改 Gateway config | stop → 编辑 → start/restart；节点身份/owner/设备密钥与通道归属保持 |
| 修改公网路由/HTTPS | 核对现有账号、hostname、源站及规则，限定授权范围；验证公网 HTTP/HTTPS 与 WS |

## 恢复与故障定位

- 官网失败、loopback 正常：检查 Tunnel LaunchAgent、ingress、DNS/边缘规则及 `public-tunnel.log`，不要改回 Tailscale HTTP 当作恢复官网。
- 两端都失败：核对 `public-im.log`、launcher 的环境和路径、持久密钥、目标代码和依赖，不退回旧裸 uvicorn 命令。
- 官网旧前端：核对 Mini dist 是否重建、官网 HTML 的资源名和浏览器缓存；不能只看 Git SHA。
- Gateway 不在线：检查配置 URL、设备运行凭据、active owner、Gateway state/live process 及新日志。不要为了恢复在线自动换设备密钥或重新 bind。
- 换 signing key、成员重新初始化、设备交接、数据库回滚均不是常规重启。需要这些动作时按本次授权及对应恢复契约执行；回滚到不具备公网保护的旧版本时保持 Tunnel 关闭。
- 数据恢复必须使用一致快照，历史 token/设备凭据失效与重新登记按恢复契约处理，不能把备份凭据直接复活。

日志位置与源站/Tunnel 服务名见 [生产舰队](../../../../docs/operations/prod-fleet.md#源站与隧道)。开发主链路见 [local-stack](../../../../docs/operations/local-stack.md)，隔离测试见 [worktree runtime](../../../../docs/development/worktree-runtime.md)。
