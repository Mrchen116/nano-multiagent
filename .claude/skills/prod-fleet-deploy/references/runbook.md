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
7. 在切换版本或停服务前完成下节 unit 部署提示词检查，将适用步骤排入部署顺序。

MacBook Air Gateway 长期复用固定 detached `prod-main` worktree，各自安装锁定的 Node/pnpm 依赖并构建。精确 SHA 进入部署记录，不进入目录名；普通更新不再创建或清理生产 worktree。首次迁移后才回收干净且无进程使用的历史目录；不 force、不动其他 worktree。

首次切换须同时完成迁移操作单中的「旧生产数据的额外对账」，尤其是 IM 旧全局主会话、可重放 relay 和工具镜像。停止旧 Python Gateway 时从保留的旧 checkout 使用 `PYTHONPATH=<旧checkout>/src <原venv>/bin/python -m personal_assistant.main stop --config …`；新代码已移除旧模块，不能从新 checkout 调旧入口。新状态安装后只用 Node 生命周期命令。

## Unit 部署提示词

固定入口为 unit 根目录的 `deployment-prompt.md`，文件约定见 [Change Unit Storage](../../../../docs/changes/README.md#一次性部署提示词)。检查和执行分开：先读取目标版本文件、确认迁移计划，再按其要求在停写、切换或启动的相应阶段执行。

1. 逐服务记录实际已部署 SHA 与本次目标 SHA；不能以主仓 HEAD 代替运行版本。结合两者之间的提交、PR 和变更文件识别本次新增或完成实现的 unit，按 unit ID 在目标版本的 active/archive 中定位。不能只筛新增 prompt 文件：设计可能早已合并，本次才实现；归档移动也不代表已经迁移生产。基线不明时先查部署记录和现场版本，不猜“最近几个 unit”。
2. 读取这些 unit 的 `deployment-prompt.md` 及其设计/实现前提，确认目标版本已包含实现且与本次节点、服务范围相符。仅设计完成或 retired 的 unit 不执行。还要核对本环境上次部署记录中未完成的迁移，同版本重试不能因没有 Git 差异而漏掉。
3. 将适用迁移按前置依赖及停启时机纳入部署计划；在已有部署授权范围内遵循 prompt 完成备份、迁移和验证，不再要求用户重复授权。文件存在本身不授权当前操作生产，也不扩大到未授权节点、数据删除或身份变更；确实超出既有授权的动作单独指出。
4. 按环境、unit、目标版本和实际对象范围核对完成记录及现场判据，完成过的不重复执行；中断只继续未完成部分。前提缺失、指令冲突或迁移失败时，停止依赖该迁移的切换，按 prompt 恢复并报告，不用临时兼容代码掩盖失败。
5. 在本机受保护的部署记录中保存 prompt 路径及目标 SHA、适用判断、执行/已完成跳过结果、对象范围、备份位置和验证证据。交付明确哪些迁移完成、哪些不适用或仍未完成；进程在线不能替代迁移验收。无适用 prompt 时记录检查结果并继续常规部署。

## 备份轮转

各机独立保留 `~/.nanoassistant/deploy-backups/` 中最近 **3 次部署备份**，另加必要的迁移前快照。已授权的正式部署包含验收后的例行轮转；失败或尚未完成的部署先保留恢复现场，不因凑满 3 份而删除回退点。此规则不扩展到其他备份根、生产数据库、会话历史或 exports。

1. 按部署记录中的时间、目标 SHA 和备份清单确定顺序，不只按目录名或可变的 mtime 排序。同一次部署的演练、重试副本不重复占名额。新备份尚未完成、部署未通过验收时，不淘汰已有备份。
2. 对需要恢复迁移前数据、身份或配置语义的快照单独保留，并在该快照的 `retention.json` 中记录迁移/unit、证据位置、保留原因和解除条件；不计入 3 次普通部署额度。后续版本的迁移后快照不能替代迁移前状态。每次轮转复核其必要性，确认迁移已无需回退或已有等价迁移前快照后才解除；不因文件名含 migration 就永久保留。
3. 删除前核实保留集的数据库完整性、关键配置/密钥及附件是否齐全，确认旧目录不是 symlink、无运行进程或恢复操作引用，也没有尚未归档的独有迁移证据或用户工作。记录不清的目录暂留并说明原因，不猜测删除。
4. 在备份根之外的受限轮转记录中保存保留/删除的精确路径、版本、保留理由、验证结果和占用；必要的轻量部署/迁移记录继续留存，不为清理再复制整份旧备份。按已核对清单逐目录删除，不用按日期批量通配删除。
5. 清理后核对实际保留目录、释放空间和服务状态，将结果纳入部署交付。保留的迁移快照和本次暂留项须明确列出。

## 更新 Mini 代码和前端

需要更新公网 IM 或 Tunnel 运行服务时，更新代码前，先在 Mini 执行 `.venv/bin/python ~/.nanoassistant/bin/prod-tunnel.py --ready`，验证已安装的 runtime 路径。安全 fast-forward 到目标代码后、停止 IM 或更新运行服务前，再核对一次；目标版本未跟踪该运维脚本时保留已安装版本，不从未提交的本地文件覆盖生产 supervisor。只有目标版本跟踪并包含本次授权更新的脚本时，才执行 `.venv/bin/python scripts/prod_tunnel.py --ready` 检查新版本。它核对 QUIC/IPv6、受管 metrics 地址和 Mini en0 实际路由，失败先恢复出口，不继续部署。当前路径与依赖以生产舰队的「源站与隧道」为准；不能把系统代理、TUN 出口或 HTTP2 当作等价路径。

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

### Tunnel QUIC/IPv6 路径与 supervisor

复用原 Tunnel 身份和 LaunchAgent。变更前备份 Tunnel YAML 与 plist，权限和配置中的密钥不得入 Git。使用生产舰队记录的 QUIC/IPv6 en0 路径；保持 `edge-ip-version` 为字符串。修改配置后先执行 ingress validate 和路径门禁，不能依赖系统代理设置、端口可连或未经验收的自动切换。常规部署不修改 Clash 配置。

Mini 将本次已验证的 `scripts/prod_tunnel.py` 安装到 `~/.nanoassistant/bin/prod-tunnel.py`，原 Tunnel plist 的 `ProgramArguments` 使用主仓 `.venv/bin/python`、该脚本、`--supervise`；保留原日志与 RunAtLoad/KeepAlive。用 SHA256 核对源文件与 runtime copy，更新脚本后重启原服务加载新代码。`bootout` 后需等原服务完全卸载，再 `bootstrap`；不能启动第二个长期 connector 来掩盖失败。

```bash
# 仅需更新 Tunnel supervisor 时在 Mini 执行；先备份 runtime copy，只复制本次已审查版本。
.venv/bin/python scripts/prod_tunnel.py --ready
install -m 600 scripts/prod_tunnel.py ~/.nanoassistant/bin/prod-tunnel.py
shasum -a 256 scripts/prod_tunnel.py ~/.nanoassistant/bin/prod-tunnel.py
# 核对既有 plist 已指向 supervisor 后，再按需要 kickstart 原 Tunnel 服务。
launchctl kickstart -k "gui/$(id -u)/io.github.mrchen116.nano-multiagent.public-tunnel"
.venv/bin/python scripts/prod_tunnel.py --seconds 600
```

仅在 supervisor 或恢复机制变更时做受控恢复演练：暂停已核对的 Tunnel 子 PID，确认 supervisor 自动替换存活但不健康的进程；再结束已核对的子 PID，确认自动重建并恢复公网。演练会短暂影响公网，保持源站和数据不变；演练应在上面的最终连续采样命令之前完成。出口、协议、cloudflared 版本变更及 Tunnel 故障恢复的采样要求见 [Tunnel 验收分级](../../../../docs/operations/prod-fleet.md#tunnel-验收分级)。清理自己的临时 connector 后开始验收，并复核双 Gateway 心跳。故障恢复时间包含每 5 秒的检查、30 秒不健康判定、最多 10 秒的终止等待与重新握手，不能把 30 秒当作可用性承诺。

顺序：IM 健康 → 需要更新的 LLM 代理 → 受影响 Gateway。两机各用自己的 `~/.nanoassistant/config.yaml`，Gateway CLI 裸跑是 start，显式子命令是 `stop` / `restart`。

- 修改 Gateway config 必须先 stop，避免运行态回写覆盖；稳定环境写入 `gateway.environment`。保留节点身份、设备密钥、已绑定的机器运行凭据；不把人类账号密码写回 config 作为常规恢复方式。
- Mini Gateway 的 IM URL 是 Mini loopback；MacBook Air Gateway 使用官网 HTTPS URL，具体值见拓扑文档。人类登录 token 与 Gateway 运行凭据不可互换。
- 代理仅在本次授权范围需要时更新或重启。先核对实际 base_url、监听、进程 cwd/PID 与管理方式；不要根据旧端口示例杀服务，也不要为符合旧文档擅改可用配置。SearXNG 稳定地址继续写各机 config。
- `ssh mini 'zsh -lc "…"'` 可取得 npm/docker 的 login PATH；Node 使用已经核实的绝对可执行路径，两个目标 checkout 都先安装锁定依赖并构建。

### 公网代理

代理地址只在 [生产拓扑](../../../../docs/operations/prod-fleet.md#公网代理出口) 维护。使用各机已有普通 HTTP/SOCKS 代理，不开启 TUN，不依赖 Clash 控制 API 或修改其全局规则。

1. 两 Gateway 先 stop，再写 gateway.environment 的大小写 HTTP_PROXY、HTTPS_PROXY、ALL_PROXY、NO_PROXY 与 NODE_USE_ENV_PROXY=1，保留身份；Mini IM launcher 使用同一环境。用固定 Node CLI restart，代理值不复制进 Gateway plist。
2. 核对真实 Gateway/DSH/工具的代理连接与本机/内网直接连接；变量存在不能代替生效证据。工具是否支持代理须看其实际协议，不能把 HTTP_PROXY 视作所有 UDP 已代理。
3. 公网探针默认读取服务 config，Mini 用已安装 prod-tunnel.py 完整采样，Air 用同一脚本 --public-only --seconds 30。--direct-diagnostic 必须与 --public-only 联用，只供独立诊断，不能代替业务验收。
4. Tunnel 的 QUIC 健康独立检查；客户端 HTTPS 失败不统一归因 Cloudflare。普通发布不必更改或重启 Tunnel，若实际修改路径或恢复机制，须按 600 秒门禁验收。

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

以下适用于完整舰队部署；局部动作只验证受影响服务及连接，纯文档只做文档检查。公网服务必须从官网验证，不能只用源站 200 或节点绿灯代替：

1. Mini IM 监听地址为 loopback `127.0.0.1:8011`；MacBook Air 没有 IM `:8011`。IM/Tunnel LaunchAgent 已加载，live PID、cwd、启动参数与目标 checkout 一致。
   按 [Tunnel 验收分级](../../../../docs/operations/prod-fleet.md#tunnel-验收分级) 执行采样：Tunnel 未变的普通部署运行 `.venv/bin/python ~/.nanoassistant/bin/prod-tunnel.py --seconds 30`；Tunnel 变更或其故障恢复才用 `--seconds 600`。门禁核对正式子进程、路由、连接与公网，采样窗口内 PID 和断连计数不变。
2. 官网 HTTPS 首页返回 200，TLS 验证开启；不使用 `curl -k`。HTTP 首页、带 query 的路径及假凭据登录 POST 返回到同主机 HTTPS 的 308，路径/query 保留。HTTP POST 不应返回应用登录结果。
3. 官网实际静态资源属于本次 build；从真实浏览器检查本次变更相关页面和行为。使用现有真实账号验证登录、历史数据和实时连接；相关附件/聊天功能变更按授权范围做真实验收，保留脱敏证据。不得拿测试账号、测试数据库或隔离端口充当生产。
4. 经官网认证读取 `/im/v1/me`、`/im/v1/nodes`：两生产节点均 online、心跳新鲜，owner 与 config 中真人 UUID 对齐。取人类有效会话用于这些 API，不使用机器凭据冒充用户；不打印 token，不在命令历史中拼接真实密码。
5. 两 Gateway 的 LaunchAgent、live process、state 都指向目标版本，日志无持续认证/owner/重连错误。受影响代理和既有外部通道健康；本地 200 但官网/Tunnel 失败，不能报告部署成功。
6. 保留数据、附件、签名密钥、设备身份、成员准入；发现漂移先核实，普通更新不隐含迁移授权。验证完成后再清理旧生产 worktree。
7. 完成本节验收后执行[备份轮转](#备份轮转)，记录保留的 3 次部署、迁移前快照及清理结果。

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
- Tunnel 进程存在但 `/ready` 503：检查 supervisor 的恢复记录、IPv6 en0 路由与 UDP 7844 的实际握手。2026-10-09 的对比中，IPv4 代理 QUIC 有断连/502，TCP/HTTP2 有握手失败；不要未经连续验收改协议、IP 家族或引入代理。门禁失败即恢复工作未完成。
- 两端都失败：核对 `public-im.log`、launcher 的环境和路径、持久密钥、目标代码和依赖，不退回旧裸 uvicorn 命令。
- 官网旧前端：核对 Mini dist 是否重建、官网 HTML 的资源名和浏览器缓存；不能只看 Git SHA。
- Gateway 不在线：检查配置 URL、设备运行凭据、active owner、Gateway state/live process 及新日志。不要为了恢复在线自动换设备密钥或重新 bind。
- 换 signing key、成员重新初始化、设备交接、数据库回滚均不是常规重启。需要这些动作时按本次授权及对应恢复契约执行；回滚到不具备公网保护的旧版本时保持 Tunnel 关闭。
- 数据恢复必须使用一致快照，历史 token/设备凭据失效与重新登记按恢复契约处理，不能把备份凭据直接复活。

日志位置与源站/Tunnel 服务名见 [生产舰队](../../../../docs/operations/prod-fleet.md#源站与隧道)。开发主链路见 [local-stack](../../../../docs/operations/local-stack.md)，隔离测试见 [worktree runtime](../../../../docs/development/worktree-runtime.md)。
