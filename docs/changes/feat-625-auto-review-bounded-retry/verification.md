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

---

## Round 3 — targeted verification of Q recovery test facilities

### Summary / 版本与范围

**Verdict: FAIL — 0 CRITICAL / 1 WARNING / 0 SUGGESTION。** 新增native证据导出错误会跳过runtime关闭，见R3-W1；未发现新的产品实现缺陷，R2-W1 closed与未变化产品范围retained。`requires_full_verification: false`，不需因此重新full审整个unit。

| 字段 | 值 |
|---|---|
| validated_at | `2f519f659b114003d35f2fcc2305469f6e40962c` |
| pre_fix_head / patch_base | `afd71206deb2220b0cddcd7840588667b62340e5` |
| executed_base | `861b94129bc8c5aadbca76967268fd203fe04112`（原Full base） |
| code_review_mode / verification_mode | patch / targeted（新增fixture、真实入口、断言、导出与清理；不兼Q） |
| diff_range | `afd71206deb2220b0cddcd7840588667b62340e5..2f519f659b114003d35f2fcc2305469f6e40962c`，9文件 / +1028 -23 |
| independent output | `code-review-r3.md`，JSON数组1条P2 CONFIRMED；本段为独立verifier输出 |
| effective_base / effective_through | 未建立，未final sync，不外推最新main或后续修复 |

读取全部9文件变更与周边调用：`M1-review-recovery/q-r1-recovery.md`、progress171–182、runbook§5.3、native optional导出、两个Python fixture、context/source新驱动及原retry驱动变更。保留R1/R2原报告、Q acceptance R1历史FAIL。Git实核afd..2f519的产品源码/锁文件无差异，`3dbfac..2f519 -- packages/dsh-integration/src`亦exit0；没有修改设计/spec来迎合测试。

### Completeness / Correctness / Coherence

| 本轮设施/契约 | 实际边界与断言 | 结论与限制 |
|---|---|---|
| context rebuild → 503 → fresh full → 下一delta | `test_auto_review_context_recovery.py:22–127`发送3条IM消息；fixture返回真实400/503 HTTP，断言5次请求序列、真实session I/I/R/F/F或失败后新full、共享context1/retry1、full旧证据/下一delta非重复及实际文件行数 | 接线与断言非循环：计划只控制HTTP响应，session/trace/effect来自运行时。未预写审核domain或controller。fixture HTTP不是vendor故障，本轮静态核对，不替代Q现场复验 |
| required action admission | context驱动:130–197用公开review window 20000与完整工具参数，断言context_required/0retry/0review HTTP/0效果、真实permission deny | action体积由模型fixture输出，不patch tokenizer/admission；无HTTP用记录端独立观察，不能只靠作者terminalReason证明 |
| 626真绑定PA/direct/PTC/restart/compact | `test_auto_review_source_recovery.py:61–245`真实新绑定、公开config/tool/plugin安装、真实Gateway restart或/compact；数据库仅mode=ro观察未消费消息，未插入Inbox/observation/审计 | `auto_review_source_scenario.py`只产公开tool calls，cursor取实际tool_result，compaction engine输出明确为受控模型摘要；summary是受控内容，不伪造宿主compact事件。原本missing markers时仅source-mode唯一case回退，未由正文生成source权威 |
| 来源冻结与去重 | source驱动:246–331读取真实reviewer HTTP messages，再解JSONL；比较首次与recovered行并分别断言owner/type/part/distinct-call/live/restored/sent/held/PTC-id和原文去留 | 首次==恢复仅证明冻结，显式行断言才证明源语义；两者组合不是自制expected行预灌。compact检查旧id/正文/旧proposal缺席、新live页与summary存在；库外消息真实创建却未观察，不应泄入。没有声称覆盖全部reply/observer/admission组合 |
| stop/cancel持久化 | retry驱动新增complete=true、terminalReason=cancelled、finalRoute=cancel、行allow不存在、总/连续计数0、跨backoff期限无新HTTP/无效果；完整approval/request导出 | 可作为真实stop边界保护；**不等同命中storage await窗口**。精确窗口仍由review-audit双gate承担，本轮27条通过；R2 closure retained |
| 隔离与原始证据 | `running()`仍使用tmp root + e2e-up/down、独立config/DB/workspace/identity、fixture127.0.0.1随机端口；source workspace验证在栈根内；restart仅对应隔离config。raw messages/system/observation导出只应保留gitignored本地 | 没有新增产品公共日志或原始prompt提交。fixture docstring的“sanitized”不可被当成无prompt保证：新增records确有完整messages/system，按用户要求本报告不引用内容、不提交原始数据。报告命令均为本地locator/脱敏事实 |
| native证据可选导出与失败清理 | `codex-approval-native.test.ts:87–104`新增finally中，在shutdown前await mkdir/writeFile | **WARNING R3-W1**；正常输出绿测不能证明不可写/路径错误分支，见下 |

### Issues

**R3-W1 / WARNING / CONFIRMED（code review P2）：opt-in证据导出错误绕过native runtime关闭。**

- 位置：`packages/dsh-integration/tests/codex-approval-native.test.ts:90–94`，及L98–104。契约：AGENTS工作红线、worktree-runtime.md:19要求启动者关闭自己的进程；导出是可选观察，不应改变原测试finally的清理可靠性或覆盖原始失败。
- 触发：`NANO_REVIEW_NATIVE_EVIDENCE`指向已存在普通文件、不可写目录，或mkdir/writeFile出现磁盘错误。L90/L92抛错会跳过client.shutdown与home删除；L98/L101抛错也会跳过home删除。实际native Agent/runtime已在try中启动，因此存在明确资源泄漏路径。
- 独立复现（exit0）：读取冻结文件完整新增finally块，用AsyncFunction执行原块，仅注入记录调用的fake client/fs（没有运行真实子进程）；mkdir按普通文件场景抛EEXIST。断言唯一事件为`mkdir`，shutdownCalled=false、homeCleanupCalled=false。该probe只确认可执行控制流，不冒称留下过真实进程或provider超时；无需重跑90秒×3才能确认。
- 建议交原实施者：导出包裹嵌套try/finally，保证失败时仍shutdown并清理自建home；尽量保留原始测试失败、单列导出错误。回归至少覆盖导出目标错误/写入错误，不仅成功文件导出；不需改生产或放宽timeout。
- 这是测试设施finding，不重开已closed产品W1。没有未证实高风险条件，不需追加独立候选核验。

### 独立命令与证据

| 命令 / 检查 | 本轮结果 |
|---|---|
| `pnpm install --frozen-lockfile` | exit0，依赖锁未改 |
| `pnpm --filter @nano/dsh-integration... build` | exit0 |
| `pnpm exec vitest run packages/dsh-integration/tests/review-audit.test.ts packages/dsh-integration/tests/review-source-recovery.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts` | **3 files / 38 tests passed，1.12s，exit0**（27 audit / 4 source / 7 lifecycle） |
| exact-finally控制流probe（上述R3-W1） | exit0，清理跳过已确认；未创建真实runtime |
| Python 3.11.13 `compile(text,path,'exec')`五个改动Python文件 | exit0，无pyc输出；328/204/197/331/398行，语法通过；不是pytest或ruff结果 |
| `git diff --exit-code afd..2f519 -- <产品src/锁>`及`3dbfac..2f519 -- integration/src` | exit0，产品树不变，R2 retained的直接版本依据 |

工具环境探测时`command -v python3.11/uv/ruff`退出1（PATH未提供，系统python3是3.9.6），已使用glob定位本机稳定Python3.11.13做无写入syntax检查；未使用临时uv下载目录或系统3.9运行产品测试。没有将该环境探测失败当产品失败。

本轮**未重跑**真IM context3/source12、native90s×3、stop6、contract/ruff/docs-check；作者在q-r1-recovery.md/progress记录的实际命令、wall time与本地导出为工程retained evidence，不是本轮独立结果或Q通过。原Q的宿主sleep时间关联及awake复跑是有界环境诊断输入，静态本轮不反推全部超时皆非产品问题。Q正独立并行续验，结论回父E；原Q插件负例事实归属于Q自己的产物，不再将作者另一clamp示例泛化到它。

### 现场与交付限制

自建前核对新绝对路径/branch不存在，新建于validated_at：`/Users/czj/.nanoassistant/workspaces/nano-engineering/.worktrees/review-feat-625-r3` / `review/feat-625-r3`；本人为owner，**保留续验**。R1/R2旧现场与原报告未动。只提交本R3 JSON和verification追加，不改产品/测试/fixture/设计；不push unit、不Inbox/conversations/taskgraph/公开消息、不派子agent、不canonical/archive/PR/merge/deploy。唯一后台install/build/tests job已结束收集，无启动IM栈，无需交接运行服务；没有创建或公开raw prompt/DB/config证据。父E请将R3-W1交原实施者修复，修后按新增导出失败影响范围复验，不因测试设施修复失效整个产品full。

---

## Round 4 — targeted closure of native evidence cleanup

### Summary / 版本与范围

**Verdict: PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION（本轮targeted范围）。R3-W1 closed。** 原R3 FAIL与finding原文保留，不追改为PASS；原产品R2-W1 closed及full未受影响范围retained。没有以本轮设施closure替代独立产品Q、corrected-delta、final sync、CI或Ready PR门禁。

| 字段 | 值 |
|---|---|
| validated_at | `89f2a20da49e3d3741b47fede35b33bb06893f3d` |
| pre_fix_head / finding_origin_head | `2f519f659b114003d35f2fcc2305469f6e40962c` |
| executed_base | `861b94129bc8c5aadbca76967268fd203fe04112`（原Full base，不改写） |
| code_review_mode / verification_mode | patch + closure / targeted-closure |
| fix_delta_range | `2f519f659b114003d35f2fcc2305469f6e40962c..89f2a20da49e3d3741b47fede35b33bb06893f3d` |
| substantive patch | `3ba1e3539..89f2a20da`：native测试、tests helper、错误路径长期测试、progress，4文件 / +193 -20；此前仅整合原R3报告 |
| focus_findings / validated_issues | R3-W1（导出失败跳过runtime关闭与home清理）/ **closed** |
| independent code-review output | `code-review-r4.md`，JSON `[]`；此段为独立verifier输出与closure说明 |
| requires_full_verification | **false**；本轮不影响共享产品边界，无需重新full |
| effective_base / effective_through | 未建立；没有final sync，不外推后续SHA或main |

完整读取4文件patch、新helper及实际native调用方，并核对AGENTS、testing.md、worktree-runtime.md:14–21的进程所有者清理契约。先前Full契约和current spec核对沿R1/R2 retained；本轮无产品/配置/spec/design改动，没有静默修改契约迎合实现。Prototype / Reference：N/A，无前端变更。

### Completeness / Correctness / Coherence

| 关联契约 / 触发 | 实现与长期保护（均在 `packages/dsh-integration/tests/`） | 核定 |
|---|---|---|
| 前置mkdir / observation写入失败不能跳过关闭 | `native-review-evidence.ts:22–35`将导出拒绝记为diagnostic，finally仍调用shutdown；`.test.ts:30–44`注入两种前置故障 | covered；不吞故障换绿 |
| 后置mkdir / fixture读取 / 写入失败仍清理home | helper:37–52嵌套finally保证继续尝试rm；只有ENOENT代表缺失文件，其余读取错误传播为fixture export diagnostic；tests:30–44、101–111覆盖后置三类失败与缺失文件 | covered；不把磁盘/权限读取故障伪装成缺文件 |
| shutdown拒绝不能阻止home清理；rm拒绝必须报告 | helper:34–52按阶段捕获；tests:30–44覆盖shutdown、rm拒绝，57–64同时导出/关闭拒绝仍到rm | covered；只证明调用与错误可见，**不是shutdown失败时进程也已退出** |
| 原错误身份、附加故障与多错误保留 | helper:55–59无附加故障重抛原对象；有附加故障AggregateError以原错误为首项及cause，其余保留阶段标签/原cause；tests:30–64、88–93 | covered；原native catch仍用原有日志/observe包装，`codex-approval-native.test.ts:87–94`只是将该错误传给finally，不改业务assertion |
| 成功测试遇导出故障仍失败 | helper:55–57即使无primary也抛AggregateError；tests:47–55 | covered；非best-effort静默通过 |
| 输出目标不得误删 | helper唯一rm参数为调用者新建home（:50–51）；实际调用方:10、90–93传入本测试mkdtemp根，evidence只用于mkdir/write | tests:66–85用**真实fs普通文件目标**触发两次EEXIST，home stat为ENOENT、输出文件原文不变；shutdown是计数替身，不是实际runtime |
| 无opt-in与成功顺序保持 | helper:28、39跳过导出，不跳过shutdown/rm；fixture复制在shutdown后；tests:95–111 | covered；原native预算320000及默认90秒×3、assertions均不变 |

提取逻辑只存在tests辅助模块，不进入产品exports/运行时，不新增DSH private import、fork/patch、第二loop或公共日志。长期测试落在能注入fs/shutdown拒绝的最低测试设施seam；真实fs用例补充输出目标保护，不与产品HTTP/IM旅程重复。注入测试记录的shutdown与rm是接口调用/错误控制流证据，不等同完整native测试或真实进程退出证据。

### 独立命令与证据

全部在本人新建R4 worktree，冻结HEAD=validated_at；Node v25.8.2 / pnpm11.7.0 / frozen DSH0.2.1-alpha.1。

| 命令 / 检查 | 本轮结果 |
|---|---|
| `pnpm install --frozen-lockfile` | exit0，锁文件不变 |
| `pnpm --filter @nano/dsh-integration... build` | exit0，product-contracts + integration编译 |
| `pnpm exec vitest run packages/dsh-integration/tests/native-review-evidence.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts packages/dsh-integration/tests/review-audit.test.ts` | **exit0，3 files / 47 tests passed，2.78s**（13 cleanup / 7 lifecycle / 27 audit） |
| `pnpm --filter @nano/dsh-integration typecheck` | exit0；按包tsconfig检查src，不宣称此命令另行typecheck了tests |
| `git diff --exit-code 2f519f659 89f2a20da -- <integration/src、product-contracts、apps、PA、channels、pnpm-lock.yaml>` | exit0；产品树/锁未变，原产品R2 closure与R3产品retained的直接版本依据 |
| `git diff --exit-code 29dc06f7c 89f2a20da -- <code-review-r3.md、verification.md>` | exit0；原R3两报告逐字保留（追加本段之前） |
| `git diff --check 2f519f659..89f2a20da` | exit0 |

作者progress:184–194的红测9fail/3pass→13pass、contract28/docs-check252为带版本/命令的补充工程证据，**不是本轮独立重跑结果**。本轮未启动native/IM，也未重跑90秒×3、全部真IM、contract或docs-check；对本finding所需的异常控制流与真实fs输出保护已有直接证据。Q在其独立现场续验，结论不由本静态报告代理；本轮不重新判定此前产品旅程事实。

### Issues / 交接现场

- **0C / 0W / 0S；R3-W1 closed，无still_open或superseded项，无需追加独立候选核验。** 原产品R2-W1不重开；其他Full契约只保留适用证据，不称本轮全部重新执行。若后续产品源码、helper调用契约或预算改变，应按实际影响重判门禁有效性。
- 创建前确认绝对路径和branch均不存在，创建于冻结SHA：`/Users/czj/.nanoassistant/workspaces/nano-engineering/.worktrees/review-feat-625-r4` / `review/feat-625-r4`。本人creator-owner，**保留续验**；R1/R2/R3现场、原报告和作者冻结现场未覆盖。
- 两个后台安装/build/tests jobs均exit0且已收集；本轮没有启动IM/Gateway/native runtime或遗留自建服务。真实fs回归仅建立并自行清理测试临时目录，不创建raw prompt/DB/config产物。
- 只提交R4 JSON与verification追加段，不改源码/测试/配置/设计，不push共享unit、不Inbox/conversations/taskgraph/公开消息、不另派worker，不canonical/archive/PR/merge/deploy。父E收集报告commit后整合；报告commit本身不改变validated_at或建立effective_through。

---

## Round 5 — final integration patch + corrected-delta

### Summary / 固定版本与门禁分离

**独立 code review：`code-review-r5.md` = `[]`，未发现有直接证据的存活实现缺陷。Corrected-delta：aligned，18/18完成实现/长期测试映射，无delta-mismatch或implementation-mismatch。但verifier不能给PASS：0 CRITICAL / 1 WARNING / 0 SUGGESTION。R5-W1是未建立的集成运行证据，不是已确认产品bug。** 不将超时直接当作产品缺陷，也不删去失败后用作者烟测或旧R4补成新栈PASS。

| 字段 | 值 / 限定 |
|---|---|
| validated_at | `22114489ba131fbf847b60e0a4ca730d61471796` |
| executed_base（本轮） | `18e1af8b1cd0834ae3f22f5780f2d50b740f5171` |
| 历史 executed_base | `861b94129bc8c5aadbca76967268fd203fe04112`，R1–R4不改 |
| review_mode / verification_mode | patch/integration / corrected-delta + targeted integration |
| ranges | main `861b94129..18e1af8b1`；集成 `6df263df3..f586ff450`；校正 `f586ff450..22114489b` |
| corrected_delta_result | **aligned**：目标投影、实现和长期测试一致，不等同本轮所有运行通过 |
| requires_full_verification | **true（受影响的共享集成边界仍需续验）**；不能保留旧栈整体Full有效性，不要求无差别重跑原unit所有组合，欠缺见R5-W1 |
| effective_base / effective_through | 仅code-review patch及静态corrected-delta映射核定为 `18e1af8b1..22114489b`；**verifier运行集成范围和整体effective_through未建立** |
| prior findings | 产品R2-W1 **closed**、设施R3-W1 **closed**；原FAIL与closure保留，不重开/改写 |

完整读取final-sync-handoff84行、delta113行全部18场景，复核approval/recovery/classifier/codex/context/sources/HTTP attribution及main的默认context/profile/features/mount、PA Global durable发送/Inbox/单线程、Channels realtime与IM receipt/status/permission identity真实调用链。current契约包括`docs/specs/gateway/agent-capabilities.md:231–262,516–604,804–857`、PA/IM/Channels相关spec、SPEC包边界及testing/worktree-runtime约束。Prototype / Reference：N/A，无前端must-match任务。

### 集成判断与版本证据

- 独立git确认merge `f586ff450` parents为`6df263df3`与`18e1af8b1`。相对6df263的`policy/approval.ts`只有contextTools import与internal_context分支/注释，cancelReview双gate/recovery未被覆盖。merge后到冻结SHA的packages/apps/src/scripts/tests/锁文件diff exit0。
- **未以625算法文件没变为由全retained。** 627/629改变默认context、有效history/pressure pruning、purpose和profile安装面；630/631/632改变同一PA入口live/restored、发送恢复及request-id/permission身份，已据此扩查和独立测试。旧Q只归其原SHA，父E另调Q，本报告不代Q。
- `agent-context.ts:4–5`精确四工具notes/history/new_context/get_context_remaining；`approval.ts:132–137`先downstream，非allow立即返回，再内部豁免。最后独立窄复跑三规则Auto-off的**root+child** context成功、显式context deny保留、业务工具不执行均通过，非任意白名单扩权。
- `codex.ts:45–55`在currentAttempt前检查公开loop、purpose及exact owner；`:199–225`独立reviewer preset、approval=never、空基础allow集+只读inspection guard、固定route/effort，不因默认插件获得父级业务权限。profile/mount及NanoCompaction ownsElsewhere分界已静态核查；新栈native owner/quarantine各1项通过。
- `sources.ts:131–182`以native deriveMessages有效表面为权威，PTC只补仍有效root子结果，不从durable Inbox复活已裁原文；跨进程epoch降级restored。`codex.ts:86–99`冻结证据，`:100–119,151–156`处理checkpoint差异、服务失败clean-full和一次context rebuild。进程观察保留的restoreEntries(false)不是跨进程live。
- PA `global-agent.ts:487–558`按operation identity取publication，检查target/body冲突，unknown/sending查询宿主状态，已有result返回，held不自动重发；与Inbox durable observation/wake/receipt、IM status访问检查一起保留sent/held/unknown差别。single-thread将业务permission身份保存在nested request，不被transport request-id覆盖；Channels pending/generation精确匹配ACK。Global44、single-thread9、web-relay12、IM message-attempts7/relay1/work9、PA work7等独立新栈分层通过，不冒称Q真实PA/source旅程全量复验。
- R4 helper、13个异常路径测试和native实际调用方三文件在`89f2a20da..22114489b` byte-equivalent（git diff exit0），R3-W1纯fs清理/原错误/输出目标保护closure具体retained；没有机械重跑90秒×3或将shutdown尝试说成实际退出。

### 全部18个delta场景映射

delta行号指`specs/gateway/agent-capabilities.md`；源码相对integration/src/policy，测试相对integration/tests。“通过”只指本轮实际结果，长期覆盖存在不等于本轮对应文件全绿。

| # / 场景 | 实现与长期保护 | 独立核定 / 运行边界 |
|---|---|---|
| 1 临时故障 L7–12 | recovery:168–208每次独立timer/共享trace，classifier30/60s，codex:102 90s | aligned；recovery25通过，完整预算/跨stage不重放有断言；native HTTP首次11/15通过、4超时 |
| 2 格式子额度 L14–17 | recovery:197–204额外2/format1；两个parser | aligned；recovery25/codex7通过，格式/服务混用不领新额度 |
| 3 取消/永久 L19–22 | recovery:28–52,170–198；approval:170–183,198；codex quarantine | aligned；audit27/lifecycle7/native quarantine1通过，有效deny/permanent/context_required不盲retry |
| 4 Retry-After L24–27 | recovery:199–207不截短>10s；llm-attribution请求局部sink | aligned；recovery/attribution/native owner通过；不称HTTP matrix全绿 |
| 5 模式/fallback L29–33 | approval:79–85,121–128,174–183，cancel优先、Global/child回父 | aligned；audit27证明cancel不fallback allow；approval首次4/6通过，缺口不隐去 |
| 6 审计/W1 L35–40 | approval:87–119,179–198；recovery:139–145,186–215 | aligned；audit27双gate/写失败不allow/未知usage与单次计数通过，原W1不重开 |
| 7 默认规则 L46–48 | approval原rules路由与CC工作区分支 | aligned；approval-workspace2通过，internal_context不是新增审核策略 |
| 8 来源/PTC L50–57 | sources去重/有效history/PTC root/epoch，codex冻结 | aligned；sources8/source-recovery4通过；新PA状态分层通过，真partial/live/restored仍另交Q |
| 9 CC超窗 L59–63 | classifier estimateContent+输出预留准入；typed超窗为context | aligned；不裁授权/不盲retry/不换模型；approval超窗native poll未达终态，R5-W1缺口 |
| 10 子任务 L65–68 | approval:60–70,79–85、runtime委派；context豁免在downstream后 | aligned；最后nano/codex/dsh三项root/child权限边界通过；personal-security首次4/6通过 |
| 11 配置切换 L70–73 | approval冻结config/exec/reviewer；codex fingerprint/release | aligned；workspace2/lifecycle7通过，迟到结果不发布旧cache |
| 12 模型失败 L75–79 | approval:153–168 reviewer固定；classifier共享recovery，Codex固定route | aligned；recovery/lifecycle与native HTTP11项通过，剩余真实HTTP需续验，不换执行模型 |
| 13 逐Agent继承 L81–84 | product-contracts/runtime既有rule解析，625无新选择器 | aligned；静态配置映射已核；model-policy首次1/5通过、4超时，不称新栈全过 |
| 14 下一轮 L86–88 | runtime替换边界、当前动作structuredClone、codex release | aligned；workspace2/lifecycle7通过；默认profile六Agent重启/opt-out最终仍30s timeout |
| 15 Codex可信现场 L92–95 | policy/sources/inspection只读、完整action、独立scope | aligned；codex7/sources8/native owner1通过，私稿/历史不变新授权 |
| 16 连续并发/恢复 L97–101 | codex:69–85,100–192成功checkpoint/clean-full；共享takeContextRebuild | aligned；lifecycle7/source4/native owner1/quarantine1通过，失败cancel不cache/fork归属有保护 |
| 17 证据预算 L103–107 | codex-context.reviewInput；codex:108–119,217–218 checkpoint不再裁 | aligned；codex7/lifecycle7通过，optional先去/required不裁/一次重建/不复活；非CC不裁路径 |
| 18 判定/失败 L109–113 | parseCodexDecision合法缺省/外围说明；approval终态/audit/recovery | aligned；codex7/audit27通过，非法outcome/enum/type才格式恢复，无判定不冒充allow |

ADDED1条+MODIFIED2条共18投影，不与首文档17旅程机械等同。默认context另一个Requirement保留，未被MODIFIED整条替换吞掉。完整预算、跨stage共享、取消事实/不allow写失败、CC typed超窗、Codex admission/parser校正均吻合实现；未发现静默改spec/design迎合实现。canonical未改。

### 独立命令与失败证据

环境：自建R5 worktree、冻结HEAD；Node25.8.2 / pnpm11.7.0、DSH0.2.1-alpha.1、context rc.5，与CI Node24/Python3.12区分。

| 命令 / job | 实际结果 |
|---|---|
| `pnpm install --frozen-lockfile`（bash-132） | exit0，锁未改 |
| `pnpm -r --if-present build`（bash-135） | exit0，8 projects；不是根pnpm build/build-node-release或远端CI |
| `pnpm exec vitest run --maxWorkers=2`下列30文件（bash-138） | **exit1，20 files passed/10 failed，218 tests passed/25 failed，600.70s** |
| 失败10文件 `--maxWorkers=1`（bash-149） | 观察到HTTP15/15与context5/5超时后主动取消剩余冗余native测试；**未完成/未通过**。取消后job_output unknown、job_list无job，不编造终态exit code |
| `pnpm typecheck`（bash-158第二命令） | **exit0，8 packages**；第一命令Python3.11 `-m pytest tests/contract/test_runtime_dependency_contract.py -q`因`No module named pytest` exit1，组合job exit1，不称contract通过 |
| `pnpm exec vitest run --maxWorkers=1 packages/dsh-integration/tests/agent-context-default.test.ts packages/channels/tests/realtime-window.test.ts`（bash-2，02:31较低负载） | **exit1，7 pass/1 fail，66.52s**；PA默认context、三规则root/child边界4项及realtime3项通过；六Agent初始化/opt-out/restart仍30s timeout |
| merge parents/approval diff、R4 helper3文件identity、merge后产品树identity、Channels相对新main identity、unit diff-check | 均exit0 |

30文件完整命令的续行表示（在bash展开花括号或逐文件列出）：

```bash
pnpm exec vitest run --maxWorkers=2 \
  packages/dsh-integration/tests/{agent-context-default,capabilities,history,knowledge,model-policy,workspace-tools,llm-attribution,review-recovery,review-audit,review-source-recovery,review-owner-native,review-quarantine-native,approval-retry-native,codex-approval-lifecycle,codex-approval,approval,approval-workspace,approval-sources,personal-security}.test.ts \
  packages/personal-assistant/tests/{relay-admission,personal-attention,global-agent,single-thread,external,work-sync}.test.ts \
  packages/channels/tests/{realtime-window,web-relay}.test.ts \
  apps/im-server/tests/{relay-delivery,message-attempts,work-sync}.test.ts
```

原批末尾`&& pnpm typecheck`因vitest exit1未执行，已独立补跑。25失败=22个整test超时（原15/20/25/30/90s），approval:310终态poll及capabilities:110非空结果poll未达两项，realtime-window:28累计frame7而非6一项。后者使用60ms ACK deadline，实现限制的是同时pending普通请求六个，超时释放slot后pump可使累计frame增加，未证明瞬时超并发；测试/实现与新main逐字不变，最后窄复跑3项通过，不报625新并发缺陷。其余timeout未观察到错误allow/来源扩权，但不能仅据此称无运行问题。

host事实：8 logical CPU，load曾177.57/137.60/128.89→694.61/443.52/266.16，最后窄复跑起点9.35/167.51/207.35。互不相关runtime用例同时越deadline，降低workers在高负载时未解决失败；这是环境压力强关联，**非证明全部失败唯一根因**。没有改timeout/fixture/assertion/产品预算/永久电源设置。作者9files73/29.31s与旧Q真IM/预算事实只按原版本/命令retained补充，不替代独立失败。

### R5-W1 / WARNING — targeted integration运行证据未建立

- **契约/位置：** 本轮final-sync targeted integration；current agent-capabilities:804–857默认context/profile/重启/有效上下文，delta L50–88、L97–107来源/冻结/配置。直接测试`agent-context-default.test.ts:9–68`、`approval.test.ts:66,310`、`approval-retry-native.test.ts:12`及失败的配置/history邻域。
- **事实：** 静态18项与长期保护齐全、native owner/quarantine/PA durable分层通过，但新栈独立批次仍25fail；较低负载复跑只补必要三规则权限边界/PA context/realtime，没有补齐profile/restart、CC超窗终态/HTTP matrix。没有证据判定implementation-mismatch，也不能把targeted退出标准记完成。
- **可恢复下一步：** 原执行者在稳定隔离现场，**同冻结版本/原期限**先独跑`agent-context-default.test.ts -t 'defaults new and existing Agents'`，再补approval、approval-retry-native及上述配置/history/capability失败邻域，记录初始化/插件切换/请求与终态/清理分段时间和onLog（不提交原始prompt/config）。仍超时则按公开RPC阶段定位，不加timeout；本独立reviewer核收后关闭R5-W1。新栈Q source/context/stop/真vendor仍交Q，不以工程绿测代理。
- **门禁：verifier NOT PASS，0C/1W/0S**。corrected-delta aligned及code-review `[]`可分别交接，不能据此canonical/归档/Ready PR或整体effective。WARNING不重开产品W1/R3-W1，不建议改spec掩盖失败。

### 现场与交付

本人创建并保留`/Users/czj/.nanoassistant/workspaces/nano-engineering/.worktrees/review-feat-625-r5` / `review/feat-625-r5`。旧R1–R4现场/报告和作者checkout未改；只提交R5 JSON与本追加，不改源码/测试/fixture/配置/spec/design，不push共享unit、不派worker、不Inbox/conversations/taskgraph/公开消息、不canonical/archive/PR/merge/deploy。未启动IM/Gateway，但确启动过native测试子进程。超时worker的orphan只在exact R5 DSH路径且PPID=1核对后TERM，不触碰Q/生产/其他worktree；未知temp home不猜路径删除，现场保留续验。最终exact worktree路径Node/DSH进程检查为0，剩余相关job均已收集或明确取消；report-only diff/check exit0。branch最终提交状态见交接回执。

---

## Round 6 — R5-W1 targeted runtime closure

### Summary / 版本与范围

**Verdict: PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION（R5-W1 targeted integration范围）；R5-W1 closed。** 原R5 NOT PASS、R2-W1/R3-W1 closed及Q R3 FAIL分别保留，不追改历史。`code-review-r6.md`为`[]`：无产品/测试patch，R5静态审查与18/18 corrected-delta **aligned retained**；不是重新生成整体Q或CI通过。

| 字段 | 值 / 边界 |
|---|---|
| validated_at / 本轮独立执行 | `b355b3e6b9dd2810a0520a8f7133a4aa0c0c1384` |
| 工程补证 executed_at | `3e5fff368d0d536ec471b0a6e7dc88e78d6e51fc`；实际运行七命令，不改为报告冻结SHA |
| executed_base | `18e1af8b1cd0834ae3f22f5780f2d50b740f5171`；更早Full base不改 |
| finding_origin_head / prior | `22114489ba131fbf847b60e0a4ca730d61471796` / R5 `db7c875efe3677e024bfcfe37df10d6b7cf57a12` |
| verification_mode / code_review_mode | targeted-closure（R5-W1）+ corrected-delta/static retained / evidence-only patch + retained |
| fix_delta_range | `22114489b..b355b3e6b`只有报告/记录；没有实现fix或timeout放宽，闭环来自同树原期限的具体运行证据 |
| requires_full_verification | **false（本轮closure已足够）**；R5当时true的未决共享边界经下表闭环，不据此取消Q独立新栈验收 |
| effective_base / effective_through | **仅R5静态/corrected-delta及本R5-W1 targeted运行范围**建立 `18e1af8b1..b355b3e6b`；整体effective_through仍未建立，Q R3继续FAIL待续验 |

独立git核对`22114489b..b355b3e6b`的packages/apps/src/scripts/tests/锁与根vitest配置diff exit0；spec/design/全部delta也diff0。`3e5fff368..b355b3e6b`仅integration-r5-runtime.md与progress.md，原R5两报告逐字等价。没有因作者新绿测就自动覆盖原报告；以下先还原全部失败，再审观察器、核原始结果和生命周期，最后独立补缺失四项及一项无observer对照。

### 原R5全部25失败的精确闭环账

原始独立30文件批次仍是20 files pass/10 fail、218 tests pass/25 fail、600.70s/exit1，未改写成整批通过。恢复原始Vitest失败输出逐test核对，发现作者七文件**尚未覆盖knowledge三项与workspace-tools一项**，并非只缺泛化“更多native”。本轮已独立补完四项，不需作者猜清单或另派worker。

证据代号：
- **A1–A7**：作者七份`*.vitest.log`与对应JSONL逐项核收，均执行于3e5fff368：A1=context-recovery-0918（1p/4skip），A2=approval-recovery-0922（6p），A3=http-matrix-recovery-0923（15p），A4=history-recovery-0924（1p），A5=capabilities-recovery-0932（3p），A6=model-policy-recovery-0927（5p），A7=personal-security-recovery-0929（6p）。共37pass/4skip，不把skip算pass。
- **R**：本人R5较低负载最后窄复跑的成功项：PA default、三规则root/child与realtime，见R5命令表；与当前产品/测试树实际等价，具体retained，不复活当时仍失败的六Agent用例。
- **I1–I3**：本轮独立、根仓配置、**无观察setup**、单worker/fileParallelism=false、原期限串行结果：I1六Agentprofile对照1p/4skip；I2 knowledge原失败三项3p/2skip；I3 workspace-tools1p。

以下file均省略`.test.ts`；除最后一行外都在`packages/dsh-integration/tests/`。名称和参数来自原失败结果，不用后来整文件总数推测匹配：

| ID | file / 原失败test完整名称或精确参数展开 | 闭环证据 |
|---|---|---|
| 01 | agent-context-default / defaults new and existing Agents to context management and persists explicit workspace opt-out | A1；I1无observer再证 |
| 02 | agent-context-default / gives a private Personal Agent the same default context tools without business permissions | R |
| 03 | agent-context-default / allows bounded internal context operations with codex Auto off while retaining child business denial | R |
| 04 | agent-context-default / allows bounded internal context operations with dsh Auto off while retaining child business denial | R |
| 05 | approval-retry-native / nano executes once after real reviewer HTTP (initial503=false) | A3 |
| 06 | approval-retry-native / nano executes once after real reviewer HTTP (initial503=true) | A3 |
| 07 | approval-retry-native / dsh executes once after real reviewer HTTP (initial503=true) | A3 |
| 08 | approval-retry-native / dsh executes once after real reviewer HTTP (initial503=date) | A3 |
| 09 | approval / uses the dedicated reviewer once per stage, escalates valid denials, and distinguishes unattended faults | A2 |
| 10 | approval / assembles native Inbox, delivered proposal and project instructions, and stops oversized review requests before submission | A2 |
| 11 | capabilities / keeps empty business tools and Skills empty while retaining context management, and restores a subset | A5 |
| 12 | capabilities / shadows owner tools in one workspace, constrains actual dispatch, and rebuilds after restart | A5 |
| 13 | capabilities / discovers copied skills in the same session while disabled names survive reload | A5 |
| 14 | history / forks a native message with its configuration and compacted prefix, independently and across restart | A4 |
| 15 | knowledge / runs independent native maintenance children, persists successful facts and withdraws each Feature | I2 |
| 16 | knowledge / invokes live human Inbox Skills once without promoting other sources (native pruning=false) | I2 |
| 17 | knowledge / invokes live human Inbox Skills once without promoting other sources (native pruning=true) | I2 |
| 18 | model-policy / keeps session effort and separates Skill catalogs from archived bodies (context windows=true, skill callable=false) | A6 |
| 19 | model-policy / keeps session effort and separates Skill catalogs from archived bodies (context windows=false, skill callable=false) | A6 |
| 20 | model-policy / keeps session effort and separates Skill catalogs from archived bodies (context windows=true, skill callable=true) | A6 |
| 21 | model-policy / keeps session effort and separates Skill catalogs from archived bodies (context windows=false, skill callable=true) | A6 |
| 22 | personal-security / keeps codex ordinary approval inside effective history while PA delivery retains its product boundary | A7 |
| 23 | personal-security / keeps the ordinary Global capability catalog and executes owner extensions and source controls | A7 |
| 24 | workspace-tools / installs workspace tools into existing chats, isolates dispatch, retries failed source and preserves restart choices | I3 |
| 25 | packages/channels/tests/realtime-window / six ordinary requests leave two slots for control and bound unsent queue | R；原60ms deadline/累计frame与并发pending区别仍按R5解释，不改断言 |

去重后恰好25项：作者七文件补齐其中17项；R5实际成功的具体4个原失败项retained；本轮I2/I3补另4项。I1重复验证01，仅作无observer对照，不再加一次closure计数。原22 timeout/2 poll/1 frame断言的失败事实全部保留；本轮不推断它们此前唯一根因均为资源压力。

### 观察器审查与工程原始证据核收

完整读取作者ignored `vitest.config.ts`两行与`setup.ts`49行：

- config保留仓库include及15s默认期限，仅设置maxWorkers=1/fileParallelism=false和setup；每test显式30/25/20秒等原期限、fixture/断言及生产30/60/90秒预算均未改。
- ObservedClient继承公开RuntimeClient；原options转发给super，仅包装onLog同步落盘后继续原callback。NANO_PROBE_INSPECT分支能改变child NODE_OPTIONS，但七次记录命令明确unset该变量和NODE_OPTIONS；本轮I1–I3亦unset，且完全不加载该setup。RPC wrapper绑定原request、传原method/params、返回原result或重抛error；prepareProfile/shutdown调用原实现；notification只记type、exit只旁观，不生成判定/终态或响应。
- **不是零扰动等价证明**：同步append与async wrapper会增加I/O/微任务并可在磁盘故障时抛错，因此不声称所有调度完全相同。没有发现它绕过权限、预算、断言或替换审核结果的机制；七份原Vitest输出确为原测试绿，I1根配置无observer同样通过是最窄相关对照，不外推为所有观察设施全面认证。
- 对七份JSONL独立做结构断言和聚合：spawn/exit分别2/5/15/2/5/8/4，共**41/41，全部code0/signal null**；test-end pass分别1/6/15/1/3/5/6，共37。按(pid,id)对应rpc-start与rpc-end/error，分别54/201/340/48/80/126/48条全部闭合，含测试预期拒绝，不把notification的任意turn/end冒充input终态。
- 独立检查每次afterEach记录home exists=false，并检查32个unique home当前实际不存在；41个记录PID当前不在进程表。这里只核作者已有证据，不kill/删除其资源。JSONL证明生命周期及观察完整，业务终态仍归原测试sessionId+inputId lookup与效果/审计断言。
- runtime.md:112–179的零Agent1421ms对照、contract13pass/7.65s、资源恢复与七次exit0作为带命令/版本的工程事实核收；没有将其称为本轮独立重复执行。作者37pass补证只在逐项匹配后使用，不以总数替代原25个失败清单。

### 本轮独立执行（新worktree，无observer）

2026-10-22 +0800，Node25.8.2/pnpm11.7.0、冻结DSH0.2.1-alpha.1/context rc.5。preflight load4.31/9.51/16.08、Data卷Available9187812KiB，只用于当前一个native窗口，不将磁盘建议值当产品契约或通过保证。依赖/build结束后才串行跑测试，没有并行Q/IM栈或宿主重批次。

共同前缀：`env -u NANO_PROBE_INSPECT -u NODE_OPTIONS caffeinate -i pnpm exec vitest run --maxWorkers=1 --no-file-parallelism`，使用根vitest.config.ts，无setup/vi.mock/注册hook，无延长期限。

| 实际命令后缀 / job | 结果 |
|---|---|
| `pnpm install --frozen-lockfile`，继而`pnpm --filter @nano/dsh-integration... build`（bash-93） | 两者exit0；product-contracts+integration编译，不声称全部release/CI build |
| `packages/dsh-integration/tests/agent-context-default.test.ts -t 'defaults new and existing Agents'`，I1，09:38:31 | **exit0，1pass/4skip，8.26s**，test7991ms，原30s |
| `packages/dsh-integration/tests/knowledge.test.ts`配下方精确`-t`正则，I2，09:38:41 | **exit0，3pass/2skip，9.53s**；maintenance4335ms、pruning=false2427ms/true2587ms，原30/20/20s |
| `packages/dsh-integration/tests/workspace-tools.test.ts`，I3，09:38:53 | **exit0，1pass，60.24s**，test60060ms，原90s |

I2完整命令（正则为OR，不含额外转义）：

```bash
env -u NANO_PROBE_INSPECT -u NODE_OPTIONS caffeinate -i pnpm exec vitest run --maxWorkers=1 --no-file-parallelism packages/dsh-integration/tests/knowledge.test.ts -t 'runs independent native maintenance children|invokes live human Inbox Skills'
```

三条在同一bash-95按set-e顺序执行，全部exit0后才继续/收取，整体exit0；不是三个同时native job。workspace测试本身有既定kill/restart/async cleanup断言，未新增故障或改清理行为。本轮未重跑七文件37项、原30文件整批、90秒×3、native owner/真IM或vendor；按范围复用可信证据并补精确欠项，而非重复已有效测试。

### Closure / 门禁边界与现场

- **R5-W1 closed，0C/0W/0S。** profile/opt-out/restart、CC超窗终态、15项真实HTTP与配置/history/capability/personal邻域由核收的同树原期限证据建立；剩余knowledge/工作区安装面已独立补齐，原R5权限四工具/root/child/downstream deny与durable分层的适用成功事实retained。R5静态18场景映射无delta变更，aligned retained，不重新写目标迎合实现。
- **Q R3仍FAIL/11pass6inconclusive，Q625-R3-01未由本轮关闭。** 真实required/source/stop/fallback/native owner/双vendor新profile交父E续原Q，底层RuntimeClient fixture（包括product.call stub）不是真实PA/IM。不能由本轮closure宣布整体effective/CI/Ready PR，亦未canonical/archive/merge/deploy。
- 新建前检查绝对路径/branch不存在，在冻结SHA建立`/Users/czj/.nanoassistant/workspaces/nano-engineering/.worktrees/review-feat-625-r6` / `review/feat-625-r6`，本人owner，保留续验；R5和作者现场不覆盖。最终exact R6路径Node/DSH进程为0，两个相关jobs已收取exit0，没有启动IM/Gateway或操作其他现场。
- 仅R6 JSON与verification追加报告commit；原R5完整字节前缀、code-review和acceptance不改，不push共享unit、不Inbox/conversations/taskgraph/公开消息、不派worker。原产品W1与设施R3-W1各自closed，不复活历史FAIL；报告commit自身不是新的受试产品版本。
