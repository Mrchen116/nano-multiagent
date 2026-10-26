# feat-625 Reviewer Runbook

本文件是本次重新 grounding 后的**设计态执行契约**，不是验收报告。产品基线 `304c59412e8316ef3ea7df9d904a9a450ca618a2`；所有实际验收必须换成 E 冻结的本次实施 SHA。本群 `c_sfokibtk` / 目标 `tg_0dd3b230`，不使用旧群任务、旧会话、旧定时复查或旧 pass。Q2 独立验收，失败交回同一 E 执行者修复和定向复验。

## 1. 当前事实、资源与交接条件

- 本次 P 只运行锁定依赖安装、公开 exports/声明核对与3组窄baseline测试（31/31）；未启动产品服务、未调用真实模型。系统 Python3.9.6，Node24.22.1；默认 `scripts/docs-check` 因缺 PyYAML 失败，文档检查的修复执行结果见正式交接。旧报告的代理 health、旧Python环境或旧模型smoke均不视为本次资源事实。
- 产品验收使用仓库当前标准 `scripts/e2e-up.sh --profile daily`，入口规则见 [worktree-runtime](../../development/worktree-runtime.md#固定日常验收模板)。daily模板P/E/Q的主模型为Sol/high、PA为Astra/medium，独立审核Luna；只是目录/模板事实，不是已启动身份或供应商可用性。真实值以本轮 `.e2e-daily.json`、IM GET config/capabilities、审核请求为准，不把模板ID当IM user ID。
- 现审核器支持原模型声明能力：优先low，否则defaultEffort/首个声明effort，无可调能力不强设。旧runbook“必须low，否则deepseek不能审核”的判断不再适用。所有恢复保持本轮冻结的provider/model/resolvedEffort，不借恢复切模型。真实路由先smoke；本地缺credential/窗口/能力配置问题和HTTP/provider临时失败分别报告。
- E在工程冻结时必须交给Q：本群实际Q验收节点ID、冻结branch/ref/SHA及构建信息；daily清单实际owner/node/群/PA/P/E/Q Agent与IM用户ID、URL/workspace；策略与fallback、模型/effort、运行PID/端口、可执行fixture命令和脱敏trace导出命令/路径。以上实际值目前尚未产生，不能编造；它们是实施验收前置，不阻止本次事前设计和独立Gate2。
- 正式P/E/Q责任角色与隔离产品内daily角色不同。daily-quality不替代独立Q2，daily-product不替代设计author或Gate2 reviewer。

## 2. 起停与双策略设置

在E/Q同一unit checkout中执行；同目标持续复用现场，不因复验新建worktree。隔离运行目录可按策略分配，CC/Codex两轮不复用插件成功状态。

```bash
# 使用自己本次准备的Python>=3.11开发环境，不借生产或用户主仓
python3.11 --version
# 若该checkout已有合格.venv则复用，不重建：
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
export PATH="$PWD/.venv/bin:$PATH"
pnpm install --frozen-lockfile
pnpm build
(cd src/IM/frontend && npm ci && npm run build)

export POLICY=codex # 第二轮cc；使用全新runtime目录
export WT_ROOT="$PWD/.e2e-feat625-daily-${POLICY}"
# 核对是本checkout内的本次隔离路径；e2e-up --wt会直接cd，不会建目录。
printf '%s\n' "${WT_ROOT:?}"
mkdir -p "${WT_ROOT:?}"
./scripts/e2e-up.sh --profile daily --wt "${WT_ROOT:?}"
source "$WT_ROOT/.e2e-ports.env"
curl -fsS "$IM_URL/health" >/dev/null
# 在跨tool受控tmux中持有，或将下面down放入trap EXIT INT TERM：
./scripts/e2e-down.sh --wt "${WT_ROOT:?}"
```

实际4282日常IM的 `/health` 返回200，而 `/openapi.json` 返回404；404不代表服务不可达，此处仅校正准备命令，不改变设计/验收判据。

只用本次随机高位端口/DB/node/workspace/owner根/DSH home，不碰生产8011或用户主仓；daily不与 `--main-config` 混用。脚本定位本checkout构建，无新常驻服务。down之后核实自己记录的进程身份已退出与端口释放，不killall/宽泛pkill，不停止共享LLM代理。

### 2.1 实际阵容、配置与审核smoke

1. 读取本轮 `.e2e-daily.json` 和IM列表/GET config，记录实际身份、online node、主模型和Luna审核路由。核对生成配置的 `NANO_OWNER_CONFIG_ROOT` 是本次node专属目录，Auto开启且dangerously_skip_permissions=false；不得打印token/secret。清单ready不等于真实模型可用。
2. 通过客户端同一IM GET/PATCH配置接口，选本轮实际 `daily-engineering` Global Agent，在当前完整tool_allowlist中增加 `plugin_manager`（若已启用则不重复）；保留其它能力和profile_version，明确设置 `approval_mode=cc` 或 `codex`，核对服务端回执及下一轮实际策略。可复用 `IMClient.update_agent_config(agent_id, approval_mode=POLICY, tool_allowlist=...)`；它读取完整当前配置再合并changes，不能整表覆盖其它开关。默认Codex不变，第二轮CC仅本隔离Agent显式覆盖，不能改产品默认来迁就fixture。
3. 新私聊发送：`这是隔离审核smoke。请仅在当前workspace用bash执行 printf FEAT625_REVIEW_SMOKE，不访问网络或其它目录，并报告实际工具结果。` bash避免普通文件fastpath。Work必须有实际受审动作、合法模型判定和工具一次执行；脱敏domain/request摘要确认实际策略、provider/model/resolvedEffort、HTTP到达和callId/reviewId。health、纯免审或未发HTTP不算smoke。
4. 缺模型/窗口/credential等发HTTP前失败记local_config_failed，先修自己的隔离资源；provider确实返回故障则记具体HTTP/failure，不冒充配置错误或反之。必要的路由调整只能在验收准备阶段按现有合格目录配置并重新smoke记录，不在产品恢复中换模型。未执行或失败的真实旅程结论为inconclusive/fail，不用stub代替。

## 3. 真IM驱动、Work与trace取证

不改客户端面，允许用客户端实际HTTP/WS接口代驱动。复用 `tests/e2e/critical_paths/_im_client.py`：`IMClient(IM_URL)` → `register_or_login('nano','nano1234')` → online node → 按清单实际Agent建立新私聊/使用实际daily群 → `send_message` 发真实用户任务。不用RuntimeClient/session.submit代替Q产品旅程，不伪造native用户source。

- Work位置：`GET /im/v1/agents/{agent_id}/work` → sessions → `/work/sessions/{session_id}/turns` → `/turns/{turn_id}/items`，按分页读全。保留用户消息ID、公开sent回复定位、主session/turn/callId、两次工具真实输出和副作用。
- 每个长审核场景观察窗口至少420秒；完整插件旅程15分钟，到限显式 `/stop` 收束并报告。不能沿用120秒poll截断完整预算，亦不无限续等。
- 当前详细attempts不新增Work界面。实际持久出口为 integration `session.observe` 的 `approvals`（`src/index.ts:466`，domain `nano_approval` v1）。工程native tests可用RuntimeClient **观察**；Q仍从真IM发任务。E须在自己的隔离runtime提供脱敏只读导出命令/产物路径，保留reviewId/callId、policy/model、attempt/request、failure category、time/budget/delay、usage completeness、终态route，并记录导出对应SHA和原数据locator。M1现提供只读 `scripts/fixtures/export_review_trace.py --runtime <本次隔离根> --sha <构建SHA> [--call-id <id>] [--session <id>]`，直接读取公开domain JSON medium并输出相对locator，不连接/restore Session；协议见 [fixture README](../../../scripts/fixtures/README.md#automatic-review-recovery-faults-and-trace-export)。SHA由调用方填写，导出器本身不证明构建版本。
- trace不是授权凭证；不导出完整prompt、owner配置、token、原始headers或私聊全库。必要模型输入证明使用脱敏标记/摘要，由Q核对与Work同一动作。

## 4. 真实双策略插件旅程

在两套干净daily运行中分别给选定Global Agent发送，使用唯一标记：

> 这是隔离测试。请在当前 workspace 为我自主创建一个差旅报销核算插件，按当前 nano-plugin-development skill 查询所需公开API后编写并安装，然后真实调用两次。规则：单条票据报销额为 min(金额, 单项限额)，不允许负数；第一组金额[80,150]、限额100，第二组[25,40]、限额30。请报告插件位置、安装结果和两次实际结果，不能用手算替代工具调用。仅使用当前workspace，不联网发送资料。

实际结果应为180、55。必须有Agent自建插件、真实install_bundle及两次插件调用/对应输出，不能预装成功bundle、用bash/文字算数代替；核对用户收到的结果和Work，不只看Agent称done。若真实provider没有503，不刻意等待它出故障；短暂恢复机制由确定性证据另证。耗尽导致Global任务阻断只证明失败路由，不能用人工allow绕过后声称自动恢复成功。

## 5. 受控故障：M1应交付的长期测试

M1已实现并执行 `tests/e2e/critical_paths/test_auto_review_retry_critical_path.py`、`scripts/fixtures/anthropic_sse_auto_review_retry.py`、`packages/dsh-integration/tests/review-recovery.test.ts`、`approval-retry-native.test.ts`，另有原生并发/配置事务测试。实际工程命令、失败修复记录与证据边界见 [M1 progress](M1-review-recovery/progress.md)；这是工程证据，不是独立Q通过。不新增产品调试开关。

fixture基于现有recording stub，绑定空闲localhost、记录自己的进程/请求计数。main/reviewer分别用模型ID识别，真实HTTP adapter贯穿IM+Node+DSH；main按脚本产生工具，reviewer按scenario发合法CC/Guardian判定、只读tool、429/503、EOF或延迟。必须把Retry-After放真实HTTP响应，不能手捏failure证明pi-ai headers保真；不mock classifier/controller结论。provider policy=always的反证保证原生重试不叠加。故障套件使用default受控source-config（`--main-config`），不将vendor替身混入daily真实服务报告；不替代daily真实旅程。

已执行的fixture命令（无需 live-provider opt-in，代理环境含裸IPv6时需避免污染本地httpx）：

```bash
env -u ALL_PROXY -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u http_proxy -u https_proxy \
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  .venv/bin/python -m pytest \
  tests/e2e/critical_paths/test_auto_review_retry_critical_path.py \
  tests/e2e/critical_paths/test_auto_review_configuration_critical_path.py -q
pnpm exec vitest run packages/dsh-integration/tests/review-recovery.test.ts \
  packages/dsh-integration/tests/approval-retry-native.test.ts \
  packages/dsh-integration/tests/codex-approval-lifecycle.test.ts \
  packages/dsh-integration/tests/codex-approval-native.test.ts \
  packages/dsh-integration/tests/llm-attribution.test.ts
```

| 两策略均测，另legacy回归 | 观测与判据 |
|---|---|
| 503→allow；429秒数/HTTP-date→allow；传输断开→allow | 同call内部恢复、不需主Agent重调、工具一次；HTTP不早于有效Retry-After，并发delay不串。 |
| 连续503；TIMEOUT→503→TIMEOUT | 总额外2次停止；新完整预算、混合类别共享；fallback=deny工具零次。 |
| 503→非法→allow；非法→非法；503→503→非法 | format≤1且计入总2；原生EMPTY_RESPONSE归format，不另送额度。 |
| CC s1非allow、s2先503再allow；s1已耗2次后s2故障 | 有效stage推进不耗额度，只恢复失败阶段，跨stage不重置。 |
| Guardian read→503；context rebuild→503→context overflow；并发fork allow/deny | 失败handle先dispose、full不带失败历史，全action context≤1，缓存不串。 |
| 401/QUOTA/永久配置；有效最终deny；context超限 | 不盲重试/刷allow/换模型；真实deny原风险路由，技术故障不增安全拒绝。 |
| Retry-After=15秒；无效header；headers不可见adapter | 超10秒停止而非截短提前重打；不可得明确unknown，无跨request残留。 |
| 请求中/退避中stop；deadline同刻stop；dispose迟返allow | 取消优先，后续HTTP零新增、工具零次；晚到不复活，超5秒quarantine。 |
| 普通interactive、Global、child、schedule/heartbeat allow/deny | 原ask/return_to_agent/child无卡/配置allow一次或deny零次；cancel不能fallback allow。 |
| 无usage/partial usage、旧domain行、写trace失败 | knownUsage不伪零/伪完整，旧行可读；写失败不新增allow。 |
| high/max-only、low可用、不可调模型；tool+disclosure同parent并发 | 同一配置provider/model支持的effort，不固定low；tool恢复不改disclosure严格parser/预算/namespace和host commit。 |
| shared-host真实owner disable/dispose/cancel，另一owner持续工作；阻塞inspection FS | 撤销本owner generation、排空/kill自己的inspection，不发后继尝试；不kill共享DSH或阻断其他owner。 |
| 请求中及503/backoff中，配置prepare拒绝→事务release；persist失败release；metadata-only完成release | 原action的冻结规则/模型/Context/预算/计数/退避与发布权不变，继续原审核且工具至多一次。configuration.release只删operation reservation，不是stop。另作真正owner cancel/disable反证，必须立即撤销/drain；idle实际配置生效后的新action才按新fingerprint换cache。 |

### 5.1 精确stream归属与真实生命周期

使用真实DSH loop + HTTP，不用scope mock代替：

- 保留idle缓存I；同parent active A和fork B、另一parent C，同时main M、与M同主session的hand-built CC D，以及同parent PA disclosure P。A/B/C均有原生独立session身份，tool owner registry不登记P。
- barrier让流同时进入全局llm/stream。A=429+Retry-After2秒，B=503，C/D/P/M各有不同request-id/usage。只有loop marker+精确登记tool身份命中才读currentAttempt；M/P透明、D保留直接sink，idle不拦别人的流。按冻结resolvedEffort校验，不按模型名/low或parent粗分。
- A只取A的delay/headers，B只取B的503，C/D/P用量不串；取消B不取消A/C/D/P/M；X-Session-Id相同不意味着同一attempt。A失败后新full F的新registry不接纳晚到A chunks/facts/checkpoint。
- 缓存C下一动作绑定新attempt，旧finally不能清后继；idle I自己异常发流失败关闭。setup失败、creation-only signal、dispose迟返/tombstone/quarantine、辅助purpose流和service卸载均有资源归属证据。

默认完整预算：fake clock证明每次CC30/60、Guardian90秒和action360秒；Q真栈分别实际观察CC和Guardian超时恢复，不能用10ms缩时假装生产预算。native fixture另验证不合作create/drain、阻塞FS单次子进程的SIGKILL和晚到零执行。模式fallback以真IM普通请求、Global委派child及测试schedule/heartbeat触发，不伪造source.kind代替Q旅程；native层补完整确定性分支。

### 5.2 当前有效Context/PA共享执行器交叉回归

执行现有 `approval-sources.test.ts`、`codex-approval.test.ts`、lifecycle/native及personal-security系列；保留current而非重建旧625策略：

- 普通tool prepare/recovery的全库授权读取为0，当前不可见/换窗或压缩已移除的标记不回灌。PA独立入站/披露、主人/observer、represented user和实际sent语义不变，不将其全量私库当tool备用证据。
- Inbox逐message保留page/sender/reply；同call正文去重、distinct call保留，投影后cursor；full恢复重用冻结rows，不因503重新标来源。
- 双向来源对照：同epoch父live→委派→503→full仍live，已有restored仍restored；跨epoch/失去观察证明/旧host_context→restored→503→full不提升。旧host_context_live按同epochfalse保留，不能只测试新格式。
- `503 → {"outcome":"allow"}` 对tool的format=0；bare deny与合法embedded verdict按现parser有效，非法outcome/enum/type才计格式；PA disclosure不应用tool默认值，needs_owner/unavailable不被恢复刷成通过。
- full默认recovery admission、checkpoint delta preserve；context rebuild→503→full不重置context额度，无0.65缩放。保留User成本、ProtectedAssistant/最近5工具、超大optional先移除、required/action保护和明确遗漏。
- 503/backoff barrier与请求中barrier分别并行提出撤下忙碌工具/Feature的配置；必须从真实prepare返回capability_in_use并经过PA/Node事务release，不能用伪造cancel代替。观察旧reviewId/attempt继续、captured恢复请求仍原provider/model/effort/rows，工具至多一次。persist失败/metadata-only release由native/事务层确定性测试补全；metadata revision原地更新不能改已冻结config快照。实际idle生效后新动作使用新配置/fingerprint，不携旧checkpoint判定；显式cache release仅撤销精确trunk回写资格、不取消活动exec，不能挂到configuration.release RPC。
- 当前Guardian独立system/agent-pre-step隔离、只读inspection、主Agent项目指令不直接污染reviewer，以及Task stop/UI resume/represented user来源原测试不退化。captured请求证明实际输入、Work和真实效果证明消费结果，分开记录。

## 6. 证据与清理

每场景保存claim、受审SHA/构建、实际阵容/策略/模型/effort/fallback、输入消息/Work/主session/turn/callId/reviewId、请求时间和failure分类、retry/format/context数、可得usage与缺失、route及工具副作用次数、pass/fail/inconclusive。

工程脱敏证据在 `M1-review-recovery/evidence/`，Q总报告在unit根acceptance/regression；真实provider、真IM受控fixture、native、fake-clock四类结果分开。raw日志/数据库/截图/运行配置均本地gitignored，仅提交必要定位和摘要。down后核对PID/端口；fixture只停自己进程，不重启代理/生产，不删除他人现场。交接与返修保持同一实施者、同一unit现场和精确新SHA。
