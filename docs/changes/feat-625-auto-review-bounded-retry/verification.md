# Verification Report: feat-625-auto-review-bounded-retry

## Round 1 — full

> Validation snapshot: `861b94129bc8c5aadbca76967268fd203fe04112 → 4c20949e5e6995944f35217177950e14dfdf67da`

| 字段 | 固定值 / 边界 |
|---|---|
| unit_id / review_round | feat-625-auto-review-bounded-retry / 1 |
| verification_mode / code review_mode | full / full（分别输出，非产品 Q） |
| validated_at | `4c20949e5e6995944f35217177950e14dfdf67da` |
| executed_base | `861b94129bc8c5aadbca76967268fd203fe04112` |
| implementation_sha | `c11683040302bcf1c4211bcd83aa284f58efc77d` |
| effective_base / effective_through | **未建立**；尚无 final sync 及失效判断，不外推到 main 或后续修复 |
| diff | 完整 `executed_base...validated_at`，22 files / +2088 -249；非空 upstream；实现、长期测试、fixture、文档全部纳入 |
| 独立性 | 未参与受审实现；同一独立静态 reviewer 执行 code review 与 verifier；不兼任 Q，不修源码/测试/配置/设计，不派子 agent |
| 来源 | 父 E 内部委派；`c_fqyj3bvq` / `tg_e33bc1fd/n3`，不读 Inbox/conversations，不发公开消息，不改团队图 |

## Summary

**Verdict: FAIL — 0 CRITICAL / 1 WARNING / 0 SUGGESTION。** W1 为已复现的取消终态审计不一致；不是发现工具在取消后执行。两份报告不能作为 Ready PR 或 M1 完成声明。

| 维度 | 结果 |
|---|---|
| Completeness | 工程实现与长期回归已逐项核对；M1 的独立 Q/完整模式真 IM 旅程仍待完成，不能将作者自验替代独立验收 |
| Correctness | 恢复次数、完整预算、失败隔离、原权限/fallback 工程证据成立；终态 trace 在持久化取消窗口偏离，见 W1 |
| Coherence | 主要设计决定遵守；取消审计设计未完全落实 |
| requires_full_verification | false（本轮本来就是 full；未发现需扩大到范围外单元的依据） |
| report paths | 本目录 `code-review.md`（纯 JSON finding 数组）、`verification.md` |

## 输入与范围核对

读取仓库 AGENTS、SPEC、docs/README、change-workflow/testing、current `docs/specs/gateway/agent-capabilities.md` 的 Auto/626 契约、service-lifecycle 相关边界；读取 unit spec/design/delta/runbook、M1 progress 和设计门禁历史定位。设计 R4 在 `6760d853f06ac81401977514975a9985587196f9` Approved，属于设计结论而非实现证据。

`git merge-base executed_base validated_at` 精确为 executed_base。`git diff --exit-code c1168304 4c20949 -- packages scripts tests` exit 0：4c209 仅补 progress，源码、测试和 fixture 与实现提交一致。审查使用固定 tree，不审作者现场的后来变化。current spec 尚未归并，属于 active unit 预期阶段；没有修改 spec 来适配发现。

## 实际命令与证据

所有本轮执行都在自建 `.worktrees/review-feat-625-r1`，不在作者现场启动测试或写入文件。Node v25.8.2 / pnpm 11.7.0，frozen DSH 0.2.1-alpha.1。

### 独立执行

| 命令 | 退出 / 结果 | 用途与限制 |
|---|---|---|
| `pnpm install --frozen-lockfile` | 0 | 自己 worktree 依赖；未改 lock/config |
| `pnpm --filter @nano/dsh-integration... build` | 0 | product-contracts + integration 编译，为 native tests 建立本轮产物 |
| 下列 12 文件 `pnpm exec vitest run ...` | **0，12 files / 91 tests，43.50s** | 真实 native HTTP、并发 owner、原始 iterator quarantine 及 626/权限回归；没有重跑耗时 90秒×3 的全部套件 |
| `pnpm typecheck`（首次） | 2 | 新现场只构建 integration 依赖，缺 `@nano/channels` 编译声明，PA 报 TS2307/级联类型错误；非受审改动失败 |
| `pnpm -r --if-present build && pnpm typecheck && git diff --check 861b94129...4c20949` | **0** | 构建全部 workspace 的前置声明后，8项目 typecheck 通过，完整 diff whitespace 通过；未执行 release/installer 发布 |
| `node --input-type=module` facade 取消/持久化探针（见 W1） | **0，CONFIRMED** | 编译产物；storage seam 控制取消时刻，真实 AbortController，验证返回与持久记录不一致；不运行工具体 |
| 第二个 deferred storage gate 加强探针 | **工具门禁拒绝，未执行，无进程退出码** | 工具返回 `Automatic reviewer unavailable ... (classifier_unavailable; return_to_agent)`；未重试或换工具绕过，不将其记为产品复现结果或测试失败 |

独立 Vitest 完整命令：

```sh
pnpm exec vitest run \
  packages/dsh-integration/tests/review-recovery.test.ts \
  packages/dsh-integration/tests/review-audit.test.ts \
  packages/dsh-integration/tests/review-source-recovery.test.ts \
  packages/dsh-integration/tests/review-owner-native.test.ts \
  packages/dsh-integration/tests/review-quarantine-native.test.ts \
  packages/dsh-integration/tests/approval-retry-native.test.ts \
  packages/dsh-integration/tests/codex-approval-lifecycle.test.ts \
  packages/dsh-integration/tests/codex-approval.test.ts \
  packages/dsh-integration/tests/approval-sources.test.ts \
  packages/dsh-integration/tests/personal-security.test.ts \
  packages/dsh-integration/tests/llm-attribution.test.ts \
  packages/dsh-integration/tests/approval.test.ts
```

### 复用作者证据（不是本轮重新执行或 Q verdict）

`M1-review-recovery/progress.md:104–141` 提供版本、完整命令、结果及 locator：最终 integration 44 files/166 tests、真 IM 8 tests（两策略各10场景、4 stop、默认30/90秒 timeout）、build、Python62、ruff/docs-check 均 exit0。全仓 TS534 / frontend936 是清理修正前 retained；只对 integration 影响范围有最终重验，不能称最终全仓534重新跑过。本轮独立91 tests 与这些最终源码一致。

只读抽查作者 `.e2e-feat625-controlled-r2/` 脱敏导出（未拷贝 config/DB/原始 prompt）：

- `test_auto_review_http_recovery{0,1}/approval-export.json`：nano/codex 首次503后的同 call 恢复、requestId/status、retry1、format0；成功 request 与失败 request 区分，缺失用量未伪零。
- `test_auto_review_real_default_0/deadline-export.json`：nano `effect-nano_deadline`，review_timeout 后新尝试 budget 30000，两个 HTTP 时间差约30.560秒，usageComplete=false。
- `test_auto_review_real_default_1/deadline-export.json`：Codex `effect-codex_deadline`，90000 后 clean full-recovery、新原生 session，HTTP 时间差约90.602秒，usageComplete=false。
- `test_auto_review_public_stop_n0/stop-export.json`、`...n3/stop-export.json`：请求中 nano 及退避中 Codex 的 terminal cancelled / finalRoute cancel。它们没有跨越 W1 的持久化窗口，不能反证 W1。

这是样本核验 + 明确版本/命令的 retained evidence，不声称本轮独立遍历了所有原始运行数据。未重跑全套慢测试或真实 vendor 旅程；产品 Q 仍独立另跑。

## Completeness

### M1 退出标准逐项

| design.md:236 退出组 | 工程核对 / evidence | 状态 |
|---|---|---|
| [reviewer] 原17场景、双策略自主插件创建→安装→两次真实调用 / Work、副作用 | 作者 progress:78–87 提供 install/call/sent locator；作者自己披露 Codex 示例负数 clamp0 而非拒绝 | **独立 Q 待覆盖**；正数180/55不等于完整规则 pass |
| [reviewer] 真 IM 受控矩阵、完整预算、Retry-After、取消、各模式 fallback | 最终8 tests工程自验 + 脱敏导出样本；普通 interactive 真实 permission deny 已有；Global/child/schedule/heartbeat 完整真 IM 故障路由没有证据 | **部分工程可验证，完整产品出口待 Q** |
| [worker] 共享 controller、failure/header/native、owner/idle/fork/main/CC、生命周期/quarantine、legacy、optional audit、626 | 本轮12/91及源码映射见下表；慢 native 90×3 retained于最终44/166 | 工程覆盖成立，**W1 阻断终态审计一致性** |
| [worker] 最窄测试→typecheck/build、dependency contract/docs/current CI、独立门禁与脱敏证据 | 本轮build/typecheck/91 tests；作者62 Python含28 contract、ruff/docs-check；原始日志保持本地 | 相关工程检查成立；独立静态本轮 FAIL，Q/最终 sync/完整CI收尾待做 |
| [worker] 长期 HTTP fixture + 可复跑真 IM 驱动，无生产或正式配置变更 | `scripts/fixtures/anthropic_sse_auto_review_retry.py`、`tests/e2e/critical_paths/test_auto_review_retry_critical_path.py`；fixture 属测试进程、真实 HTTP adapter/IM ingress，不 mock reviewer verdict | 已实现，未在本轮启动真 IM |

没有原流程 worker tasks.md 不作为缺陷：这是简化流程，progress 是补充；退出依据是实际实现、回归和适用验收，而非文档数量。无前端改动/prototype/reference，must-match **N/A**。

## Correctness

下列代码路径未展开时均在 `packages/dsh-integration/src/`；测试均在该包 `tests/`，真 IM 指上述长期 E2E。编号按 spec.md 顺序覆盖全部17 Scenario，工程通过不代表 Q 通过。

| # / Requirement / Scenario（契约位置） | 实现位置 | 直接证据与限制 | 状态 |
|---|---|---|---|
| 1 短暂故障后放行（spec:63–67） | `policy/recovery.ts:168–208`；`approval.ts:143–145,175–177` | `approval-retry-native` 15条覆盖nano/codex/legacy的真实503/429-date/EOF与effect一次，provider always/max5不乘法；真 IM success retained | 工程 covered |
| 2 混合失败共额2次（69–72） | recovery:172,198–204；classifier:24–40 | recovery测试 stage共享、transient+format/耗尽，lifecycle context→503→overflow；真 IM mixed/exhausted retained | 工程 covered |
| 3 CC完整30/60预算（76–79） | classifier:30；recovery:172–175 | fake-clock每次30/60/90；CC第二阶段只重做失败阶段；默认30秒导出实测 | 工程 covered |
| 4 Guardian完整90秒（81–84） | `policy/codex.ts:102–159` | `run('guardian',90000)`包含create、inspection、context rebuild；最终native90×3 retained；默认90秒导出实测 | 工程 covered |
| 5 几分钟但有界（86–89） | recovery:136,148–166,199–207 | action360s/prepare累计15s/cleanup5s，500/1000ms±10%、每wait≤10s；正常最坏预算有余量，不共享旧90秒窗口 | 工程 covered |
| 6 首次格式后有效判定（93–96） | recovery:197–204；classifier:35–38；codex:140–143 | EMPTY_RESPONSE、empty_text、malformed共享format1/total2；合法bare/embedded由parser处理 | 工程 covered |
| 7 再次格式或总额尽（98–101） | recovery:198 | recovery组合矩阵、真 IM twiceformat/exhausted；不按类型重新给额 | 工程 covered |
| 8 CC两阶段/最终拒绝（105–108） | classifier:13,24–40；approval:168–178 | approval既有deny计数/escalation、受控secondstage；stage1非allow正常推进，不当作失败；有效最终deny不重试 | 工程 covered |
| 9 Codex风险/授权/检查（110–113） | codex:93–99,108–150,194–226 | 只读host tools、never approval、exact action；native fork/只读 retained；本轮parser/admission/security/owner通过 | 工程 covered |
| 10 最终deny、永久错误（115–118） | recovery:28–43；codex:142–150 | AUTH/QUOTA优先、SERVER非503已知状态不泛化、未知/ABORTED无盲重试；真 IM401/deny retained；独立模型/low不切换 | 工程 covered |
| 11 主动停止（122–125） | recovery:66–70,178–196；codex:127–134,178–192；approval:147–150,175 | backoff/同tick取消；真实native忽略signal12秒的raw iterator quarantine约14.19秒本轮通过；4真IM stop retained；**audit await窗口见W1** | 执行安全 covered；终态追踪偏离 |
| 12 非主动单次超时（127–130） | recovery:175–204 | 每attempt独立signal与budget，父取消优先，完整预算/新session/默认30/90导出；不能用dispose/idle代替raw drain | 工程 covered |
| 13 有人值守耗尽（134–137） | approval:78–85,100–107,152–160 | `review-audit` ask、技术不可用no_verdict不增安全拒绝；真 IM实际permission deny retained | 工程 covered，非完整Q |
| 14 Global/child耗尽（139–142） | approval:79,83,104–107 | facade直接覆盖return_to_agent及child不借allow配置扩权；origin/路由未改 | 工程 covered；完整真IM Global/child **Q待覆盖** |
| 15 schedule/heartbeat allow/deny（144–148） | approval:82,104–107 | `review-audit`分别allow/deny、persist失败不allow、cancel不fallback；只沿既有配置 | 工程 covered；真实触发器旅程 **Q待覆盖** |
| 16 可区分尝试/新call/模型/成本（152–155） | recovery:11–26,73–118,139–145,211–215；`policy/audit.ts:4–23`；approval:158–174 | reviewId/callId/attempt/request、bounded100 summaries、unknown/partial usage、optional旧行；**最终取消只剩allow trace，W1** | **WARNING** |
| 17 真全局插件旅程与受控证据分别交付（157–160） | 长期真IM驱动:160–377；progress:78–87,118–138 | 作者真实vendor无故障旅程和fixture分开；真实vendor不是故障恢复证明；Codex负数偏差已披露；静态review不替代独立观察 | **独立Q待完成，不假造闭环** |

### 626 与其他关键回归契约

| 契约（design:56–62、runbook§5.2） | 实现/测试定位 | 核对 |
|---|---|---|
| 普通PA `pa.authorization=0`，有效历史不从库复活 | approval:137–145 无全库查询；classifier:14–22；codex:86–99；`personal-security`、`approval-retry-native:64–78` | 本轮通过；现有独立PA入站/披露链不修改、不删除 |
| 技术恢复冻结rows，不重标live/restored | approval:72–75保留epoch规则；codex:93 restore(false)仅规范化；classifier准备一次；`review-source-recovery`四例 | 同/跨epoch、legacy host_context_live、原restored、sender/page/reply/迟到新历史冻结均覆盖；这些是source seam测试，不冒称完整真实委派旅程 |
| 同call正文去重/distinct call/message粒度/cursor | `policy/sources.ts:20–27,175`未变；codex:93–100以规范化serialized前缀判断 | `approval-sources:137–147`与source恢复测试通过；每message来源保留，不将projection当授权解释器 |
| current admission：required/preserve/recovery | codex:108–119；`codex-context.ts:86–130`未变 | delta传false；full/初次full/context/full恢复默认recovery；required/action放不下即失败；无0.65缩放；parser/admission测试通过 |
| parser是语义owner | `codex-context.ts:10–26`未变；codex:142–143 | bare allow/deny、embedded/default risk/auth/rationale均按626；非法outcome/enum/type才格式失败；不恢复四字段强制/额外critical-allow禁令 |

## Coherence

| design 决定 | 遵守 | 代码与证据 |
|---|---|---|
| action级窄controller，不循环整个facade/不重复工具体 | 是 | approval:132–145只建一个recovery，run只驱动判断；classifier跨stage共享controller |
| 首次Guardian cache/delta/fork，失败clean full；context rebuild≤1/action | 是 | codex:79–104,151–165；recovery:157–160；lifecycle/owner tests；失败fork不发布/清除另一成功trunk |
| 5秒raw drain/quarantine，creation signal/late handle只能清理 | 是（本轮真实native重验） | recovery:79–103；codex:169–235；真实uncooperative iterator测试，而非以whenIdle/dispose证明底层完成 |
| 全局唯一stream分派、先public marker+exact native sessionId，非所属/main/CC/purpose透明 | 是 | `llm-attribution.ts:70–83`唯一listener，codex:45–55先身份过滤；index:107–117接线；owner barrier实际I/A/B/C/D/M，D/M同主session，通过 |
| request-local HTTP facts/usage/generation不串；不记录body/credentials | 是 | attribution:8–32,40–64；recovery:73–118；capture attempt后不再读可变entry；失效sink inactive，owner tombstone等待raw drain后移除 |
| Retry-After秒数/date/unknown；>10秒不截短提前请求 | 是 | attribution:28–32；recovery:199–207；native真HTTP date、invalid、EOF；fixture longdelay retained |
| DSH只公开exports，不fork/patch/第二loop | 是 | 新增imports均公开根/已声明estimate/client；真实Agent create/scoped request-error/loop marker复用；lock/config/依赖拓扑无改动；Python runtime contract证据retained |
| 审计v1兼容、cancel/no_verdict不当安全deny，trace先落盘再fallback | 部分 | audit optional recovery + legacy schema本轮通过；persist失败不走allow；**W1：成功verdict写入后的取消没有终态补记** |
| 现有fallback/独立模型/权限不变，无新fail-open | 是（工程层） | route逻辑及native never/inspection限制保留；facade各模式allow/deny通过；完整模式产品旅程仍待Q |

### Prototype / Reference Contract

N/A。没有客户端面或视觉原型契约；本报告不做产品可用性或视觉判断。trace是持久终态/domain/session.observe数据，不声称Work新增attempt UI，也不保证进程突死前未落盘记录。

## Issues

### CRITICAL

0。尚未收到独立Q结果是明确的未完成外部门禁，不伪装成已验证缺实现，也不能据此签M1完成。

### WARNING

**W1 / CONFIRMED — 取消跨越判定审计持久化时，已封闭trace仍声称最终allow。**

- 契约：design.md:201–203 要求主动取消有不增deny计数的审计、终态事实可由session.observe检查；spec.md:150–155要求准确最终结果和路由。
- 位置：`packages/dsh-integration/src/policy/approval.ts:165–175`，重点L175。先finish('allow','allow')并await record，然后检查取消直接return cancel；没有同reviewId的取消事实。
- 触发：有效allow已到达，父stop/取消发生在storageDomain update等待期间。并不要求provider不合作或人为扩大权限。
- 直接复现：在 `packages/dsh-integration` 以 `node --input-type=module` 导入本次build的 Context/NanoApproval；仅stub config、ccApproval有效allow与storageDomain。storageDomain update调用真实父AbortController.abort()后返回更新结果。stdout得到 `result={kind:'cancel'}`，唯一row为 `source='classifier_allow', decision='allow', recovery={terminalReason:'allow',finalRoute:'allow',complete:true}`，没有cancelled行；命令exit0。这个同步注入位于被await的update调用内，直接覆盖相同状态边界。未执行bash工具体，不宣称取消后副作用发生。
- 根因：检查和持久化不在同一终态协议内，L147–150只处理审查结束前观察到的取消，无法覆盖其后audit await。
- 可执行建议（交原实施者，不由reviewer修复）：保留模型verdict事实，同时追加/持久化同reviewId的最终cancel，不把sealed planned allow当最终路由；测试在持久写入前后分别取消并比较返回、audit、零副作用；并核对no_verdict/fallback写入期间的同类窗口。
- 追加核验：首个探针和明确代码路径已足够确认普通finding，不需额外候选reviewer。第二个以外部deferred gate加强的探针被本会话工具门禁拒绝，未执行；未重试/绕过。这不是候选产品测试结果，不计pass或源码bug证据。

### SUGGESTION

0。不以风格、文件数或可选维护偏好凑finding。

## Delta 核对

本轮是 full，不是 corrected-delta。active delta `specs/gateway/agent-capabilities.md` 的新增恢复契约和modified既有fallback/独立模型/legacy单阶段语义与工程实现基本对应；W1仍是可检查终态事实的implementation-mismatch，不能静默改spec降格为planned allow来放行。尚未做最终sync/corrected-delta/canonical归并，不外推这些收尾门禁已完成。

## 现场、清理与交接

- 本人creator-owner创建前已核对：目标绝对路径不存在，`refs/heads/review/feat-625-r1`不存在；主workspace在main且原有`.claude/skills/.usage.json`、`.worktrees/` untracked保持不动。创建独立branch/worktree于validated_at，不动作者冻结现场。
- 自建worktree：`/Users/czj/.nanoassistant/workspaces/nano-engineering/.worktrees/review-feat-625-r1`；branch：`review/feat-625-r1`。**保留续验**，当前owner为本独立reviewer；父E可收集报告commit后将修复交原实施者，再续此reviewer核对受影响范围。未删除未知目录或清理作者数据。
- 本轮无IM/Gateway长驻服务；native测试自建temp runtime/HTTP server，在各finally shutdown/close。所有本会话后台安装/build/tests jobs均已收集结束；没有需要移交的运行job。
- 只提交本目录两份报告；未推共享unit分支，未merge/deploy/release。agent-scope async-boundary-validation只沉淀可复用的持久化取消观察方法，不含本unit进度。
- 父E下一步：将W1原文/版本/复现交原实施者，先修复并冻结新SHA，再按实际delta复验；Q补独立17场景/模式入口与真实插件限制；最后才能判断sync/CI/canonical/archive/Ready PR。不将本报告FAIL或工程retained证据说成全门禁pass。

---

## Round 2 — targeted-closure（W1 与相邻持久化窗口）

### Summary / 版本

**Verifier verdict: PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION（本轮 targeted-closure）。W1 closed。** R1 的历史 FAIL 与 finding 原文保留，不回写；本轮不是重新 full，也不是独立产品 Q 或 Ready PR。

| 字段 | 固定值 |
|---|---|
| review_round / verification_mode | 2 / targeted-closure |
| code_review_modes | patch + closure，完整修复 delta，不扩大审整条 unit |
| validated_at | `3dbfac7689a959b7a33106631bafd4f7975a9ae8` |
| executed_base | `861b94129bc8c5aadbca76967268fd203fe04112`（Full 的原始 base，不替换为 pre-fix） |
| pre_fix_head / finding_origin_head | `4c20949e5e6995944f35217177950e14dfdf67da` |
| fix_delta_range | `4c20949e5e6995944f35217177950e14dfdf67da..3dbfac7689a959b7a33106631bafd4f7975a9ae8` |
| fix_implementation_sha | `db8bc8201badf734fa7bde25bcd27a00b09128fe` |
| prior_reports | `code-review.md`、本报告 Round 1；原提交 `ce3d08fc212e94c5dc18cccdceeb97ab86ba3b7f` |
| report integration | `7beeaf72e` 的 R1 两份报告与原 ce3d 报告 byte-identical（Git diff exit0） |
| effective_base / effective_through | **未建立**，没有 final sync；本轮 retained 仅限固定输入间差异，不外推 main |
| requires_full_verification | **false**；修复影响保持在同一 facade 的取消/审计终态，相关权限与 native 边界已复验，无需重开全量验证 |
| independent code-review output | `code-review-r2.md`：JSON finding 数组 `[]`；closure状态与证据如下 |

### Code review patch + closure

| Focus finding | 原位置与确认状态 | 本轮 closure | 依据 |
|---|---|---|---|
| R1-W1 / P2 | 原 `policy/approval.ts:175`，CONFIRMED | **closed** | 新 `approval.ts:100–118,167–179,185–197` 在取消后 await 同 reviewId 的原子终态更新；持久化前/后双 gate 独立通过 |

Patch 范围包含全部5个文件：两份原报告集成、progress证据追加，以及 `approval.ts` 和 `review-audit.test.ts` 实质修复。没有存活 finding，无 still_open/superseded；未发现相邻 no-result/fallback/escalate 路径的新 correctness 问题。不是按作者的“已修好”声明关单，而是核对代码和独立运行冻结版本长期测试。

### Completeness / Correctness

本轮闭环 spec.md:122–125 的取消语义、spec.md:150–155 的最终路由/用量追踪、design.md:193–203 的原审计事实/取消终态/落盘失败边界；原17场景与M1其余映射沿R1 retained，不重写为新full结论。无 prototype/reference 改动，must-match **N/A**。

| 受影响契约 / 窗口 | 实现位置（`packages/dsh-integration/src/`） | 独立证据 / 状态 |
|---|---|---|
| 模型 allow 或 deny 已返回，持久化前 copy / copy后update仍pending时取消 | `policy/approval.ts:185–195` → `100–118` | `review-audit.test.ts:80–120` 的 model allow/deny × before/after gate；返回cancel、原模型判定保留、唯一详细trace改为cancelled/cancel、linked取消行各1，**covered** |
| no-result 第一条详细审计 pending，尚未进入allow或ask fallback | `approval.ts:171–180` | unavailable before unattended allow / interactive ask × 双gate；只两条row，取消未进入fallback，**covered** |
| unattended allow/deny、Global return_to_agent或有效deny阈值escalation的第二条记录pending | `approval.ts:120–127,188–197` | 四类第二写入 × 双gate，返回cancel；唯一详细trace纠正实际终态、未发生fallbackOutcome清除，**covered** |
| 早取消与普通backoff取消 | `approval.ts:167–169`；cancelReview的initial参数 | 无历史trace时原位写一条详细cancel行；既有backoff测试继续通过，**covered** |
| 保留模型判定/metadata/attempt/request/usage，取消不重计usage或增deny | `approval.ts:108–116` | map保留原entry并仅改recovery终态字段，嵌套attempt/usage与metadata不重建；测试explicit fixture knownUsage 7/3仍在原trace，新行无recovery/usage，counts与前行相等；**covered** |
| cancel终态写入失败必须reject，不能allow或伪装已完成写入 | `approval.ts:105–118`，调用方await/返回其Promise | `review-audit.test.ts:123–133` deferred gate + 第二次写入报错；独立执行reject测试通过；已有首次存储失败no-allow测试保留，**covered** |
| 终态幂等和manual路径 | `approval.ts:103–104,113` | reviewId限定修改，已有cancelled行则不追加；无自动reviewId维持manual取消路径；静态可直接核对，旧manual/native权限回归通过 |

精确持久化窗口的证明层级是 **facade + schema/storage seam 的长期测试**：真实父AbortController仅在deferred gate已进入后abort，gate位于schema解析copy前和copy后/update resolve前，测试还断言facade没有提前settle。测试中的effects是允许返回计数，不是声称真实工具执行。真实native HTTP/业务副作用由相邻integration回归另行保护；没有将本轮测试冒称真IM storage故障注入。

### Coherence / 失效与 retained 判断

- **失效并重验：** R1-W1、模型verdict/no-verdict/fallback/escalation的审计取消窗口、终态写入失败、计数/usage及旧fallback相关结论。原行仍保留模型判定，取消事实通过同reviewId终态/新增行表达，不抹除已发生的安全deny计数；无新fail-open。
- **实现范围实核：** Git确认 `db8bc820..3dbfac -- packages scripts tests` exit0，validated tree 与fix源码/测试一致；`4c209..3dbfac` 除approval.ts/review-audit测试和3份报告/progress外无变化。旧报告集成不会变更其历史结论。
- **R1 full retained：** recovery次数/30–60–90预算/prepare15s/action360s/cleanup5s、Retry-After、唯一global dispatcher/HTTP sink、exact-owner身份/缓存fork隔离、raw iterator drain、Guardian clean full/context≤1、626来源/零全库读取/admission/parser、独立模型/检查权限、DSH公开exports/依赖锁和current/unit specs均未改。通过精确path diff exit0和本轮受影响回归支持保留；没有将90秒×3、默认30/90超时、owner并发HTTP及parser旧证据说成重跑。
- **外部门禁仍保留限制：** 本轮不兼Q。Global/child/schedule/heartbeat完整真IM故障旅程、真实双策略插件独立验收和Codex负数clamp旅程限制不因W1 closed而补成pass；父E需结合Q另行报告判定。最终sync/CI/canonical/archive/Ready PR仍不在本轮结论内。

### 独立命令 / 结果

全部命令在新建本人R2 worktree运行，未进入作者现场或重新执行上轮被拒的自定义probe。

| 命令 | 退出 / 结果 |
|---|---|
| `pnpm install --frozen-lockfile` | 0；锁文件不变，Node v25.8.2 / pnpm11.7.0 / frozen DSH0.2.1-alpha.1 |
| `pnpm --filter @nano/dsh-integration... build` | 0；编译本轮product-contracts + integration产物 |
| 下列9文件 `pnpm exec vitest run ...` | **0，9 files / 94 tests，25.83s**；其中audit27条（含16个双gate窗口及终态写入失败），真实native quarantine约13.78秒、真HTTP三策略15条均通过 |
| `pnpm --filter @nano/dsh-integration typecheck` | 0 |
| `git diff --check 4c20949..3dbfac768` | 0 |
| `git diff --exit-code ce3d08fc2 3dbfac768 -- <R1两份报告>` | 0；R1历史原文一致 |
| `git diff --exit-code db8bc820 3dbfac768 -- packages scripts tests` | 0；fix frozen identity |

```sh
pnpm exec vitest run \
  packages/dsh-integration/tests/review-audit.test.ts \
  packages/dsh-integration/tests/approval.test.ts \
  packages/dsh-integration/tests/approval-workspace.test.ts \
  packages/dsh-integration/tests/approval-retry-native.test.ts \
  packages/dsh-integration/tests/review-quarantine-native.test.ts \
  packages/dsh-integration/tests/personal-security.test.ts \
  packages/dsh-integration/tests/approval-sources.test.ts \
  packages/dsh-integration/tests/review-source-recovery.test.ts \
  packages/dsh-integration/tests/review-recovery.test.ts
```

作者progress:143–169的有版本/命令证据只作补充：红测17failed/10passed→修复27绿；workspace8项目typecheck、9/94、真IM受影响6passed/2deselected、contract28/docs-check通过。本轮独立确认9/94与integration typecheck；**未重跑作者真IM6条/全workspace typecheck/contract/docs-check**。真IM6条不包含storage gate，其精确窗口由上列长期测试承担；本轮无工具拒绝或测试失败。

### Issues / 交接现场

- 本轮 **0C / 0W / 0S**，validated_issues：W1 closed；无需追加独立候选核验。两份静态输出分别为本R2段与`code-review-r2.md`的`[]`，不覆盖R1 JSON finding。
- R1 worktree先核clean，HEAD=`ce3d08fc2`不是3dbfac祖先（`merge-base --is-ancestor` exit1），原因是父branch cherry-pick报告造成历史分叉；没有尝试非ff merge、解决冲突或覆盖R1。按caller预授权fallback，先核绝对目标不存在/branch不存在后，新建 `review/feat-625-r2` 于3dbfac。
- R2保留续验：`/Users/czj/.nanoassistant/workspaces/nano-engineering/.worktrees/review-feat-625-r2`；R1保留原报告commit/现场不动。两现场owner仍为本独立reviewer，父E收集报告commit后可续同会话；无自动删除。
- native测试自有temporary runtime/HTTP均按finally关闭，进程模式复查无本轮残留；唯一后台安装/build/tests job已结束并收集。没有启动IM/Gateway长驻服务。
- 只提交R2 JSON与本报告追加段，不改源码/测试/配置/设计，不推共享unit分支，不发公开、不改团队图、不派worker、不merge/deploy。请父E整合报告并维持其他独立门禁与final-sync版本边界。
