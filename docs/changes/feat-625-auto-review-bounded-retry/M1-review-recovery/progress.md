# M1-review-recovery — 实施事实

## 2026-10-20 第一阶段：隔离环境与 meaningful red

- 接管专属 worktree `unit-feat-625-auto-review-bounded-retry`，branch `unit/feat-625-auto-review-bounded-retry`；起点/当前产品构建 `861b94129bc8c5aadbca76967268fd203fe04112`，初始 clean。未修改用户主仓、生产 checkout 或父 workspace main。
- `git diff --exit-code 6760d853f06ac81401977514975a9985587196f9 HEAD -- <五项设计产物>` exit 0；Gate 2 retained 仅为设计批准，不是产品 pass。
- 工具链：Node `v25.8.2`（package engines 接受 >=24）、pnpm `11.7.0`、DSH locked `0.2.1-alpha.1`；新建本 worktree `.venv` 使用已安装 standalone Python `3.11.13`，`pip install -e '.[dev]'` exit 0，未使用系统 3.9.6。
- `pnpm install --frozen-lockfile`、`pnpm build`、frontend `npm ci && npm run build` 均 exit 0；frontend 报已有 5 low dependency vulnerabilities，未执行 audit fix/改 lock。
- `PATH="$PWD/.venv/bin:$PATH" ./scripts/docs-check` exit 0：245 maintained Markdown sources / 67 required routes（本阶段记录落盘前执行）。

### 真实 provider smoke（不是故障恢复产品验收）

使用 runbook §2.1 指定入口，两份全新隔离 runtime，main 保持 `deepseek:deepseek-v4-flash`，reviewer 为 `anthropic / codexOAuth:gpt-6.1-sol`、low、声明 context 258400；真实 IM 用户私聊 Global Agent，请求 bash `printf FEAT625_REVIEW_SMOKE`，不是文件免审或 RuntimeClient submit。工具真实返回 marker、exit 0，approval domain 确认为 `classifier_allow` 而非 fallback。两套栈均 down 并复查原端口无监听。未复制生产 secret 或修改真实 owner config。

| 策略 | 真实主 session / bash call | 实际审核与时间 | 本地证据（gitignored） |
|---|---|---|---|
| CC/nano | `8a680484-dd43-402e-af87-c0a821fcc22a` / `call_01_sci7JbD1qfxV8Uz5Xmut0493` | `classifier_allow`，3723ms；proxy 请求 `2026-10-20_18-31-57_033` 明示模型及 low | `.e2e-feat625-smoke-nano/work.json`、`summary.json`，`.dsh-runtime/wt-.e2e-feat625-smoke-nano-92208/storages/nano_approval/sessions/8a680484-dd43-402e-af87-c0a821fcc22a.json` |
| Codex | `ee3f9978-9c98-4818-8f92-202c30c22a65` / `call_00_ET_IijYlUmX77ClvQbkhQ6A9338` | `classifier_allow`，6319ms，full；native reviewer `nano-codex-994d71db-93c9-4a86-b879-89af82d69376`；proxy 请求 `2026-10-20_18-32-18_989` 明示模型及 low | `.e2e-feat625-smoke-codex/work.json`、`summary.json`，`.dsh-runtime/wt-.e2e-feat625-smoke-codex-92317/storages/nano_approval/sessions/ee3f9978-9c98-4818-8f92-202c30c22a65.json` |

代理 locator：CC `/Users/czj/Repos/LLM_PROXY/logs/raw/openai_codex/2026-10-20_18-31-57_033-req-anthropic_messages.json`；Codex `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-20_18-32-18_989_nano-codex-994d71db-93c9-4a86-b879-89af82d69376/`。只提交 locator 和脱敏摘要，不提交原始 prompt/log。

限制：这是基线真实服务 smoke，不是候选实现通过，不替代双策略插件创建→安装→180/55 两次调用、受控 HTTP 矩阵或 17 场景验收；当前 CC 没有 session header、Guardian root header 为 reviewer 自身的现状由新测试观察到，归因修复仍待实现。

### 有意义红测与既有测试处置

- 新增长期 `packages/dsh-integration/tests/approval-retry-native.test.ts`：真实本地 HTTP server → pinned pi-ai/native DSH → NanoApproval → 业务副作用文件；只替代 main 模型输出，不 stub reviewer。覆盖 CC、Codex、legacy 三路径、无故障对照与先503后合法allow。
- `pnpm exec vitest run packages/dsh-integration/tests/approval-retry-native.test.ts` exit 1，**3 passed / 3 failed**，约5.38s。三条对照全部通过；三条恢复场景只收到 `[503]`、副作用为空（期望 `[503,200]`、once）。因此 fixture 已先稳定，红因是基线缺少恢复而不是配置/模型映射失败。
- fixture 明确声明 provider `always/maxRetries:5`，仍只一个失败 HTTP，证明此处不存在可代替本功能的原生透明恢复；新 controller 仍须对最终请求数加产品上限。
- 新测试后续还要求 Retry-After 不提前重打、626 `pa.authorization` 读取0、恢复 trace、Codex full新session。**trace 字段名目前只是测试期望，不是已实现接口**，应在读完设计 trace schema 后校正。
- 既有 `approval.test.ts`、`approval-sources.test.ts`、`llm-attribution.test.ts`、`codex-approval-native.test.ts` 保留各自 parser/来源/非审核 attribution/原生只读与fork职责；`codex-approval-lifecycle.test.ts` 的“单一 timeout 调用”内部断言将按新生命周期 rewrite-merge，而不删除其取消与context rebuild保护。新文件保护真实审核 HTTP facts/恢复接线，现有测试没有同一失败原因覆盖。

### 下一步与门禁

本节为第一阶段历史快照；**其“尚未改产品源码”状态已由下节实施事实取代**。未提交/push、未请求独立review/Q、未canonical/归档/PR；后续修复仍由同一执行子会话承担。

## 2026-10-20 第二阶段：候选实现与扩大验证（未冻结）

### 实现

- 新私有 `policy/recovery.ts`：action共享2次、format子额1次；每次30/60/90s完整预算，prepare总15s，action360s，cleanup5s有界；结构化分类、指数退避、Retry-After不截断、取消优先、封闭generation、请求/attempt/终态摘要。
- 既有唯一 `llm-attribution.ts` stream/dispatcher扩展request-local HTTP事实。Guardian公开loop marker + exact原生session registry命中后才读取currentAttempt；非所属和purpose流透传。未引入第二listener/dispatcher、DSH private import或runtime patch。
- facade先保留downstream/CC workspace免审；冻结精确参数/配置/route/来源；失败先持久完整终态再进既有fallback；拒绝计数及拟route在同一个domain update内计算，取消单独审计不增拒绝，fallback第二行只关联reviewId，人工后续allow关联同reviewId。
- CC冻结准备，stage2只恢复自身，legacy仍单阶段；Guardian首次cache/delta/fork保留，服务恢复销毁旧分支再full，context额度action共一次；late create / 慢dispose按parent quarantine且并发待清理集合全部drain前禁止新reviewer。
- 审计维持domain version1/per-record，optional recovery兼容旧行。request摘要及usage明细各上限100，溢出usage只保留可得合计；pre-response失败native合成的全0 usage不冒充已知成本，缺失/partial标不完整。

### 故障调查与修正

- 首次native regression全不发HTTP：terminal错误明确 `cannot get property codexApproval without inject`；唯一listener回调改经Cordis inject捕获服务，不直接跨上下文get。修正后原6条恢复/对照全绿。
- late-create quarantine在disposal实际完成后仍锁：hold原来只在fulfilled释放，creation会在合法清理后reject；区分pending-work rejection与dispose失败，前者释放、后者保持失败关闭。
- 并发同parent多个慢dispose不能只存最后一个promise：改Set并加两分支分别drain测试，首个完成仍阻止新reviewer。
- 第一次IM fixture误取WS重放的历史completed/permission：改关联当前case与持久公开FINISHED marker，不用“任何completed”代表本轮完成。产品恢复及文件事实未更改。
- native ownership main probe没有Nano配置而触发workflow提示装配异常：测试main scope改为host-owned完整prompt+空tools；不是生产修复或削弱owner测试。

### 已跑候选验证（均工程自验，不是独立产品pass）

| 层级 / 命令 | 已确认结果 |
|---|---|
| `pnpm --filter @nano/dsh-integration build` | 多次exit0 |
| `pnpm typecheck` | workspace8项目exit0；最终批次另在跑 |
| `review-recovery.test.ts` | 25 tests exit0：30/60/90全预算、360上界、shared stage/format、prepare、backoff取消、同刻stop、quarantine、context quota、bounded usage |
| `review-audit.test.ts` | 10 tests exit0：普通ask/Global/child/schedule/heartbeat原fallback、存储失败不allow、cancel不fallback、旧行兼容 |
| `codex-approval-lifecycle.test.ts` | 7 tests exit0：配置/父证据重写、context、context→503→overflow、late create、单/并发慢dispose |
| `approval-retry-native.test.ts` | 15 tests exit0，27.79s：nano/codex/dsh各无故障、503秒header、429 HTTP-date、非法header、真实EOF transport；native policy always/max5不乘法；精确side effect一次、PA读取0 |
| `review-owner-native.test.ts` | 真实native loop + HTTP barrier exit0：idle I、warm trunk B、seeded fork A、另parent C、CC D与main M同时HTTP；A429/2s、B503/backoff cancel、C/D不同usage/requestId；A恢复新session；C2绑定新action；idle self普通流拒绝且HTTP0；release后owner0 |
| `review-source-recovery.test.ts` | 4 tests exit0：两策略×同/跨epoch，live/restored与legacy host_context_live保真、规范化正文/精确action、失败后新历史不进入冻结恢复输入、bare/embedded合法allow format0 |
| `codex-approval-native.test.ts` | exit0，274.25s：真实原生只读inspection/fork、完整90s×3耗尽、晚到取消、全部created=disposed |
| 现有626/attribution相关6文件 | 先29/30通过，仅旧context报错字串期望需更新为结构化terminal；更新后`approval.test.ts`6/6通过；其余sources/codex/personal-security/attribution/workspace保留通过 |
| `.venv/bin/python -m pytest tests/contract -q` | 28 passed，exit0 |
| `.venv/bin/python -m pytest tests/unit tests/integration -q` | 34 passed，exit0 |
| `PATH="$PWD/.venv/bin:$PATH" ./scripts/docs-check` | exit0，245 maintained Markdown / 67 routes（本节落盘前） |

### 真IM受控provider

- 长期fixture与E2E已实现，真实IM用户HTTP/WS→Node→stdio DSH→Anthropic HTTP，不伪造classifier verdict。首轮修正事件关联后 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .venv/bin/python -m pytest tests/e2e/critical_paths/test_auto_review_retry_critical_path.py -q --timeout=180` **2 passed /94.52s/exit0**。
- 两策略各7场景：503→allow、503→malformed→allow、双格式停止、有效deny、429→allow、401不重试、Retry-After15不早发；真实bash文件出现次数等于allow次数；ordinary人工fallback经真实permission接口deny。全部栈down/端口释放。
- 当前另已扩为耗尽、EMPTY_RESPONSE、CC stage2恢复、Guardian inspection→503→clean full，并新增生产默认30/90秒timeout真IM测试；最终结果待下节回填，不预先算通过。

### 真vendor双策略插件旅程（本地gitignored证据）

main均`deepseek:deepseek-v4-flash`；审核均`anthropic/codexOAuth:gpt-6.1-sol`、low；未预放bundle，由Agent分别查API、自主生成、install_bundle并实际两次调用。不是人工批准绕过，也未改生产owner/profile。两份栈均down并复查IM端口关闭。

| 策略 | 用户入口/主session | 实际工具事实 |
|---|---|---|
| nano | `c_zn7ygvgp` / input `f5a4e836d0524861a083d709c5f8b4c1` / `3fc971c0-81a8-41b2-90e2-7e86b4b85ccb`，101.67s | install `call_00_ET_na4ROApXllBNg3HhZrEy2884` application=applied；`travel_reimbursement` calls `call_00_G6unbSHazFdek8z0trXU1408`、`call_00_ET_Z5aKZrkwquSmSBEJfkNQ6759`实际total180/55；公开结果sent `5dd70516360640fda774a86856a38ba4` |
| codex | `c_z42jfmsh` / input `4dba3ce2dd45459eb6ea4cec9a3f546a` / `ead566ba-3bcb-44e2-8855-d9aaef87e322`，154.13s | install `call_00_ET_eDlo4a2nmzNfbgJte3wa5992` application=applied；`travel_reimbursement_calc` calls `call_00_VeioQEGW6VDKDNBEQye90217`、`call_00_ET_zH5YW2ln4SyLGKQPKLq40258`实际180/55；公开结果sent `05c3471c66464a2fa32fe60dbe3ab1c7` |

证据目录`.e2e-feat625-plugin-{nano,codex}/`下work.json（含真实调用output）、messages.json、summary.json、approval domain；不提交原始日志/config/prompt。**限制**：Codex生成的示例业务插件将负数金额clamp0而非拒绝，不能把该差异藏为完整业务规则pass；本单元核心install+两次正数实际调用事实成立，独立Q须按自己的完整旅程判定。工程未人工改示例产物来伪造Agent自主成功。真实旅程本次无技术恢复（retries0）；恢复由受控HTTP证据单独证明。

### 当前下一步

待最终本地批次收集后冻结候选SHA、形成独立静态审查/verifier与Q的中性交接包。未获得独立审查或产品pass，未canonical/归档/PR；同一执行者继续后续修复。

## 2026-10-20 第三阶段：真实底层清理红测与最终候选自验

- 完成第二阶段所列扩大真IM矩阵：两策略各10场景共2 tests **154.00s/exit0**；真实生产默认30/90s timeout→allow再2 tests **142.57s/exit0**。把证据移到独占gitignored本地目录重新组合跑，`-k 'not public_stop' --basetemp="$PWD/.e2e-feat625-controlled-final"`为 **4 passed/287.07s/exit0**。
- 真IM用户`/stop`四场景（两策略×请求中/8秒Retry-After退避中）：**4 passed/54.34s/exit0**。持久cancel、唯一审核HTTP、原退避边界后仍无第二请求、实际文件无动作。导出已保存`.e2e-feat625-evidence/effect-{nano,codex}_stop_{request,backoff}.json`。这是第二阶段实现证据，后续stream drain修正后的同组复验仍在跑。
- `review-owner-native`加强D为真实main的**相同sessionId**而非仅另一个父ID，同时同barrier发HTTP的main仍透传；**1 passed/3.26s/exit0**。移除临时phase.json诊断写入。
- `pnpm typecheck && pnpm test`扩大批次：**111 files/534 tests passed，286.89s，exit0**，包含真实90s×3 native Guardian275.57s。`pnpm build`exit0；Python `pytest -m 'not e2e' -q` **62 passed/39 deselected**；frontend `npm run test` **100 files/936 passed/exit0**（保留既有act/localstorage警告，无新前端修改）；ruff全仓check/format均exit0。
- 新增**真正native Agent/whenIdle/dispose**不合作stream测试，而不是只用fake handle：reviewer第一条迭代故意忽略AbortSignal12s且最终吐allow，父真实session.cancel后5秒取消终态，立刻提第二动作。初次得到实质红测：第二动作过早创建reviewer并执行，原因是model-loop在迭代器return的5秒race退回后已经idle，native dispose可以早于原始iterator settle；只等dispose不足以证明底层drain。
- 修正局限于recovery/Guardian：每条捕获stream持有原始return的drain承诺，超5秒即以此承诺quarantine；discard等待当前attempt全部原始drain后再native dispose/移除exact registry，避免idle/dispose错当底层完成。正常stream路径不变。新native测试确认during-quarantine无第二reviewer/无effect，12秒晚allow只清理，实际`agent/disposed`后新动作才允许且effect只有after-drain一行。最窄组合 **3 files/33 tests/exit0，native13.06s**。
- 因此上述大批次及真IM成功为stream-drain修正前证据，不伪称最终版本全绿：已起最终 **workspace typecheck + 全integration suites**，以及完整8条真IM文件（两策略20场景+4stop+2production deadline）在新独占`.e2e-feat625-controlled-r2/`复验；待收集后更新。
- 上一条为第三阶段进行中快照；源码现已冻结于下节所列提交。尚无独立审查/产品pass、未canonical/归档/PR。全量frontend/Python结果与本次仅integration内部清理修正无重叠，保留；独立门禁须审真实最终SHA。

## 最终工程自验与独立门禁交接（R1）

### 版本与范围

- `unit_id=feat-625-auto-review-bounded-retry`，`review_round=1`，mode=full，有用户旅程。
- `implementation_sha=c11683040302bcf1c4211bcd83aa284f58efc77d`，提交`feat(approval): recover automatic review with bounded fresh attempts`；本节后续提交仅更新工程证据，不修改实现/测试。派发时`validated_at`取本节提交后的clean unit HEAD，以实际`git rev-parse HEAD`为准；两者源码/测试/fixture完全相同。
- `executed_base=861b94129bc8c5aadbca76967268fd203fe04112`。本轮完成前已`git fetch origin main`，HEAD基线与origin/main仍同为861；已审设计R4为6760d853f06ac81401977514975a9985587196f9，产品事实基线为051e7d68e159814cdba1e622f760208fc6d3af68，不混作实施基线。
- worktree：`/Users/czj/.nanoassistant/workspaces/nano-engineering/.worktrees/unit-feat-625-auto-review-bounded-retry`；branch：`unit/feat-625-auto-review-bounded-retry`。未改用户主仓/生产checkout；未push、未创建PR、未merge/deploy/release。
- 改动只含integration policy/单一attribution接缝、相关测试/长期HTTP与真IM驱动、active unit工程事实/runbook；没有改已审spec/design/delta、没有canonical提前覆盖current specs。既有公共Tool/PreToolDecision、配置、domain版本布局不变。

### 最终源码实际执行结果

所有行均工程自验，不代表独立门禁通过；命令均在上述worktree，退出码均0。

| 命令 | 实际结果 / 证据 |
|---|---|
| `pnpm typecheck && pnpm exec vitest run packages/dsh-integration/tests` | workspace8项目typecheck通过；**44 files/166 tests passed，275.69s**，含native90s×3、真实native晚到14.26s、HTTP15场景、owner同barrier及626回归。实际源码与c116相同 |
| `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .venv/bin/python -m pytest tests/e2e/critical_paths/test_auto_review_retry_critical_path.py -q --basetemp="$PWD/.e2e-feat625-controlled-r2" --timeout=240` | **8 passed/342.35s**，两策略各10受控场景、请求中/退避中真`/stop`四场景、真实默认30/90秒timeout→allow。每个允许动作实际文件恰一行，非允许无该行；手工fallback由真实permission卡deny接口闭合 |
| `pnpm build` | 全workspace构建/本地installer candidate通过，版本c116、candidate hash `efa5f6aa3074`；只构建未发布 |
| `PATH="$PWD/.venv/bin:$PATH" ./scripts/docs-check` | 246 maintained Markdown sources、67 routes通过（本末节追加前） |
| `.venv/bin/ruff check . && .venv/bin/ruff format --check .` | 全仓通过，85 files already formatted |
| `.venv/bin/python -m pytest -m 'not e2e' -q` | **62 passed/39 deselected，1.06s** |
| retained `pnpm test` / frontend `npm run test` | 前者111 files/534 tests、后者100 files/936 tests均exit0；仅integration清理修正影响范围已由最终44/166覆盖，未重复无关frontend/PA/IM tests。不能把534写成最终全仓重新执行 |

### 可复查证据与环境

- `.e2e-feat625-controlled-r2/`保留8个pytest场景目录与8份脱敏的`approval-export.json` / `deadline-export.json` / `stop-export.json`，同时有隔离stack数据；均gitignored，**其中config/DB/原始prompt不可提交或直接公开**。fixture records只含case、model、route、session、时间和选定故障，trace不含正文。
- 双真实vendor旅程及限制见第二阶段表，`.e2e-feat625-plugin-{nano,codex}/work.json`的`turns[].items[].payload.presentation.detail`提供实际install与两次工具结果，不应使用截断summary当全量输出。
- 最后`ps`按上述所有本次stack路径核对，IM/Node/HTTP fixture活动进程0；历史真实plugin IM端口49813/50124均关闭。全部新真IM栈finally down；专用worktree保留给独立门禁/后续修复，不自行删除。
- 已沉淀与本unit无暂态耦合的agent-scope `async-boundary-validation` Skill：区分wrapper/idle/dispose与原始iterator settle、并发quarantine集合和重放事件关联；不修改仓库生产运行代码。

### 下一步：由父E派发独立门禁

1. 同一独立静态审查者承担`change-code-review`（review_mode=full，diff_range=`861b94129...validated_at`）与`change-verifier`（verification_mode=full），分别结论和证据；不自行兼任产品Q。特别核对共享完整预算、单stream/HTTP sink、exact owner registry、actual raw drain/quarantine、旧fallback/持久化、626冻结来源和协议兼容。
2. Q独立`change-reviewer`，mode=full/revalidation_mode=full；使用[runbook](../reviewer-runbook.md)和原始17场景，不把E自验当产品pass。受控HTTP与真实vendor旅程分开；除已有普通IM入口，**Global/child/schedule/heartbeat实际故障旅程**仍需Q独立覆盖（现E只在持久化facade测试了这些fallback，不冒充完整模式IM旅程）。负数clamp业务示例偏差如实保留，Q自行判断完整插件规则。
3. 本执行子会话仍为唯一实现/后续修复者；收门禁发现后续用本会话，不另派修复worker。code review/Q返回后才进行按失效范围修复/复验、final sync门禁有效性、delta校正/canonical归并、archive、Ready PR与required远端CI；本次未完成这些步骤。

当前可交付仅为**工程候选及中立门禁输入**，不宣称M1全部退出、独立验收通过或Ready PR完成。

## R1 静态门禁 W1 返修（工程事实，非closure verdict）

### 来源与版本

- 父E已将R1候选4c209推送；Q继续使用其独立4c209现场，本执行者未进入或修改该现场。本节不再沿用上节“未push”的历史快照作为当前团队事实。
- `pre_fix_head=4c20949e5e6995944f35217177950e14dfdf67da`。恢复先核clean/HEAD，然后按父E指令仅cherry-pick独立报告原commit `ce3d08fc212e94c5dc18cccdceeb97ab86ba3b7f`，本branch落点`7beeaf72e`。已用git diff核对两份报告与原commit逐字一致，**不改历史FAIL/CONFIRMED结论**。
- 已完整读取[code-review](../code-review.md)和[verification](../verification.md)：1 P2 CONFIRMED / 0C-1W。W1是终态审计不一致，不是确认取消后执行或重复副作用。
- reviewer首个直接probe足以确认。其第二probe的工具拒绝没有被重试/换工具绕过；以下为本执行者在允许工具内开发的长期Vitest用例，不把该拒绝记成测试结果或权限授权。

### 根因、红测与修复范围

- facade在模型verdict/no-verdict后先封planned trace并await domain update；父取消可穿过这个持久化await，返回cancel而留下唯一完整allow/deny或fallback trace。`escalate`的首/尾取消检查也只返回cancel，未记录同reviewId终态。
- 在`review-audit.test.ts`的storage seam使用deferred gate，将真实`AbortController.abort()`放在**持久copy前**与**持久copy后但update尚未resolve**，不是旧abort-before-review/backoff测试。8条路由×2边界：model allow、model deny、no-result→unattended allow前、no-result→interactive ask前、unattended allow/deny写入中、Global return_to_agent、deny阈值escalation fallback。另测取消补记写入失败必须reject而不能allow。
- 修复前实际`pnpm exec vitest run packages/dsh-integration/tests/review-audit.test.ts`：**17 failed / 10 passed / exit1**。16条窗口均返回cancel却保留旧route，补记失败用例因根本没写取消而错误resolve cancel；测试确实到达目标gate并且未提前完成。未触及产品源码前取得有意义红测。
- 修复只改`policy/approval.ts`：新增私有取消终态操作，在**一次同session原子domain update**中保留原判定行的decision/reason/metadata/attempt/usage事实，将该reviewId唯一详细trace最终route/reason改为cancel/cancelled、移除未执行的fallbackOutcome，并追加同reviewId `review_cancelled/cancelled`终态行。无已有trace的早取消仍只写一条详细取消行；已有trace时新行不重复usage，取消不新增拒绝计数，重复补记不重复终态行。
- 有效verdict持久化后、no-result持久化后、escalate入/出持久化的取消检查都经这一操作；非取消路由及配置不变，manual无自动reviewId仍沿旧路径。所有取消写入必须await，存储失败继续抛出，不能借取消/丢失审计返回allow。
- 没有修改recovery预算/次数、HTTP listener/sink、Guardian registry/生命周期、来源投影/626、公开类型、audit schema/version、设计/delta/canonical。模型allow/deny事实仍在原行；不是把原模型判断伪装成cancel，也不抹去实际安全deny计数。

### 验证与待复验范围

- 初次修复最窄 build + audit：**27 passed / exit0**。补强model fixture knownUsage留存与取消行不重复usage断言后再次单跑：**27 passed /0.311s/exit0**。该补强后的源码/测试已冻结于`fix_implementation_sha=db8bc8201badf734fa7bde25bcd27a00b09128fe`；后续只有本节证据追加。
- `pnpm typecheck && pnpm exec vitest run`下列9文件：**9 files / 94 tests passed /27.02s/exit0**；workspace8项目typecheck通过。文件为`review-audit`、`approval`、`approval-workspace`、`approval-retry-native`、`review-quarantine-native`、`personal-security`、`approval-sources`、`review-source-recovery`、`review-recovery`。包括三策略真HTTP15场景、真实native晚到drain、旧fallback/counters、626有效来源/零全库读取、30/60/90预算组合；其后仅补强audit fixture/断言未改源码，最窄重跑单列。
- 真IM受影响回归使用新独占gitignored`.e2e-feat625-audit-closure/`运行：`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .venv/bin/python -m pytest tests/e2e/critical_paths/test_auto_review_retry_critical_path.py -q -k 'not real_default' --basetemp="$PWD/.e2e-feat625-audit-closure" --timeout=240`：**6 passed /2 deselected /201.55s/exit0**。两策略各10受控场景及4个真实stop；有有效allow/deny、no-verdict及真实人工fallback，允许动作effect一次、取消零执行，finally清理栈。该普通IM回归没有制造storage gate；W1精确持久化窗口证据是上列deferred长期单测，不混称IM已覆盖该注入点。
- `PATH="$PWD/.venv/bin:$PATH" ./scripts/docs-check`通过248篇/67routes，`pytest tests/contract -q` **28 passed/0.56s/exit0**。首组合最后`git diff --check`因本节EOF多一空行exit2，修正该文档空行后通过，无产品代码变化；最终落盘后再执行docs-check/diff检查。
- 失效判断：W1及同类persist窗口、原audit终态/计数/取消/旧fallback结论需closure复验；该处为公共facade，扩大到已有native权限/来源/普通IM矩阵。**原90s×3及默认30/90s timeout、并发owner HTTP归因、预算退避、parser/admission、真实vendor插件结果**在本次delta无变化，保留R1 report与原44/166、真IM8条对应部分证据；不能把retained说成本轮重新执行。PA/IM/frontend无改动，不机械重跑无关全量。
- 本轮结果已全部收集，最后按独占closure目录核对IM/Node/fixture活动进程0，保留6份脱敏export（不提交config/DB/原始prompt）。agent-scope `async-boundary-validation`追加了持久copy前后双gate和cancel-terminal写入失败配方，无本unit暂态数据。
- clean commit冻结后交父E：code review patch/closure + verifier targeted-closure，prior reports为本unit R1两份、focus W1及相邻persist取消边界；`fix_delta_range=4c20949e5e6995944f35217177950e14dfdf67da..validated_at`，其中报告集成为7beeaf72e、实际源码/测试patch为`7beeaf72e..db8bc8201badf734fa7bde25bcd27a00b09128fe`，其后仅本progress证据。`validated_at`取本节追加后的clean HEAD，由最终交接回执提供。原`executed_base=861b94129bc8c5aadbca76967268fd203fe04112`保留，未做final sync或外推effective_through。是否独立closure pass由独立reviewer决定；Q对相关审计范围的失效通知由父E协调。本执行者未push修复、不改Q现场、不派新worker、不归档/PR/pass。

## Q Full R1 FAIL证据缺口恢复（工程输入，不改历史verdict）

- 父E续派原执行者，起点`f47f2b06572d05d2cf520a385c3e81e545182ae7`；仅cherry-pick Q acceptance原`befdea05b5f6d09dca1f54c8a4ade2fa2df72ab8`→本branch `afd71206deb2220b0cddcd7840588667b62340e5`，完整保留14pass/3inconclusive和两major。独立静态R2 closure由父集成，未被本执行者改写；Q workspace/残存日志只读。
- 有限调查定位原Guardian1162s/649s与独立Global能力测试同时超时，宿主sleep928s/645s精确跨其attempt；原attempt、审计、created/disposed、pmset时间和结论边界详见[恢复记录](q-r1-recovery.md)。同命令只加生命周期`caffeinate -i`、不变320s/30s timeout和90s×3预算，**2files7tests/275.18s/exit0**，未确认源码死锁，不把环境定位当context/source缺口自动通过。
- 本轮**未改产品源码/公开契约/设计/delta**。只增持久真IM/context/source驱动、HTTP fixture精确请求导出、native可选证据导出、stop终态断言和工程runbook；没有扩大timeout或伪造source/授权/compact事实。product diff相对于afd为空，由交接实际git证据核对。
- 新真IM context组合：**3pass/60.97s**，暖cache delta→context rebuild503→新full→下一delta，以及第二context不能再rebuild和完整required action放不下时0review HTTP/0retry/0effect；`.e2e-feat625-context-final/`。
- 新真绑定PA source矩阵：**12pass/283.47s**，2策略×direct/PTC×同epoch/真Gateway恢复/公开compact；每页身份/实际observation、sent/held、规范化冻结rows在真实child503前后对照，压缩后旧raw不复活、未观察库内历史不泄入、副作用恰1；`.e2e-feat625-source-final/`。
- native扩大组合**7files47tests/277.01s**，含原Guardian90s×3、Global能力、真正并发owner/fork/HTTP、实际drain/quarantine与626/W1。可选`NANO_REVIEW_NATIVE_EVIDENCE`将实际observe和review/created/disposed/effect导出，未改变测试预算/断言。`.e2e-feat625-native-r2/`。
- 分层来源/admission/audit补跑**5files53tests/1.18s**；真IM既有故障矩阵+stop本轮**6pass2deselected/223.23s**，包含两策略20个HTTP场景及4stop，stop新增complete/cancelled/计数0断言和完整approval/request导出；`.e2e-feat625-stop-final/`。这些集合有重叠，不相加冒充独立测试总数；两个默认30/90s真IM场景retained未本轮重跑。
- 保留Q真正双策略业务插件180/55与负金额/限额拒绝、其他模式fallback事实；不把作者旧clamp示例套到Q另一产物。不声称12个source场景覆盖非空reply/observer/每类admission/旧host_context全部真IM组合：精确行策略与W1storage门控仍是分层长期测试，入口和剩余判定由Q独立核对。
- 所有入口、输入、预期、超时、raw日志、导出、安全清理、早期设施失败及不相等断言修正见[恢复记录](q-r1-recovery.md)；原始config/DB/prompt不提交。首次docs-check因新文件尚未git add被判非tracked link，stage后重跑，不把失败忽略为成功。
- 原17场景不重置；父E收到冻结候选后沿原Q节点n5真实@Q定向续验major和W1。源码不变，静态closure保留；新增测试设施是否需patch审由父E按影响判断。未Q通过，不canonical/archive/Ready PR，不merge/deploy；后续修复仍本执行子会话。

## R3静态patch设施finding返修（工程事实，待原reviewer closure）

- 父E续原执行者，`pre_fix_head=2f519f659b114003d35f2fcc2305469f6e40962c`，先核clean并仅cherry-pick独立R3报告原`29dc06f7cfb2acceddde784c35950954332c23c0`→本branch `3ba1e3539`；[code-review-r3](../code-review-r3.md)与[verification R3](../verification.md#round-3--targeted-verification-of-q-recovery-test-facilities)保留原1P2 CONFIRMED/FAIL0C1W，Git对原两报告diff exit0。未把R3设施finding重开为产品W1，R2 closed及Q此前事实保留。
- 根因确认为opt-in导出直接置于finally的shutdown/home删除之前；mkdir/observation write失败跳过后续清理，后置copy失败跳过home删除，并可覆盖原测试错误。没有启动真实泄漏进程作为复现。
- 将原序列提取为仅tests内的`native-review-evidence.ts`，先对未修复的等价序列运行长期`native-review-evidence.test.ts`，实际**9failed/3passed/exit1**；前置mkdir/write、后置mkdir/copy、shutdown失败均确实到达门控。红测证明是原可执行清理控制流，不冒充完整native运行。
- 修复只在测试设施：嵌套try/finally保证先取observe、再shutdown、后复制fixture、最后清理调用者自建mkdtemp home；各阶段单列diagnostic，不论导出或shutdown拒绝都继续尝试后续清理，每项最多一次。仅缺失fixture ENOENT可忽略，真实读取故障归导出错误；不删除有问题的输出目标。shutdown若拒绝如实报告，不能把“尝试关闭”说成进程已退出。
- 原测试catch仍构造原有带日志/observe的错误并交给finally；无附加故障时重抛同一错误对象，有附加故障时AggregateError以原错误为首项和cause，其余分别标明observation export/shutdown/fixture export/home cleanup及各自cause。成功测试遇导出故障仍失败，不吞错换绿。
- 长期回归扩大为13项：前置mkdir/observation write、后置mkdir/read/write、shutdown、自建home删除失败、双失败聚合、原错误身份、未opt-in路径、成功顺序/缺失文件；另用真实fs既有普通文件输出目标触发EEXIST，假shutdown被调用一次、home消失、输出文件原文未动，不启动runtime。**13passed/1.46s/exit0**；integration typecheck exit0。
- 窄扩大命令`pnpm exec vitest run packages/dsh-integration/tests/{native-review-evidence,codex-approval-lifecycle,review-audit}.test.ts`：**3files47tests/1.77s/exit0**；`pytest tests/contract -q`：**28passed/4.36s/exit0**。原报告与来源commit逐字diff exit0；stage后`docs-check` **252篇/67routes/exit0**、`git diff --cached --check` exit0，产品源码相对2f519的精确path diff exit0。本轮未起native/IM长驻进程，所有job已收集，无服务待清理；workspace Skill另补可复用的可选导出失败清理配方。
- 未改产品源码/权限/预算/timeout/策略/原native业务断言；本轮不重跑全部真IM或90s×3。`2f519`的新context3/source12/原矩阵6、native7files47和旧产品W1 closure按原版本retained，不写成本轮重新执行；Q已自行隔离续验，本执行者未读写其现场/消息/任务图。
- 父E以新冻结HEAD交原R3 reviewer做patch+closure / targeted verification；`fix_delta_range=2f519f659b114003d35f2fcc2305469f6e40962c..validated_at`（含报告整合），实质设施patch从`3ba1e3539`起，仅native测试+tests helper/新错误路径测试与本节证据。原`executed_base=861b94129bc8c5aadbca76967268fd203fe04112`保留，无final-sync/effective-through外推。未push/PR/canonical/archive/merge/deploy。

## Final sync：同链路main变化，暂停收尾门禁交接

- 父E收到两个独立结果后续派：Q R2 PASS实际2f519、静态R4 targeted closure PASS实际89f2。先在clean现场依次整合Q报告7dc58→59acee、R4报告8fcc6→6df263，仅三份报告+184行，原报告逐字及Q/89f2产品树等价均git diff exit0。历史R1/R3 FAIL保留，不用报告整合SHA冒充实际执行版本。
- fetch实际最新main=`18e1af8b1cd0834ae3f22f5780f2d50b740f5171`，相对原861增量134files/+8302/-319；含默认context bundle rc.5/pressure pruning/四工具Auto-off内部放行，以及durable Inbox/发送确认/权限身份/Work隔离，均触及本unit真实入口。不能自动retained全Q PASS或原静态范围。
- merge完成于`f586ff4500e6b522ed470cd4718037889ecd7442`。唯一文本冲突是approval相邻import，保留ReviewRecovery与contextTools；最终该文件相对6df263仅main原3行增量。继承main archive空行曾使全cached diff-check exit2，确认与main逐字相同未改他人归档，本unit相对新main检查另做。
- 未canonical/archive/Ready PR。实际校正delta，补完整阶段预算、W1终态与审计失败边界、CC context分流及Codex完整恢复/admission/parser条目，18个投影场景逐项给实现/测试映射。校正不改设计/首文档，不用旧verifier声称新delta已独立审过。
- [final-sync中性交接](final-sync-handoff.md)提供固定版本、main增量、每闸retained/失效矩阵、原static patch/integration + corrected-delta与Q targeted输入、当前CI等价清单。原executed_base/validated不改；新复验executed_base=18e1af8b1，整体effective_through尚未建立，等独立范围闭环。
- 准备性验证：pnpm frozen install、integration依赖build/typecheck均exit0；集成代码树9files73tests/29.31s/exit0，含新main默认context/旧error helper等。不是新Q真IM或完整CI，后台job121/123均收集。当前等待父E调度必要独立integration/corrected-delta，不因图权限停止已有授权工程，也不绕过该独立门禁提前归并。

## R5-W1 集成运行证据有界调查（门禁仍未关闭）

- 原reviewer R5报告db7c875原样cherry-pick为22a5cbf25；保留code-review `[]`、corrected-delta18/18 aligned和verifier **NOT PASS/0C1W0S**。产品/测试/fixture/锁树仍精确22114489，新执行基线18e1，报告整合不当成重新运行的版本。
- 父E续原执行者后加载systematic-debugging/async-boundary-validation，按原30s期限、单worker/单测试先跑六Agent context默认/profile/opt-out/restart。实际exit1/1fail4skip/35.09s；RPC时间点表明唯一等待为initialize6，未到session.ensure或插件开关。第二次仅Nano自有await诊断也exit1/37.77s：进入initialize handler已用28.72s，worker结束后native继续mount至48.93s；未观察initialize返回，不把timeout视为已清理或已证opt-out死锁。
- 最窄nano无503 HTTP对照按原25s期限仍exit1/1fail14skip/33.22s，同为initialize1未返回，尚未submit/审核HTTP；无fixture的公开initialize0单独30s cutoff也exit1，TERM后实际exit与自建home删除均完成。未继续重跑其余重型native批次刷冗余timeout，欠CC超窗终态/HTTP15矩阵/model-policy/history/capabilities等场景保持待验证。
- 宿主本轮8CPU、1min load约14–24、swap用9489MiB/10240MiB、瞬时disk约32MiB/s，表明仍有明显资源压力；不是全部失败唯一原因已证。额外CPU-profile观察设施曾误将debugger ending识别为listening而重连，已修ignored脚本并用无debugger对照取代，该跑次不用于产品根因或PASS；仅对核对确属本次的pid KILL，未触碰其他工作/生产。
- 补实际`.venv/bin/python -m pytest tests/contract/test_runtime_dependency_contract.py -q` **13pass/7.65s/exit0**，不冒称本轮全28contract或native通过。全部job收集；三个超时native经exact命令+cwd核对后TERM，额外诊断与无debuggerbaseline也实际退出；最终exact unit path native/Vitest为0，原三个mkdtemp home保留恢复现场。
- 详尽命令、每阶段未到边界、原始日志locator、观察层限制及恢复条件见[集成运行调查](integration-r5-runtime.md)。没有证明需要产品/测试修复，故本轮不改源码/预算/期限/fixture/断言；未替Q通过，未canonical/archive/ReadyPR。父E接收具体初始化/资源阻塞后协调下一次稳定现场与原reviewer R5-W1 closure，不能用本次失败补成整体effective_through。

## Q R3报告整合与03:07只读就绪核对

- 父E明确本轮仅整合报告及只读准备；Q报告252c43528原样cherry-pick为03327b4b2，acceptance367–467完整读取、原报告byte-equivalent，FAIL11pass6inconclusive及major/unclear Q625-R3-01保留。两个新树真IM C3链（context→503→allow、再次context封顶→WS deny）为新pass保留，不外推S9/11/13/14/15/17或required/source/stop/fallback/native owner/双vendor新profile旅程。
- 03:07:11+0800一次有界只读采样：Data卷仅1566940KiB≈1.49GiB空闲、df100%；8CPU的load14.98/16.20/32.10，瞬时CPU97%busy/3%idle；24GiB RAM、swap用9456.94/10240MiB。相对上轮未实质恢复，自己exact unit路径runtime/test进程0；本轮没有启动任何runtime/新诊断器/重批次，没有kill旧PID或删除数据。
- 仅量八个已证自己创建的既知目录共191456KiB≈187MiB，均保留。回收这点体积不解决磁盘headroom，不建议牺牲历史原始证据。完整事实、体积表、最小保留建议和保守readiness闸见[原调查新增节](integration-r5-runtime.md)；10GiB盘余量/load接近8等仅建议工程准备线，不是产品契约或已验证充分条件。真正复跑由父E续原计划，未自行起零Agent或并行多栈，未canonical/archive/PR/CI。
