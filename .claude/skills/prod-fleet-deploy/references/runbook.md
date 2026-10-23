# 生产舰队部署（公网 IM + 双 Gateway）

当前域名、节点地址、进程管理与通道归属只在 [生产舰队](../../../../docs/operations/prod-fleet.md) 维护。先读该文档；本操作单负责如何更新与验证。官网由 Mini 同一套生产 IM 提供，不是另一个需要上传的站点。

## 部署前

安装包是独立发布动作，按 [发布规范](../../../../docs/operations/local-stack.md#发布首次安装包) 判断明确授权和版本号。普通部署先记录并保留现有 `IM_NODE_RELEASE_DIR/manifest.json`；默认目录为 IM checkout 下 `dist/node-release`。切换 checkout 时携带现有已验证清单，不用构建候选替代，不为匹配服务 SHA 新建 Release；部署后核对清单内容未变。

1. 确认用户授权范围、目标 `origin/main` 精确 SHA、CI、两机 checkout/status 和 live PID/cwd。Mini 主仓只安全 fast-forward；MacBook Air 主仓只 fetch，保留全部无关 dirty/untracked。
2. 记录现有 IM/Tunnel/Gateway 的 LaunchAgent、launcher、数据库及附件绝对路径、节点 ID、owner、凭据文件位置和通道归属；不输出密钥/token。不要从历史部署记录猜当前 PID，也不按端口批量 kill。
3. 常规更新复用持久 JWT signing key、公司准入、Gateway 私钥及节点运行凭据；缺失或身份不匹配先查原因。不要例行 `initialize_company`、重新 bind、重新批准成员、创建新 Tunnel 或迁移飞书。
4. 涉及数据库迁移或运行配置修改时先备份。SQLite 使用 backup API，或正常停写后复制完整快照；不要只复制仍在写入的主库。数据库旁 `message-images/`、旧 uploads、配置及密钥一并备份到权限受限目录，不入 Git。
5. 若本次首次从 Python Gateway 切到 DSH，先按 [DSH 迁移](../../../../docs/operations/dsh-migration.md) 完成每节点最终快照、未决外发核对和资产切换；普通版本重启不能绕过该步骤。
6. 若仍使用旧 PA 目录，先执行 [无覆盖迁移](../../../../docs/operations/pa-workspace-layout-migration.md)。完成迁移后不重复执行。

MacBook Air Gateway 长期复用固定 detached `prod-main` worktree，各自安装锁定的 Node/pnpm 依赖并构建。精确 SHA 进入部署记录，不进入目录名；普通更新不再创建或清理生产 worktree。首次迁移后才回收干净且无进程使用的历史目录；不 force、不动其他 worktree。

首次切换须同时完成迁移操作单中的「旧生产数据的额外对账」，尤其是 IM 旧全局主会话、可重放 relay 和工具镜像。停止旧 Python Gateway 时从保留的旧 checkout 使用 `PYTHONPATH=<旧checkout>/src <原venv>/bin/python -m personal_assistant.main stop --config …`；新代码已移除旧模块，不能从新 checkout 调旧入口。新状态安装后只用 Node 生命周期命令。

## 更新 Mini 代码和前端

涉及公网运行服务前，使用 Mini 已安装的 `.venv/bin/python ~/.nanoassistant/bin/prod-tunnel.py --ready` 验证代理 TUN/QUIC 路径；目标版本未跟踪该运维脚本时保留已安装版本，不从未提交的本地文件覆盖生产 supervisor。

以下是按需执行的命令，不是整段盲跑脚本。首先确认 Mini 当前分支为 main、已跟踪改动不会被覆盖，并确认远端目标 SHA 是本次授权版本。

```bash
ssh mini 'cd ~/Repos/nano-multiagent && git status -sb && git fetch origin && git rev-parse origin/main'
# 核对目标后，只快进到已确认的 SHA，避免部署期间 main 又前进而漂移。
# 在 Mini 执行：git merge --ff-only <已确认目标SHA>
ssh mini 'zsh -lc "cd ~/Repos/nano-multiagent && pnpm install --frozen-lockfile && pnpm build && npm --prefix src/IM/frontend ci && npm --prefix src/IM/frontend run build"'
```

前端或其依赖变更必须重建 `src/IM/frontend/dist`，它是未入仓的产物。记录本次 build 的资源文件名，随后确认官网 HTML 引用这些资源且请求成功；仅 pull 不等于官网前端更新。

## Node 运行时升级

版本、安装路径和 Brotli 验证依据只在 [生产舰队](../../../../docs/operations/prod-fleet.md#node-运行时) 维护。运行时升级不隐含源码版本升级、安装包发布或修改其他服务的 Node：

1. 从 Node 官方下载指定平台发行包和 SHA256 清单，校验后安装到两机的固定版本目录；保留旧运行时用于恢复。用新 Node 安装锁定依赖并构建，先完成候选版本验证。
2. 记录并备份两机 config、Gateway plist/state，以及 Mini 的 IM launcher/plist、持久 signing key 和安装清单；涉及数据库时使用一致快照。备份放本机权限受限目录，不输出秘密。
3. 按原 Gateway 的生命周期入口 stop 后，仅在 `gateway.environment.PATH` 前置新 Node 的 `bin`，保留其他配置。Mini 的既有 IM launcher 改用新 Node 绝对路径，并前置同一 PATH；保留原公网参数、数据库、附件和密钥。
4. 按 IM → Gateway 顺序切换。两机均用新 Node 的绝对路径执行各自原 checkout 的 `apps/node/lib/cli.js restart --config …`，让生命周期入口重建自启定义；不要只改 Homebrew 软链接。
5. 核对两机 Gateway plist、state 和 live executable，确认各 DSH 子进程也使用新运行时；核对 IM live executable 与 Brotli 补丁。完成下文公网检查、30 秒 Tunnel 采样及两节点真实模型回复；安装清单和身份保持原值。

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

### 公网代理与 TUN

持久策略与端口以 [生产拓扑](../../../../docs/operations/prod-fleet.md#公网代理出口) 为准。不能用交互 shell 的一次 export 证明自启服务，也不能把 HTTP_PROXY 当作 UDP 已代理。

1. 在权限受限目录备份两机 Clash 的 config.yaml、verge.yaml、profiles/Script.js、生成配置及 Mini supervisor/plist。核对已安装 supervisor 与目标版本差异，不从未知文件覆盖生产。
2. 两机 Clash 全局扩展安装目标版本 scripts/prod_proxy_policy.js，保留订阅及选中节点。持久开启 TUN、Clash 登录自启；重新加载后通过本地控制 socket 核对 enable、实际 utun、规则与 UDP 支持。控制密钥和订阅不导出到报告。
3. 两 Gateway 先 stop 再持久写代理环境，保留身份。Mini IM launcher 同步大小写 HTTP/HTTPS/ALL_PROXY、NO_PROXY 与 NODE_USE_ENV_PROXY。用固定 Node CLI 应用，代理值不复制进 Gateway plist。
4. Tunnel 路径切换先停原受管 Tunnel，安装经过 review 的 scripts/prod_tunnel.py 到既有路径；验证 ingress、loopback IM 与 --ready 后 bootstrap 原 plist。保持 QUIC/IPv6、Tunnel 身份和 HTTPS 规则。
5. 用 lsof 与 Clash /connections 检查 Gateway/DSH/工具实际链路，以及四条 cloudflared UDP 7844 的非 DIRECT 代理链、双向字节和 utun 路由。本机源站、LLM 与 Tailscale 仍直接到原地址。
6. 路径/恢复机制变更须验证代理不可用时 supervisor 暂停 Tunnel，恢复后自动重建四连接；随后 --seconds 600 要求 child PID 与 closed_connections 全程不变。普通服务部署仍采样 30 秒。

正式检查从服务 config 读取代理。Air 从候选/生产 checkout 使用 `.venv/bin/python scripts/prod_tunnel.py --public-only --seconds 30`；Mini 使用已安装脚本的完整检查。--direct-diagnostic 必须与 --public-only 联用，只绕过应用 HTTP 代理，TUN 开启时仍受系统路由接管；物理直连诊断必须另行隔离且不能破坏正式出口。公网 HTTPS 失败、Tunnel readiness 失败和代理链失败分别记录，不一概归因 Cloudflare。

### 固定生产 worktree

固定路径见 [生产舰队](../../../../docs/operations/prod-fleet.md#节点身份)。在 Codex 内首次创建使用 `create_worktree(name="prod-main", ref=目标SHA)` 并核对返回路径；之后复用，不能因 SHA 改变而新建目录。已有同名路径须核对 Git common dir 与用途，不覆盖或改名不明现场。非 Codex 环境可用 `git worktree add --detach <固定路径> <目标SHA>` 首次创建。

首次切换先在新 checkout 执行 `pnpm install --frozen-lockfile` 和 `pnpm build`，再从 live cwd 已核对的、已构建的旧 checkout 执行 `pnpm pa stop --config ~/.nanoassistant/config.yaml`，最后在新目录 restart 并验健康。不要从尚未构建的新目录调用 pa stop。下面的升级示例适用于固定目录已经投入运行的后续部署。

```bash
# Mini Gateway（代码、依赖和构建已经更新到确认版本）
ssh mini 'cd ~/Repos/nano-multiagent && pnpm pa restart --config ~/.nanoassistant/config.yaml'

# MacBook Air：主仓只 fetch；target 是本次已确认、与 Mini 相同的 SHA。
set -e
cd ~/Repos/nano-multiagent
git fetch origin
: "${target:?set the reviewed deployment SHA}"
prod_worktree="$HOME/.codex/worktrees/prod-main/nano-multiagent"
# 首次创建已按上文完成。Git 返回异常、dirty 或非 detached 状态时先核实。
git -C "$prod_worktree" rev-parse --show-toplevel
test -z "$(git -C "$prod_worktree" status --porcelain)"
if git -C "$prod_worktree" symbolic-ref -q HEAD; then
  print -u2 -r -- "ABORT: production checkout must be detached"
  exit 1
fi
previous_sha=$(git -C "$prod_worktree" rev-parse HEAD)
# 将 previous_sha 与 target 写入本机受限部署记录，不写密钥。
if lsof -tiTCP:8011 -sTCP:LISTEN; then
  print -u2 -r -- "ABORT: local IM listener exists; identify its owner"
  exit 1
fi
cd "$prod_worktree"
pnpm pa stop --config ~/.nanoassistant/config.yaml
git checkout --detach "$target"
pnpm install --frozen-lockfile
pnpm build
pnpm pa restart --config ~/.nanoassistant/config.yaml
```

升级失败时保留日志和当前状态，停止候选 Gateway，再在同一干净 checkout `git checkout --detach "$previous_sha"`、安装旧版本锁定依赖并构建、重新启动和验健康。不 reset/clean/stash 生产目录中的未知修改；数据库变更按对应迁移操作单回退。

新 Gateway 健康后核对两机 LaunchAgent label（用 `apps/node/lib/lifecycle.js` 的 `gatewayLabel(config绝对路径)` 计算）、plist 工作目录、`.gateway-state.json` 的 PID/process birth、live cwd、DSH ready/runtime_pid 与目标 SHA。另核 nano profile 内 dsh-integration 与 dsh-base 的链接目标属于当前 checkout/锁定安装；这两条链接由启动逻辑自动检查并刷新。若同名 entry 是普通文件或目录，保留内容并解决冲突，不能删整个 DSH_HOME。

首次迁移需要停止旧 Gateway，并在固定 checkout 启动后验证上述状态；旧目录暂留用于恢复。仅在迁移验收通过且没有 dirty/untracked、进程 cwd 或 profile 链接引用后回收旧 production worktree。Codex 管理目录使用 `archive_worktree`，其他普通 Git worktree 可 `git worktree remove`；保留固定 prod-main，最后按需要 prune。不要直接移动 Codex 管理目录而留下旧附件路径。

## 部署完成验收

必须从官网验证，不能只用源站 200 或节点绿灯代替：

1. Mini IM 监听地址为 loopback `127.0.0.1:8011`；MacBook Air 没有 IM `:8011`。IM/Tunnel LaunchAgent 已加载，live PID、cwd、启动参数与目标 checkout 一致。Tunnel 未变的普通服务部署执行已安装脚本 `--seconds 30`，记录 PID、连接数和公网结果；Tunnel 路径或恢复机制变更及故障恢复才执行 600 秒门禁。
2. 官网 HTTPS 首页返回 200，TLS 验证开启；不使用 `curl -k`。HTTP 首页、带 query 的路径及假凭据登录 POST 返回到同主机 HTTPS 的 308，路径/query 保留。HTTP POST 不应返回应用登录结果。
3. 官网实际静态资源属于本次 build；从真实浏览器检查本次变更相关页面和行为。使用现有真实账号验证登录、历史数据和实时连接；相关附件/聊天功能变更按授权范围做真实验收，保留脱敏证据。不得拿测试账号、测试数据库或隔离端口充当生产。
4. 经官网认证读取 `/im/v1/me`、`/im/v1/nodes`：两生产节点均 online、心跳新鲜，owner 与 config 中真人 UUID 对齐。取人类有效会话用于这些 API，不使用机器凭据冒充用户；不打印 token，不在命令历史中拼接真实密码。
5. 两 Gateway 的 LaunchAgent、live process、state 都指向目标版本，日志无持续认证/owner/重连错误。受影响代理和既有外部通道健康；本地 200 但官网/Tunnel 失败，不能报告部署成功。
6. 保留数据、附件、签名密钥、设备身份、成员准入；发现漂移先核实，普通更新不隐含迁移授权。验证完成后再清理旧生产 worktree。

无凭据公网检查示例（在 Mini，显式使用业务代理；只读且不跟随重定向）：

```bash
curl --proxy http://127.0.0.1:7890 --noproxy '' --max-time 15 -sS -o /dev/null -w '%{http_code} %{size_download}\n' https://im.nanoim.win/
curl --proxy http://127.0.0.1:7890 --noproxy '' --max-time 15 -sS -D - -o /dev/null 'http://im.nanoim.win/login?deploy_check=1'
curl --proxy http://127.0.0.1:7890 --noproxy '' --max-time 15 -sS -D - -o /dev/null \
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

- 官网失败、loopback 正常：先区分业务代理出口、Tunnel readiness 和实际代理连接链，再检查 Tunnel LaunchAgent、ingress、DNS/边缘规则及 `public-tunnel.log`；不要改回 Tailscale HTTP 当作恢复官网。
- 两端都失败：核对 `public-im.log`、launcher 的环境和路径、持久密钥、目标代码和依赖，不退回旧裸 uvicorn 命令。
- 官网旧前端：核对 Mini dist 是否重建、官网 HTML 的资源名和浏览器缓存；不能只看 Git SHA。
- Gateway 不在线：检查配置 URL、设备运行凭据、active owner、Gateway state/live process 及新日志。不要为了恢复在线自动换设备密钥或重新 bind。
- 换 signing key、成员重新初始化、设备交接、数据库回滚均不是常规重启。需要这些动作时按本次授权及对应恢复契约执行；回滚到不具备公网保护的旧版本时保持 Tunnel 关闭。
- 数据恢复必须使用一致快照，历史 token/设备凭据失效与重新登记按恢复契约处理，不能把备份凭据直接复活。

日志位置与源站/Tunnel 服务名见 [生产舰队](../../../../docs/operations/prod-fleet.md#源站与隧道)。开发主链路见 [local-stack](../../../../docs/operations/local-stack.md)，隔离测试见 [worktree runtime](../../../../docs/development/worktree-runtime.md)。
