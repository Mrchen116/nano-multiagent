# Final sync 与 corrected-delta 中性交接

本记录是工程影响判断与独立复验输入，**不是新的独立门禁PASS**。遇到同链路main语义变化后，停在这里交父E调度；未canonical归并、归档或创建PR。

## 固定版本与报告归属

| 项 | 精确版本 / 事实 |
|---|---|
| 原执行基线 executed_base | `861b94129bc8c5aadbca76967268fd203fe04112`，历史报告不改写 |
| Q R2实际validated_at | `2f519f659b114003d35f2fcc2305469f6e40962c`，PASS；原R1 FAIL保留，2major closed / 新增0，17项组合=14具体retained+3新closure；21真IM E2E+96分层，不含后续导出失败分支 |
| Q报告集成 | 原`7dc58abc6e65c1c47fff7c8e693a8abf44249fe9`→`59acee1ff`，仅acceptance追加123行，逐字diff exit0 |
| 静态R4实际validated_at | `89f2a20da49e3d3741b47fede35b33bb06893f3d`；code-review-r4为`[]`、targeted verifier PASS0C0W0S，R3-W1 closed，requires_full_verification=false；不背书final sync/corrected-delta |
| R4报告集成 | 原`8fcc6c1a7f9087c34838984204660c37ccb00f2e`→`6df263df3d1434355e7c81648b6a7ce69597d9ed`，仅code-review-r4/verification，逐字diff exit0 |
| 报告集成树核对 | `89f2..6df263`仅3份报告+184行；Q2f519与89f2的integration/src、产品包、apps、src与锁文件diff exit0。此等价性**仅限同步前** |
| fetch到的main | `18e1af8b1cd0834ae3f22f5780f2d50b740f5171`；`861b94129..18e1af8b1`共134文件，+8302/-319，不把庞大docs数量当风险判断 |
| 集成产品树 | merge commit `f586ff4500e6b522ed470cd4718037889ecd7442`，parents为6df263与18e1af8b1；之后只校正本unit delta和交接文档，最终冻结HEAD由父E交接回执给出 |
| 当前校正/复验候选 executed_base | `18e1af8b1cd0834ae3f22f5780f2d50b740f5171`（新复验使用）；不替换上列历史executed_base |
| effective_base / effective_through | final-sync目标base=18e1af8b1；整体门禁effective_through **尚未建立**，待下列同链路独立复验及corrected-delta。不能把merge成功、烟测或报告commit当成整体有效 |

## main增量与冲突处理

- **feat-627 / bugfix-629：直接同链路。** 默认启用`dsh-agent-context`，当前锁定`0.3.0-rc.5` tarball及integrity；DSH仍`0.2.1-alpha.1`，没有fork/patch。workspace profile初始化、随包bundle inventory、tool selection、四个上下文工具Auto-off内部放行、native压力裁剪/Skill恢复均发生变化。审核依据的有效历史、compaction purpose及公共工具面随之变化，不能整体继承旧Q的context/source结果。
- **feat-630 / bugfix-631/632：同一真实产品入口。** IM/Channels/Node引入独立Work上传、request-id窗口、durable relay receipt/control、Inbox分类/恢复wake、发送状态查询/确认与permission resolved身份；PA Global发送/读取/重启链均变化。625的live/restored/sent/held/partial/PTC、cancel/fallback与子任务可见性需针对新集成栈判断。632仅标题命名，不据此重测视觉。
- **bugfix-633、feat-628/634：当前main为文档/设计，不是假定其未来实现已合入。** 特别不把633的原生human来源改造提案当成本次实际代码变化，也不在此顺手实施。
- merge唯一文本冲突在`policy/approval.ts`相邻import：unit新增ReviewRecovery、main新增contextTools。保留两行；最终相对6df263的该文件diff只有contextTools import与原main的internal_context两行分支，没有重写cancelReview/recovery逻辑。原业务assertion/预算/fixture未改。
- 首次`git diff --cached --check`因main自带archive feat630 relay-protocol末尾空行exit2。精确与origin/main比较该文件exit0，故未改他人已合并归档；本unit冲突文件检查exit0后完成merge。PR相对新main的unit delta另做diff-check，不把继承的空行隐藏成无失败运行。

## 每闸影响矩阵（工程建议，独立角色可扩大）

| 闸 / 原报告 | 可具体retained | 失效或待复验范围 / 下一责任 |
|---|---|---|
| Gate2 design R4 Approved | spec/design/milestone未改；需求仍是共享额外2次、格式1次、完整阶段预算、不扩权限。main没有把本unit目标替换成另一方案 | delta校正不是重新设计。若独立核对发现新profile与既有设计不能兼容，再交P；不能凭本表自判新设计通过 |
| 产品code review R1 + R2 closure | 原cancelReview双gate/W1 closed事实；recovery/classifier/codex/sources等625算法源码未由main改动 | 原静态reviewer对`6df263..f586ff`中同链路main与approval import合并做patch/integration核对，重点internal_context豁免必须在downstream deny后、业务工具/child不获扩权、默认上下文插件与reviewer scope/purpose/owner归属边界 |
| R4测试设施closure | helper/13错误路径测试与native调用契约在sync中未改；纯fs清理/原错误保留结论可retained | 主runtime上下文插件变化不等于helper错误路径重新失效。若新的调用者生命周期/清理接口改变才扩大；本次不机械重跑90秒来验证mkdir失败 |
| verifier Full/R2/R4 | 原共享次数、阶段预算、typed错误、审计usage与终态的确定性结果；产品W1、设施R3-W1各自closed，不抹旧FAIL | targeted integration verification + **corrected-delta**；逐项核对新默认context/发送恢复与625冻结证据、不复活原文、额度与fallback。范围不足可扩大，不能仅看新旧文件名 |
| Q R2 PASS | 历史17项组合及21+96的实际结果、真vendor180/55/负例事实仍成立于其原SHA；不重写为“新栈全量跑过” | Q对新main集成栈targeted：context3/source12与stop/cancel/人工分流邻域、native缓存/fork/owner及默认context交叉；新workspace profile/inventory影响安装路径，S17是否需最小真vendor安装+调用复验由Q按实际边界裁定。先复验后才能建立整体effective_through，非空reply/observer等仍按原具体分层边界，不强制笛卡尔积 |
| CI / archive | CI配置本次main增量未变，原绿测作为历史事实 | 当前新集成树需本地等价与远端CI；它们不是上述独立产品/静态门禁的替代。corrected-delta前不canonical，不运行“已归档”检查冒充退出 |

供父E一次调度原静态reviewer：`review_mode=patch`（集成同链路）+ `verification_mode=corrected-delta`并覆盖上述targeted integration关注点；`executed_base=18e1af8b1`、`validated_at=最终冻结HEAD`，prior verification R1–R4、code-review R1–R4、Q acceptance R1/R2；main区间`861b94129..18e1af8b1`、集成差异`6df263..f586ff`、本轮delta校正相对f586ff。Q另由父E在原节点定向续验；本执行者不派worker/不改Q现场或任务图。

## corrected-delta实际校正与实现/测试映射

文件：[delta agent-capabilities](../specs/gateway/agent-capabilities.md)。未碰canonical；不更改spec.md/design.md来迎合实现。原delta是设计时目标，本轮补最终可观察行为并修正歧义：

1. 明确完整CC30/60与Codex90秒预算、跨stage共享额度；不是所有重试挤进首次窗口。
2. W1闭环后的最终取消路由、原模型事实/用量保留、不重复成本/拒绝计数及审计失败不allow。
3. CC实际context超限不能盲作临时重试；其他typed错误按类型适用有界恢复，不再含混写“全部按原失败路径”。
4. 补MODIFIED Codex requirement的完整条目：干净full与成功cache/context≤1、冻结来源、default recovery与checkpoint preserve、required不可裁、合法parser缺省/外围说明。626已有稳定语义只在这一条完整保留，不新增另一份影子契约。
5. 保留MODIFIED Auto其余完整场景，canonical中main新增的默认上下文Requirement是另一个条目，不被本delta替换。新增ADDED1条、MODIFIED2条，合计18个投影场景，不把它与首文档17个验收场景机械等同。

下表为逐项中性核对入口，不是作者的独立verifier结论。源码均相对`packages/dsh-integration/src/policy/`，测试均相对`packages/dsh-integration/tests/`；IM驱动在`tests/e2e/critical_paths/`。

| delta Scenario | 实现落点 | 长期测试 / 独立历史证据 |
|---|---|---|
| A临时故障恢复 | recovery.run；classifier.classify阶段；codex.review共享action | review-recovery / approval-retry-native / codex-approval-native；Q C2/T2/N2与原默认预算证据 |
| A空白/非法共享子额度 | recovery.run format与总次数；parser | review-recovery、approval-retry-native；retry真IM mixed/twiceformat/empty |
| A取消/永久错误 | recovery.reviewFailure/whileActive；approval.review/cancelReview；codex.clean/quarantine | review-recovery、review-quarantine-native、review-audit；Q T2真实stop |
| ARetry-After | recovery.run + llm-attribution单stream HTTP facts | review-recovery、approval-retry-native、review-owner-native；Q T2限流/N2归属 |
| A旧模式/fallback | approval.route/escalate/review | review-audit、approval；Q原R1 F/H及R2相邻取消复验，不冒充新栈重跑 |
| A可检查恢复事实/W1 | audit schema、approval.cancelReview/record、recovery.finish/knownUsage | review-audit27双gate/写失败、approval-retry-native关联、Q T2/N2 |
| M-Auto默认规则 | approval.review原规则路由 | approval、approval-workspace；Q双策略旅程 |
| M-Auto去重/来源/PTC | sources.history/restoreEntries/codexEntries | approval-sources、review-source-recovery；Q P2真PA12、PA2独立链；新main需针对复验 |
| M-Auto CC超窗 | classifier的estimateContent+maxTokens准入 | approval-sources/approval + 真IM不可用分流；CC不裁授权，Codex走下列独立准入 |
| M-Auto子任务委派 | approval.review、runtime原approval=never、Global主产品桥 | approval/personal-security；Q R1 F与R2 P2 child，sync需核新context基础工具不扩业务 |
| M-Auto配置切换 | approval/codex.release/config fingerprint与原runtime轮次配置 | approval-workspace、codex-approval-lifecycle、个人安全；旧Q既有请求/迟到结果邻域 |
| M-Auto模型失败处理 | approval路由 + classifier/codex request reviewer | approval-retry-native、personal-security；Q独立审核模型与typed失败 |
| M-Auto逐Agent继承 | 原产品contracts与runtime配置选择，625不新造选择器 | approval-workspace、model-policy；原R1实际规则/模型事实，新main上下文工具面另验 |
| M-Auto下一轮切换 | 原runtime config/release边界；当前动作recovery冻结 | approval-workspace、codex-approval-lifecycle；历史事实保留不等于new main已体验 |
| M-Codex现场可信来源 | codexPolicy、sources、inspectionTools | codex-approval、approval-sources、personal-security；Q A2/PA2/P2 |
| M-Codex连续并发/预算恢复 | codex.prepare/review/owners/checkpoint/clean + recovery.takeContextRebuild | codex-approval-native、review-owner-native、codex-approval-lifecycle、review-source-recovery；context/source真IM驱动 |
| M-Codex证据预算 | codex.review准入+codex-context.reviewInput | codex-approval、lifecycle；context required-action、公开compact/source有效原文不得复活 |
| M-Codex判定/失败 | codex-context.parseCodexDecision、codex.review、approval终态 | codex-approval/parser、approval-retry-native、review-audit；Q allow缺省/deny/JSON外围说明分层 |

## 本轮准备性执行与当前CI等价清单

在已同步f586ff的代码树运行（随后只有本unit delta/本记录文档变化）：

- `pnpm install --frozen-lockfile`：exit0，新增加1个已锁定context bundle，锁文件未改；`pnpm --filter @nano/dsh-integration... build`和integration typecheck均exit0。
- 9文件窄烟测（agent-context-default、capabilities、history、model-policy、native-review-evidence、review-audit、approval-sources、review-source-recovery、codex-approval-lifecycle）：**9files73tests/29.31s/exit0**。含新main原默认上下文5项及原13导出失败；没有真IM/90s×3，不替Q/静态targeted复验。
- 当前`.github/workflows/ci.yml`：backend为pip dev依赖、docs-check、pnpm frozen install、`pnpm build && pnpm typecheck`、`pnpm test`、`pytest -m 'not e2e' -q`、ruff check/format；frontend为`npm ci`、`npm audit --audit-level=critical`、`npm run test`。build-node-release包含在pnpm build；不把frontend build当CI必需项。
- iOS检测按最终PR相对main的full diff，非按历史merge带入的文件；本unit不改CI或iOS，预期detect=false，但以最终diff与远端check实际结果为准。PR archive gate需整个unit完成归档后执行，当前故意不声称通过。
- backend CI Node24/Python3.12、frontend Node20；本机命令环境与远端版本区别如实记录，不能仅本地绿就称远端绿。完整等价批次留待独立门禁对新集成树有效后持续执行。

下一步阻塞仅为**必要独立integration复验与corrected-delta**，不是任务图权限；内部工程已按原授权推进。父E取得报告后续同一执行者完成canonical/local CI/archive/Ready PR/远端CI，仍不merge/deploy。
