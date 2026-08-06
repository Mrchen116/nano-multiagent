---
name: prod-fleet-deploy
description: 个人生产双节点舰队部署/更新：Mac mini 常驻唯一 IM(:8011) + Gateway(mac-mini) + LLM_Bridge(:4000)；本机 jmacbook-air 常驻第二 Gateway(macbook-air)，连 mini IM，LLM 走本机 LLM_PROXY(:4000)。触发条件：用户说"部署生产 / 更新生产 / 部署 fleet / 双节点部署 / 重启 IM / 重启本机 gateway / 重启 mini gateway / 拉代码并重启服务"。不要用于：worktree 隔离 E2E（走 e2e-up/down）、本机再起第二份 IM(:8011)。
---

# 生产舰队部署（IM@mini + 双 Gateway）

个人生产拓扑：**IM 只在 Mac mini**；**两台机器各跑一个常驻 Gateway**，都连同一 IM；两边 Gateway 使用同一个 IM owner。本机禁止再起 `:8011`。

```
本机 jmacbook-air (100.92.244.68)          Mac mini (100.88.34.122, ssh: mini)
┌──────────────────────────────┐           ┌──────────────────────────────────┐
│ Gateway  node_id=macbook-air │──Tailscale─▶│ IM :8011（唯一）                 │
│ LLM_PROXY :4000（本机）       │           │ Gateway  node_id=mac-mini        │
│ 浏览器 → mini:8011            │           │ LLM_Bridge :4000                 │
└──────────────────────────────┘           │ SearXNG :8888                    │
                                           └──────────────────────────────────┘
```

本 skill 覆盖完整闭环，也支持用户指定局部动作（见「局部动作」）。

## 连接与机器事实

```bash
ssh mini                  # Host mini -> 100.88.34.122, user czj, id_rsa 免密
```

| 机器 | 角色 | 代码目录 | LLM 代理 |
|---|---|---|---|
| Mac mini | IM + Gateway `mac-mini` + SearXNG | `~/Repos/nano-multiagent` | `~/Repos/LLM_Bridge`（:4000） |
| 本机 | Gateway `macbook-air` only | `~/Repos/nano-multiagent` | `~/Repos/LLM_PROXY`（:4000） |

两个 ssh 坑：

- **非交互 ssh 无 login PATH**：`docker` / `npm` 用 `ssh mini 'zsh -lc "…"'`。
- **多行命令别套多层引号**：脚本写本地，`ssh mini "zsh -s" < script.sh`。zsh 会把以 `=` 开头的词做 = 展开，脚本里避免 `echo ===`。

## 节点身份（canonical）

| 机器 | `node.node_id` | `im_service.url` | LLM `base_url` |
|---|---|---|---|
| Mac mini | `mac-mini` | `http://127.0.0.1:8011` | `http://127.0.0.1:4000`（LLM_Bridge） |
| 本机 | `macbook-air` | `http://100.88.34.122:8011` | `http://127.0.0.1:4000`（LLM_PROXY） |

- 两边 Gateway 用各自机器上的 `~/.nano-assistant/config.yaml`（不提交仓库）。
- IM 凭据只保存在各机的本地 secret store 或 `~/.nano-assistant/config.yaml`；不得写入仓库、命令历史或本 skill。
- **`node.user_id` 必须是 IM 真实用户 UUID**（`GET /im/v1/me` 的 `id` / `owner_id`），**不是**用户名 `nano`，也**不是**占位符 `demo-user`。两边 Gateway 应对齐同一 IM owner。错了会出现：飞书/外部 channel 仍能回，但影子会话写不进内部 IM（`configured node owner differs from authenticated IM owner`）。部署或改 config 后**必须**用下方验证清单核对。
- **禁止**两台机器共用同一个 `node_id`（后连会踢掉先连）。
- 生产 mini 的 `node_id` 已是 `mac-mini`。若再改名 = 新节点身份，需重新 bind，旧 Agent 路由不会自动迁移；**不要静默改名**。

## 飞书归属

- **飞书 Bot 只挂在 Mac mini 的 Gateway**（`mac-mini`）。
- 本机 `macbook-air` **不跑**飞书 channel；本机 `channel-manifest` / config `channels` 里不应再留 `feishu:*`。
- 通道由 Web IM desired state 下发到目标节点；迁移时在 IM 给 mini 上 agent 建/改通道，不要只拷贝本机密文 cache。

## 硬事实

1. **解释器必须用各 repo `.venv/bin/python`**。homebrew 裸 python 缺依赖。重启 Gateway / LLM 代理禁止用 `python3` / `/opt/homebrew/bin/python3.*` 裸起。
2. **Gateway 配置 = `~/.nano-assistant/config.yaml`**（默认路径）。运行中会把刷新后的 IM token **回写**该文件（备份在 `~/.nano-assistant/backups/`）。**改配置必须先 stop → 改 → start/restart**，否则内存态回写冲掉编辑。
3. **`node.user_id` = IM owner UUID**（见「节点身份」）。部署闭环结束前必须跑验证清单里的 assert；未对齐不算舰队健康。
4. **Gateway CLI**：只有 `stop` / `restart`；不带参数裸跑 = start。没有 `start` 子命令。
5. **本机禁止起 IM `:8011`**。Web IM 入口：`http://100.88.34.122:8011/`。
6. **IM 前端 `src/IM/frontend/dist` 被 gitignore**——mini 上 pull 到前端改动后必须 `npm ci && npm run build`。
7. **IM 签名密钥只保存在 mini `~/.nano-assistant/im-jwt-secret`（`0600`）**；不得把值写进仓库、shell history 或临时命令。常规部署在停止旧 IM 前读出并复用它；文件缺失或为空时必须直接失败。主动换钥才覆盖该文件，并会使 Web IM 既有登录态失效。
8. **两边 Gateway 启动都带 `SEARXNG_URL=http://100.88.34.122:8888`**（SearXNG 只在 mini；本机经 Tailscale 访问）。mini 上也可用 `http://127.0.0.1:8888`。
9. **LLM 代理配置只在启动时加载**；改 `upstreams.json` / `.env` 必须重启对应代理。改前留 `.bak`。
10. 顺序：**IM →（各机 LLM 代理若需要）→ 两边 Gateway**。Gateway 启动即连 IM。

## 完整部署闭环

默认用户说「部署 / 更新生产」时走全流程。某步无变更可跳过，但验证仍要两边 node。

```bash
# ——— Mac mini ———
# 1. 拉代码
ssh mini 'cd ~/Repos/nano-multiagent && git status -sb && git pull'

# 2. 前端有改动则重建
ssh mini 'zsh -lc "cd ~/Repos/nano-multiagent/src/IM/frontend && npm ci && npm run build"'

# 3. 读取持久密钥后重启 IM（普通更新不换钥）
ssh mini 'zsh -lc '"'"'
  secret_file="$HOME/.nano-assistant/im-jwt-secret"
  [[ -s "$secret_file" ]] || { print -u2 -r -- "IM secret missing: $secret_file"; exit 1; }
  im_secret=$(<"$secret_file")
  pids=$(lsof -ti:8011)
  [[ -n "$pids" ]] && kill $pids
  for attempt in {1..120}; do lsof -ti:8011 >/dev/null 2>&1 || break; sleep 0.5; done
  lsof -ti:8011 >/dev/null 2>&1 && { print -u2 -r -- "IM port still in use"; exit 1; }
  cd ~/Repos/nano-multiagent && IM_JWT_SECRET="$im_secret" PYTHONPATH=src \
    nohup .venv/bin/python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011 >> im-service.log 2>&1 &
'"'"''

# 4. 若改了 LLM_Bridge，重启代理
ssh mini 'kill $(lsof -ti:4000) 2>/dev/null; sleep 1; cd ~/Repos/LLM_Bridge && \
  nohup .venv/bin/python start_proxy.py --ui >> nohup.out 2>&1 &'

# 5. 重启 mini Gateway
ssh mini 'cd ~/Repos/nano-multiagent && \
  SEARXNG_URL=http://127.0.0.1:8888 PYTHONPATH=src \
  .venv/bin/python -m personal_assistant.main restart'

# ——— 本机 ———
# 6. 拉代码（先确认无会挡 pull 的本地改动；保留用户 dirty）
cd ~/Repos/nano-multiagent && git status -sb && git pull

# 7. 确认本机没有占用 8011 的 IM；有则停掉并告知用户
lsof -ti:8011 && echo "ABORT: 本机 :8011 被占用，生产模式禁止本地 IM"

# 8. 若改了 LLM_PROXY，重启本机代理
kill $(lsof -ti:4000) 2>/dev/null; sleep 1
cd ~/Repos/LLM_PROXY && nohup .venv/bin/python start_proxy.py --ui >> nohup.out 2>&1 &

# 9. 确认 config：node_id=macbook-air，im_service.url=http://100.88.34.122:8011
#    然后重启本机 Gateway
cd ~/Repos/nano-multiagent && \
  SEARXNG_URL=http://100.88.34.122:8888 PYTHONPATH=src \
  .venv/bin/python -m personal_assistant.main restart
```

## 局部动作（用户指定时只做这些）

| 用户意图 | 动作 |
|---|---|
| 只重启 IM | 闭环步骤 3；随后建议重启两边 Gateway（token/连接可能抖），至少验证 IM HTTP + 两 node 是否仍 online |
| 只重建前端 | 步骤 2；IM 静态资源一般即时生效，缓存异常再重启 IM |
| 只重启 mini Gateway | 步骤 5 |
| 只重启本机 Gateway | 步骤 9（先做步骤 7） |
| 只更新 mini 代码+服务 | 步骤 1–5 + 验证 |
| 只更新本机 Gateway | 步骤 6–9 + 验证本机 node |
| 只重启 LLM 代理 | mini→步骤 4；本机→步骤 8；改模型目录见下 |
| 改 Gateway config | 目标机：`stop` → 编辑 `~/.nano-assistant/config.yaml` → 裸跑或 `restart` |

### 显式换 IM 签名密钥

只有需要让全部现有 IM 登录令牌失效时才执行。它不是常规代码部署的一部分：

```bash
# mini：生成并保存新值，权限仅限当前用户读取
ssh mini 'cd ~/Repos/nano-multiagent && umask 077 && .venv/bin/python -c '"'"'import secrets; print(secrets.token_urlsafe(48))'"'"' > ~/.nano-assistant/im-jwt-secret && chmod 600 ~/.nano-assistant/im-jwt-secret'

# 接着执行完整闭环的步骤 3 重启 IM；随后两个 Gateway 用保存的账号凭据重新认证

# 两边 Gateway 重新认证
ssh mini 'cd ~/Repos/nano-multiagent && SEARXNG_URL=http://127.0.0.1:8888 PYTHONPATH=src .venv/bin/python -m personal_assistant.main restart'
cd ~/Repos/nano-multiagent && SEARXNG_URL=http://100.88.34.122:8888 PYTHONPATH=src .venv/bin/python -m personal_assistant.main restart
```

浏览器中的 Web IM 会被要求重新登录。换钥后必须完成下方完整验证清单。

## 验证清单

```bash
IM=http://100.88.34.122:8011

# IM
curl -s -o /dev/null -w "%{http_code}" "$IM/"     # 期望 200

# 从本机 secret store 或当前 shell 取得 IM 凭据；不要把值写入本 skill。
: "${IM_USERNAME:?set locally}"
: "${IM_PASSWORD:?set locally}"

# 登录拿 token + 真实 owner UUID
TOKEN=$(curl -s -X POST "$IM/im/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$IM_USERNAME\",\"password\":\"$IM_PASSWORD\"}" | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
ME=$(curl -s "$IM/im/v1/me" -H "Authorization: Bearer $TOKEN")
OWNER=$(python3 -c "import json,sys;print(json.load(sys.stdin)['id'])" <<<"$ME")
echo "IM owner=$OWNER"

# 两节点均应 online（名称以现网为准；已迁移则是 mac-mini + macbook-air）
curl -s "$IM/im/v1/nodes" -H "Authorization: Bearer $TOKEN"

# 强制：两边 Gateway config 的 node.user_id == IM owner（错则飞书影子会话会静默失败）
ssh mini "python3 -c \"import yaml;from pathlib import Path;u=yaml.safe_load(Path.home().joinpath('.nano-assistant/config.yaml').read_text())['node']['user_id'];print(u);assert u=='$OWNER', u\""
python3 -c "import yaml;from pathlib import Path;u=yaml.safe_load(Path.home().joinpath('.nano-assistant/config.yaml').read_text())['node']['user_id'];print(u);assert u=='$OWNER', u"

# Gateway 日志不应在刷 owner differs（有则 shadow sync 坏了）
ssh mini 'tail -n 80 ~/.nano-assistant/gateway.log | grep -c "configured node owner differs" || true'
# 期望 0；非 0 则先 stop → 改对 user_id → 必要时清理 ~/.nano-assistant/external_shadow_sagas.sqlite3 里 stale owner 的 pending → restart

# 本机未占 8011
lsof -ti:8011 && echo "FAIL: local IM running" || echo "ok: no local IM"

# SearXNG（首请求可能 5s+）
ssh mini 'curl -s --max-time 15 "http://127.0.0.1:8888/search?q=test&format=json" | head -c 100'
```

日志：

| 服务 | 位置 |
|---|---|
| IM | mini `~/Repos/nano-multiagent/im-service.log` |
| Gateway（每机各自） | 该机 `~/.nano-assistant/gateway.log`；PID 见同目录 `.gateway-state.json` |
| LLM_Bridge | mini `~/Repos/LLM_Bridge/nohup.out` |
| LLM_PROXY | 本机 `~/Repos/LLM_PROXY/nohup.out` |

## 改模型目录（llm 段）

- 可选模型 = 该 Gateway 自己 config 的 `llm:`（**必填**）。经 WS 上报给 IM，设置页模型下拉按**节点**出现。
- 模型名是对应代理的 `profile:model` 路由：mini 看 `LLM_Bridge/upstreams.json`，本机看 `LLM_PROXY/upstreams.json`。
- 改完：先 stop Gateway → 改 config → start/restart；若只改了代理 upstreams，先重启代理再重启 Gateway。

## 与其他文档的边界

- 人读拓扑与入口：[`docs/operations/prod-fleet.md`](../../../docs/operations/prod-fleet.md)
- 纯本机一次性 IM+Gateway（开发主链路，非本舰队）：[`docs/operations/local-stack.md`](../../../docs/operations/local-stack.md)
- worktree 隔离 E2E：[`docs/development/worktree-runtime.md`](../../../docs/development/worktree-runtime.md)
- SearXNG 容器细节：仓库根 `LOCAL_INFRA.md`（gitignore，本机笔记）

## 常见报错速查

| 现象 | 原因 |
|---|---|
| `No module named httpx/uvicorn/dotenv` | 用了 homebrew 裸 python，换 `.venv/bin/python` |
| `argument command: invalid choice: 'start'` | CLI 只有 stop/restart，裸跑即 start |
| `config root must contain 'llm' section` | config 缺 `llm:` |
| 本机 Gateway 连不上 IM | Tailscale / `im_service.url` 未指 `100.88.34.122:8011`；或本机误起了本地 IM |
| 只有一个 node / 另一个被踢 | 两边 `node_id` 撞名 |
| `zsh: == not found` | echo 参数以 `=` 开头触发 zsh = 展开 |
| `docker: command not found`（ssh） | 用 `zsh -lc` |
| IM 起不来且 log 无新行 | `:8011` 旧进程未杀净 |
| Web IM 仍是旧前端 | mini 上未 rebuild `dist` |
| 本机 Gateway HTTP 能登录但节点不上线 / WS 报 SOCKS | 系统开了 Clash 等 SOCKS；当前代码 IM WS 已 `proxy=None` 直连。旧进程需重启 Gateway |
| 飞书能回，内部 IM 看不到飞书会话/消息 | `node.user_id` ≠ `GET /im/v1/me.id`（常见残留 `demo-user`）。日志：`configured node owner differs from authenticated IM owner`。处理：stop → 改成真实 UUID → 清 saga 里 stale `owner_id` pending → restart。代码层静默双轨见 issue #225 |
| 改完 config 又变回旧值 | 未先 stop；运行中 token 回写冲掉编辑 |
