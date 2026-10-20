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
