# feat-625 Reviewer Runbook

本文件是设计态可执行验收说明；尚未实施/运行，不是验收报告。Q在工程交接后用实际受审SHA执行；新fixture/测试文件由M1实现，不把尚不存在的命令宣称已可用。

## 1. 隔离、版本与资源

- 只在E/Q自己的本unit worktree/临时目录运行；不使用生产或开发主仓，不修改真实Agent配置/owner目录，不重启LLM_PROXY。每个策略使用独立runtime目录、IM DB、端口、node identity、workspace、owner config、DSH home。
- 当前基线资源检查：P workspace的node_modules、E2E scripts及config模板存在，`:4000/health`为200；没有`.venv`，系统python是3.9.6且缺yaml/httpx/pytest，不满足仓库Python≥3.11要求。E/Q需使用自己的已有≥3.11 dev环境，或先提供≥3.11解释器后按`docs/development/local-development.md`准备；不可把下面的python3.11替换成系统3.9。health不是模型可用性凭证，不复制私人配置/secret。
- 外部资源：仓库`config/e2e/gateway.yaml`提供声明目录；本机`:4000`提供模型代理入口，但不保证指定路由真实可用。main保留`deepseek:deepseek-v4-flash`，它只声明high/max，**不得选作固定low审核**。审核候选明确选已有`codexOAuth:gpt-6.1-sol`（context_window=258400，levels含low），不修改其能力声明或产品审核effort；它尚未真实smoke，当前只证明本地声明合格，不声称服务可用。受审integration构建、Gateway capability与映射后的native model声明须一致。缺low、窗口、UNSUPPORTED_REASONING_EFFORT等发HTTP前错误按本地配置失败处理，先修隔离配置，不误归为provider临时故障；真实HTTP/provider失败另标inconclusive，fixture不能替代。

从E/Q的受审worktree根执行：

```bash
pwd
 git branch --show-current
 git rev-parse HEAD
 git status --short
# 复用自己已有dev环境；缺少时按仓库安装，不访问生产环境：
python3.11 --version
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
export PATH="$PWD/.venv/bin:$PATH"
pnpm install --frozen-lockfile
pnpm build
(cd src/IM/frontend && npm ci && npm run build)
curl -fsS http://127.0.0.1:4000/health >/dev/null
```

`.venv`已有时不重建；安装依赖不以更新lockfile解决问题。每条命令记录exit code；版本/构建不符先修正自己的隔离环境。

## 2. 每种策略的配置和起停

`POLICY`分别为`nano`（CC）和`codex`。两次旅程独立创建与安装插件，不跨策略复用插件或成功状态。

```bash
export POLICY=nano # 第二轮改codex，分配全新目录
export WT_ROOT="$PWD/.e2e-feat625-${POLICY}"
export E2E_CFG="$WT_ROOT/source-config.yaml"
mkdir -p "$WT_ROOT/.gateway-owner"
python3 - <<'PY'
import os
from pathlib import Path
import yaml
root=Path(os.environ['WT_ROOT']); policy=os.environ['POLICY']
source=yaml.safe_load(Path('config/e2e/gateway.yaml').read_text())
# 保留default tools，显式增加本旅程所需的当前插件宿主能力。
for a in source['agents']:
    if a['agent_id']=='e2e-global':
        a['tool_allowlist']=list(dict.fromkeys(a['tool_allowlist']+['plugin_manager']))
reviewer='codexOAuth:gpt-6.1-sol'
matches=[(p,m) for p in source['llm']['providers'] for m in p['models'] if m['name']==reviewer]
assert len(matches)==1, 'reviewer must select one exact catalog route'
provider,model=matches[0]
assert isinstance(model.get('context_window'),int) and model['context_window']>0
assert isinstance(model.get('reasoning'),dict) and 'low' in model['reasoning']['levels']
source['llm']['tool_approval_model']=reviewer
print({'main':source['llm']['default_model'],'reviewer':reviewer,
       'provider':provider['name'],'reviewer_context_window':model['context_window'],
       'reviewer_effort':'low','live_smoke':'not_run'})
(root/'source-config.yaml').write_text(yaml.safe_dump(source,allow_unicode=True,sort_keys=False))
(root/'.gateway-owner/config.yaml').write_text(yaml.safe_dump({'auto_mode':{
 'enabled':True,'rules':policy,'dangerously_skip_permissions':False,
 'unattended_fallback':'deny'}},sort_keys=False))
PY
./scripts/e2e-up.sh --wt "${WT_ROOT:?}" --main-config "${E2E_CFG:?}"
source "$WT_ROOT/.e2e-ports.env"
curl -fsS "$IM_URL/openapi.json" >/dev/null
# 本轮结束或任意失败都执行；不以killall/宽泛pkill清理：
./scripts/e2e-down.sh --wt "${WT_ROOT:?}"
```

实际执行时把down放入`trap EXIT INT TERM`，或用受控tmux跨多次工具调用持有栈；记录PID、端口、工作区和受审SHA。脚本从本worktree构建启动IM和Node，Node管理stdio DSH。检查生成的`.gateway-config.yaml`确实把`NANO_OWNER_CONFIG_ROOT`指向该`.gateway-owner`，不能让此配置落回真实`~/.nanoassistant`。同一runtime目录不要反复up刷新策略（它会重建DB）；要清楚down后分配新目录。示例未启动真实fixture，也不自动删除证据目录。

agent如有显式approval_mode，以IM config GET/PATCH的实际值为准：CC选`cc`、Codex选`codex`或清空回到上述node继承。不要用UI展示名猜有效配置。既有`IMClient.update_agent_config`通过真实GET/PATCH配置入口并保存profile_version，可复用；核对返回配置和下一轮生效。

### 2.1 审核路由smoke（执行者实际运行，不能用health替代）

1. 起隔离栈后，登录IM读取`GET /im/v1/agents/e2e-global/capabilities`的models及生成的本次配置：确认main仍deepseek，reviewer为上述唯一候选、有窗口且low映射有效；`apps/node/src/providers.ts`会把levels变为native reasoningEfforts，不能只改tool_approval_model字符串而遗漏目录。
2. 在新私聊向该Global Agent发送：`这是隔离审核smoke。请仅在当前workspace用bash执行 printf FEAT625_REVIEW_SMOKE，不访问网络或其它目录，并报告实际工具结果。` bash避免普通文件fastpath。通过Work确认**确实进入模型审核**而非免审；脱敏approval-domain/native请求摘要确认reviewer provider/model、effort=low、实际HTTP请求、合法判定、工具一次执行。代理日志只提供请求事实，不能替代Work消费与输出。CC/Codex各跑一次，各自记录callId/reviewId及代理locator；无有效审核请求不算smoke成功。
3. 发HTTP前的UNSUPPORTED_REASONING_EFFORT/缺模型/窗口/credential配置错误记为`local_config_failed`；先修本次隔离资源，不把它放入503/transport恢复证据。HTTP已发但路由不可用记具体provider结果；未实际运行/未成功均不能写“模型可用”。若候选真实不可用，可在本次隔离目录换另一**已有low+窗口声明**候选后重新smoke并记录实际选择，但产品恢复过程不得临时换模型或effort。
4. P设计修订只执行了无网络目录和公共事件探针，**未执行本smoke**。当前真实路由可用性仍待E/Q执行，不是已验证资源。

## 3. 真IM驱动与可检查位置

不改客户端面，允许客户端同一HTTP/WS接口代驱动；使用`tests/e2e/critical_paths/_im_client.py`而非integration内部session.submit发起产品旅程：

1. `IMClient(IM_URL)`，`register_or_login('nano','nano1234')`，`wait_for_online_node`，核对本次node、`e2e-global`已列出。
2. 用既有`create_direct_conversation('e2e-global')`创建与该Agent的私聊，`send_message`作为真实用户发送下段任务。它调用`POST /im/v1/conversations/{id}/messages`，不是伪造native用户source。
3. 观察会话公开回复和Work：`GET /im/v1/agents/{agent_id}/work` → session → `/work/sessions/{session_id}/turns` → `/turns/{turn_id}/items`。按分页读全。保留会话/用户消息ID、主session/turn/tool call ID和最终sent回复定位。每个长审核场景poll至少420秒，插件完整旅程最多15分钟；到限显式发送`/stop`收束并报告，不静默多等。
4. 临时故障/取消观察同时读取fixture请求时间与实际workspace副作用，不能只看最终文字“done”。普通聊天人工审批使用IM实际permission入口；Global在Work的既有入口观察，不借审批接口绕开return_to_agent。
5. 详细恢复trace不在当前Work新增页面。由E提供脱敏approval-domain导出定位；worker原生测试可调用既有`RuntimeClient.rpc session.observe`读取approvals。Q在自己的隔离目录读该导出、核对reviewId/callId与Work一致，不用底层submit代替用户任务。导出只包含design定义的摘要，不复制原始prompt、owner config、凭据或全量用户数据。

## 4. 真实双策略插件旅程

通过真IM分别给CC/Codex发送（替换唯一标记）：

> 这是隔离测试。请在当前 workspace 为我自主创建一个差旅报销核算插件，按当前 nano-plugin-development skill 查询所需公开API后编写并安装，然后真实调用两次。规则：单条票据报销额为 min(金额, 单项限额)，不允许负数；第一组金额[80,150]、限额100，第二组[25,40]、限额30。请报告插件位置、安装结果和两次实际结果，不能用手算替代工具调用。仅使用当前workspace，不联网发送资料。

预期两次实际结果180和55；至少有真实install_bundle且application结果可解释、两次插件工具调用及对应输出。插件实现由Agent自主生成，不预放“已经安装”的bundle。允许计算规则的实现细节不同，但不得用bash/文字算数冒充插件调用。没有审核请求（全走免审）不能证明恢复；受控矩阵另证受审动作。不保证真实provider恰好出现503，不反复制造服务流量等故障。

实际耗尽后Global可阻断并让任务未完成；这证明失败路径而非真实旅程成功。记录真实vendor/模型、时间、已完成部分及阻塞，不人为人工allow绕过后声称自动恢复完成。

## 5. 受控故障：长期fixture实施契约

M1新增`tests/e2e/critical_paths/test_auto_review_retry_critical_path.py`及配套`scripts/fixtures/anthropic_sse_auto_review_retry.py`。设计选路径，不声称文件已存在。基于现有approval recording stub，监听空闲localhost端口，拥有进程生命周期；使用不同的main/reviewer模型ID识别路由，所有主Agent与审核模型请求都走真实HTTP adapter。main返回确定待审工具/安装动作，reviewer按预定序列返回CC或Guardian合法响应/只读工具使用、HTTP错误、EOF或延迟；不得直接mock classifier/controller结论。

fixture只影响本次source-config，模拟header需在真实HTTP响应上发送，不通过手工捏造LlmFailure证明pi-ai headers保真。按request/model/action/scenario计数，服务恢复后返回正确格式；Guardian可先发guardian_read再失败，下一次检查输入必须没有失败分支残留。不把原生循环native5次/always叠进审核；fixture同时配置provider原生policy=always做隔离反证，主Agent脚本正常结束。

实现后运行示例（从同一worktree，读取文件确认真实参数）：

```bash
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .venv/bin/python -m pytest \
  tests/e2e/critical_paths/test_auto_review_retry_critical_path.py -q
pnpm exec vitest run packages/dsh-integration/tests/review-recovery.test.ts \
  packages/dsh-integration/tests/approval-retry-native.test.ts \
  packages/dsh-integration/tests/codex-approval-lifecycle.test.ts \
  packages/dsh-integration/tests/codex-approval-native.test.ts \
  packages/dsh-integration/tests/llm-attribution.test.ts
```

新增test命名是设计约定；若实施合理等义调整，由E更新runbook和交接命令。pytest live门控沿用仓库规则，受控场景不需要真实vendor返回；报告区分stub/model来源。前端不变但真IM+Node+DSH全栈必须运行。

| 矩阵（两策略均覆盖，另legacy单阶段回归） | 关键观测与判据 |
|---|---|
| 503→allow；429 Retry-After秒数/HTTP-date→allow；传输断开→allow | 同call内部恢复，工具一次，HTTP时序不早于有效Retry-After；并发动作delay不串。 |
| 503连续；TIMEOUT→503→TIMEOUT | 额外恢复2次后停止；完整预算计时器每次重建、混合类别共享额度；工具零执行（fallback=deny）。 |
| 503→非法→allow；非法→非法；503→503→非法 | format最多1次且占总2次；第二个格式或总额度耗尽立即停止，不能领取第三次。原生EMPTY_RESPONSE也适用。 |
| CC s1有效非allow，s2先503再allow；s1故障用完2次后s2失败 | 两阶段正常推进，失败只恢复当前阶段，跨stage不重置总额度；不能把s1非allow当故障。 |
| Guardian read→503；context rebuild→503→context overflow；并发fork一allow一deny | 失败reviewer先dispose；恢复full但不带失败检查结果；全action context最多一次；并发判定/缓存不串。 |
| 401/QUOTA/永久配置；有效最终deny；上下文确定超限 | 不盲重试，不刷allow；deny按原计数/风险升级，技术不可用不增安全拒绝；不换审核模型。 |
| Retry-After=15秒；非法header；headers不可见adapter | 15秒不截成10秒后重打、直接失败分流；无效/不可得信息明确unknown，无跨request残留。 |
| 请求中/退避中 `/stop`，deadline与stop同刻，dispose迟返allow | cancel优先，后续HTTP零新增、工具零执行；晚到不复活、不发布cache；超5秒quarantine不再恢复。 |
| 普通有人值守耗尽，Global耗尽，child耗尽，schedule/heartbeat分别allow/deny | 分别原ask / return_to_agent / child无卡 / 配置allow一次或deny零次；cancel不能fallback allow。 |
| 审计缺usage、partial usage、旧domain行、trace写失败 | model/action关联、knownUsage非伪零、旧行可读；写失败不新增自动allow。 |

### 5.1 精确stream归属的强制并发/idle/full-fork用例

这组由worker用真实DSH loop + HTTP fixture实现，并把request→reviewer session→reviewId/attempt/generation→HTTP facts对照交Q检查；纯mock scope隔离或仅最终allow/deny不足：

- 先成功审核并保留idle缓存reviewer I（currentAttempt为空）；另创建同parent的active reviewer A和并发fork B、另一parent reviewer C，同时发main流M与CC hand-built流D（D沿用与M相同主session作日志关联）。A/B/C必须是真实`agents.create`产生的不同原生session身份，不能在测试中都写parent ID。
- barrier让A/B/C/M/D同时进入全局`llm/stream`，HTTP fixture分别返回A=429+Retry-After 2秒、B=503、C=成功/不同usage、D=另一request-id/usage、M=正常文本。断言全局owner分派先以公开loop marker+精确原生session命中A/B/C才读currentAttempt；M/D和所有非所属流透明、不被I的空attempt或其它owner signal拦截，M仍无审核sink、D保留自己直接绑定的sink。
- 核对A只取得A的429/header/delay，B只取得B的503，C/D的usage/requestId不混；只有A按2秒延迟、取消B不取消A/C/D/M。X-Session-Id即使相同也不能合并facts，X-Agent-Session-Id保持各实际身份。
- A技术恢复废弃旧session后新full reviewer F有新registry entry；人为迟返A的chunks/HTTP facts不能写F的attempt、usage或checkpoint。B从fork结束不能覆盖另一成功trunk。I仍idle时M/D继续成功；人为让I自己普通loop发流应失败关闭且不产生HTTP，不能因此影响其他流。
- 再复用成功缓存C进入下一动作，必须绑定新currentAttempt；旧stream finally不得清空新绑定，旧generation不能获得新授权。重复create失败、dispose迟返/quarantine、listener/entry卸载场景，registry数量与资源归属可核对。辅助purpose流不能被计作普通审核request或从其它owner获取sink，原context/compaction边界不退化。

P无网络probe只证实公开`sessionId`/loop marker分派、ALS以及非所属流透传可行（见design-review Author Resolutions）；没有真实Agent/fork/HTTP，不能代替以上实施证据。

计时证据分两层：worker用fake clock完整证明30/60/90秒每次预算及360秒上界；Q真栈至少分别观察一条CC超时恢复和一条Guardian超时恢复，保持生产默认时长（允许耗时数分钟），不能把10ms缩时测试充作真实预算证明。准备/cleanup不合作边界用native profile注入可控promise，再检查真实cancel/dispose事件与晚到工具零执行。各模式fallback通过真正IM产生的普通请求、Global委派子任务和测试schedule/heartbeat触发；复用现有产品工具与配置，不把直接改source.kind的底层submit当Q真IM证据。工程native tests补确定性覆盖。

### 5.2 合入626后的交叉回归（实施必须保留）

产品新基线`051e7d68e159814cdba1e622f760208fc6d3af68`已修复上下文保真；运行现有`approval-sources.test.ts`、`codex-approval.test.ts`、`personal-security.test.ts`及lifecycle/native suites，并在恢复fixture加入下列反例。这里是待执行契约，不借626历史报告声称625已经通过。

- 普通PA工具动作的准备及所有恢复均断言`pa.authorization`读取次数为0；库内巨大/不在有效上下文的历史标记不进入审核prompt。父压缩后full恢复不复活已删除原文，继承Inbox维持restored；PA入站/披露独立链、observer、主人DM豁免原测试仍通过，不能因禁普通取数而删除独立消息检查。
- Codex Inbox按message分项并保留page/sender/reply；generic Inbox/send正文同call只出现一次，distinct call仍在。service恢复后的full输入重新使用同一规范化冻结rows，cursor/full/delta/fork不因重复投影而误判前缀。
- `503 → {"outcome":"allow"}`应一次service恢复后成功，format=0；`{"outcome":"deny"}`和外围JSON包裹的合法assessment直接按现parser处理，不触发格式恢复。缺省risk/auth/rationale保持626；非法outcome/enum/type才占格式额度，不恢复旧四字段要求或parser额外risk拒绝。
- 组合context rebuild→503→full恢复，检查full沿用recovery admission且context额度不重置；有checkpoint的delta preserve不裁历史，初次full也沿用当前default recovery（不是另加首轮preserve），无0.65缩放；User成本、最近5工具/ProtectedAssistant保护、超大optional先剔除及显式遗漏断言仍成立。required/action确实放不下时不可用，不能靠service retry裁权限证据换allow。
- Q在双策略真实PA受审任务中同时核对上述库外历史标记不泄入、服务恢复不重复副作用；输入体积/来源和恢复轨迹证据分开记录。626的历史production replay只能作为回归参考，不替代此次候选实施SHA验证。

## 6. 证据与清理

每个场景至少保存：claim、受审SHA/构建时间、策略/实际模型/模式/fallback配置摘要、输入消息ID、主session与callId/reviewId、request开始时间与failure分类、额外/format/context计数、可得usage及未知字段、最终route、业务副作用次数、结果pass/fail/inconclusive。

- 当次文字结果放`M1-review-recovery/evidence/`，Q总判定放unit根acceptance/regression；原始logs/DB/screenshots/fixture记录保持gitignored，提交定位与脱敏摘要。
- 真实provider旅程、真IM受控fixture、native integration、fake-clock单测四类结论分开，不写“一切已验证”。
- 每轮down后核对自己记录的PID身份与端口释放；fixture只停自己保存的进程，不能杀其他模型代理/生产Gateway。保留审计导出直到交付完成，不自动clean/reset或删除他人目录。
