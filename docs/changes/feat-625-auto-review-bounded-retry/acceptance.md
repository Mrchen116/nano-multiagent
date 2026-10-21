# feat-625-auto-review-bounded-retry — 独立产品验收报告

## Round R1

> Validation snapshot: `861b94129bc8c5aadbca76967268fd203fe04112 → 4c20949e5e6995944f35217177950e14dfdf67da`
>
> unit_id: feat-625-auto-review-bounded-retry · review_round: R1 · mode: full · revalidation_mode: full
>
> 独立 Q fresh context；来源 #361 / c_fqyj3bvq / tg_e33bc1fd/n5。未读作者 progress/tasks 或既有验收结论，未静态审查实现，也未修改实现、测试、设计或受版本控制配置。

## Verdict

**fail（Full 验收证据未闭环，不等于已证实全部产品功能有缺陷）**。

Highest Required Action: **fix-implementation**（交 E 判真并补齐下述阻塞证据；不以此断言源码根因）。Issues: **2 major**；gh_issues_filed: 0；needs_re_review: **true**。17 个必验 Scenario 逐项判定：14 pass、3 inconclusive；无 not-applicable，未虚报未知项通过。

真实双策略全局插件完整任务可交付，受控重试/预算/取消/各模式 fallback 的已观察部分符合判据。但 Codex context rebuild × service retry × concurrent/cache 生命周期，以及 runbook §5.2 的完整有效上下文/压缩/来源/admission 交叉验证仍不足；不能由成功插件任务或 lower-layer 单测代替 Full 放行。

## 原始判据、版本与环境

- 以 `spec.md` 17 个 Scenario、`design.md`、`reviewer-runbook.md` §§5/5.1/5.2 与本轮交接的最新确认要求验收。每次完整30/60/90秒；额外恢复全 action≤2；格式≤1占共同额度；context rebuild全 action≤1；取消/late不执行；耗尽保留既有 fallback，包括无人值守 allow 恰好执行一次。
- checkout：`/Users/czj/.nanoassistant/workspaces/nano-quality/.worktrees/q-feat625-acceptance-r1`；branch `q/feat625-acceptance-r1`；开跑及报告前 HEAD 均为 validated_at。无 pull/rebase；父 checkout 的 untracked 内容未动。
- 自己新建 `.venv`：Python 3.11.13，解释器来自本机 uv 安装；未使用 E 的 venv运行目录。`pip install -e '.[dev]'`、`pnpm install --frozen-lockfile`、`pnpm build`、frontend `npm ci` / `npm run build` 全 exit 0。Node25.8.2 / pnpm11.7.0 / DSH0.2.1-alpha.1。build 输出候选 SHA `4c20949e…`，installer digest前缀 `fd42cf25a86e`。构建 warning（frontend chunk大小、npm 5 low audit）未修改依赖锁或运行实现。
- 真实 vendor：main `deepseek:deepseek-v4-flash`；独立 reviewer `codexOAuth:gpt-6.1-sol`，provider `anthropic` 经既有 localhost:4000。不仅检查目录声明：真实 bash smoke、安装及插件调用的 durable审核 records 均有该 reviewer 的完成请求与 allow。受控 fixture 使用 `main` / `review`，记录 effort=low；不把 fixture成功等同真 vendor 可用性。
- 所有运行经 `scripts/e2e-up.sh --wt <独立目录> --main-config <本次配置>`，仅隔离 nano / e2e-global 测试身份；每栈独立端口、DB、workspace、node identity、owner config root及 DSH home。未读取私人/生产配置或真实账号，未重启代理、merge或部署。
- 客户端面未变，本轮按 runbook 允许使用实际 IM HTTP/WS（`_im_client.py`）与 Work分页接口；没有 runtime session.submit 替代。**实际 viewport: N/A（无浏览器运行）**；不声称观察了视觉布局/交互截图。

## 用户旅程体验

用户以自然任务请求创建差旅插件；Global Agent真实读 Inbox、加载插件 skill/公开 API、编写 workspace bundle、安装、调用并通过 send_message 交付。用户能从结果辨认插件位置、安装状态和逐项限额核算，不需反复重新发起安装。双策略分别返回第一组80+100=180、第二组25+30=55，并有 Work 中对应真实工具输入/结果。随后以“不修改/不重装”的补充请求实际调用负金额及负限额，两个已安装插件均明确拒绝，没有把负值截断为0继续核算。局部探索中 CC 的安装前单独 JS import遇到 workspace peer解析失败，Agent仍按插件宿主安装后正常运行；这不是审核重试失败，本轮未据此扩大实现修复。

期间最初 smoke driver把包含命令的接单回复匹配为完成，导致紧接着发送插件请求；因此本报告**不使用 driver completed=true 证明完成**，而核对随后 Work 的 bash实际输出、安装 applied及插件工具结果。Global主上下文正确继续处理第二条已读消息；没有把确认消息当交付。

内部恢复无需主 Agent重调工具。控制服务的持续错误时，普通有人值守通过真 WS得到人工审批请求（未允许前零副作用，allow_once后一次）；Global/child返回准确技术阻断；schedule/heartbeat依既有 allow/deny配置分别一次/零次。可观察失败与“模型安全拒绝”清楚分开。几分钟等待通过真实默认计时验证，不能宣称新 UI显示每次尝试明细：attempt trace在既有approval domain，不是Work新增进行中journal。

## Reference Artifacts Reviewed

N/A：设计明确“不动客户端面、不新增页面/按钮/卡片”，无 prototype或 must-match视觉参考。本轮未作视觉质量通过结论。

## 本地证据索引与分层

以下路径均相对于上述 Q worktree；原始日志、DB、配置、模型 prompt、截图/secret不提交。报告内只保留脱敏结果和可复查的定位。原始运行数据保留本机供主 Q/E复查，不是仓库可移植附件。

| ID | 层 / 实际入口 | 可复查证据 / 结果 |
|---|---|---|
| L | 真 vendor + 真 IM/Work | `.e2e-feat625-q-r1-live-{nano,codex}/{meta.json,negative-work.json,negative-messages.json}`；下表列 call/review定位。两策略真实插件独立创建安装与调用、边界拒绝 |
| M | 真 IM + 受控HTTP | `.e2e-feat625-q-r1-matrix-20261020/`；长期 E2E全文件8项pass，340.75秒；各用例approval/deadline/stop-export.json；双策略每个 matrix测试内10个动作 |
| B | 真 IM + 受控HTTP，临时观测driver | `.e2e-feat625-q-r1-budget-{nano,codex}{,-extra}/budget-export.json`；完整60秒阶段、跨阶段额度、timeout/503/timeout、格式总额度及三次timeout；额外的早期 crossstage=[503,503,allow,503]在s1 allow后正常终止，不误作跨阶段覆盖；有效覆盖为crossstage_exhausted |
| F | 真 IM / 实际schedule、heartbeat、Global/child | `.e2e-feat625-q-r1-extra-*/summary.json` 与 `review-inputs.jsonl`；下表只采用完成的 v3/global与明确child结果 |
| H | 真 IM WS人工审批 | `.e2e-feat625-q-r1-manual-{nano,codex}-v2/manual-export.json`；三个503后allow_once，允许前0、允许后1 |
| N | native integration补充 | `.e2e-feat625-q-r1-output/native.log`：10文件79 tests pass，Guardian native 1 test timeout；retry-native transport/HTTP-date/invalid-header/legacy、owner归因、实际late quarantine通过；不是产品入口替代 |
| U | lower层/fake-clock补充 | `boundary-verbose.log`：6文件61 pass（是N子集重跑，不叠加虚增覆盖）；含30/60/90完整budget、action context上限、来源投影及626 admission/parser/只读约束 |
| NR | native有界复跑 | `native-recheck.log`：Guardian native再次timeout；personal-security 5 pass / Global capability test timeout。两普通PA有效history检查通过，不等于全面产品压缩/来源回归 |

可复跑主命令（**basetemp必须首次不存在**）：

```bash
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .venv/bin/python -m pytest   tests/e2e/critical_paths/test_auto_review_retry_critical_path.py -v   --basetemp="$PWD/.e2e-feat625-q-new-unique"
```

临时 drivers仅在gitignored `.e2e-feat625-q-r1-output/`，没有改长期fixture/测试。初版schedule driver沿用了旧 `plan` 参数，真实工具schema实际是 `after_seconds`；初版无due execution被判无证据，不当产品失败。检查真实模型请求中的schema后只改临时driver，v3重新以全新目录得到实际schedule/heartbeat fallback证据。中途若干长等待后隔离客户端出现401，改为每旅程重新login；未取证token失效根因，不复用失败现场冒充pass。Global work_mode对已有Agent切换收到409，改用从首次启动即global的独立栈；409本身不作本unit缺陷。

## 真 vendor 旅程定位

以下均 main turn `1`，实际审核模型 `anthropic / codexOAuth:gpt-6.1-sol`，所列成功动作内部 retries=0（真vendor未主动注入故障）。

| Policy | 运行UTC / IM端口 | conversation / input message | main session |
|---|---|---|---|
| nano | 2026-10-20T14:29:35+00:00—2026-10-20T14:32:14+00:00 / 59498 | `c_wxstntd1` / `d322878697b24c6dbfc35352fb744c0d`；负数补充 `742cd5ed176a4364bebbf63e3d8a2327` | `7e1262df-60f7-4f64-8211-88eadfc62431` |
| codex | 2026-10-20T14:29:48+00:00—2026-10-20T14:32:27+00:00 / 59574 | `c_d5oedriq` / `40c8147bd5fd4fcd9300a9ffb59336bd`；负数补充 `f22cac5fd678448b960484b5735334b4` | `e2d8ca68-1bdc-42fd-95b0-f73ec8c2e370` |

| Policy / action | Work seq / callId | reviewId | 实际结果 |
|---|---|---|---|
| nano / plugin_manager | 65 / `call_00_sKsJPDEefHlSCfQonJrX7506` | `d685c900-b01b-401c-936a-b272c458afd7` | applied / warnings=[] / 1次安装 |
| nano / travel_expense_settle | 69 / `call_00_9Ns0JdJ1skMIHaW7VvTJ1112` | `80f6d3d4-946d-4cc4-a63d-2ca9f8fd43cf` | 180 |
| nano / travel_expense_settle | 72 / `call_00_ET_HVnvnShsJpgtN7Euoiiz5847` | `81ef979a-873b-460d-8bed-dffbbdb87050` | 55 |
| nano / travel_expense_settle | 75 / `call_00_IALAKUtaqYA0WHg4UKyF3824` | `840e60d2-7617-4849-a178-8010b9c653eb` | Error: 票据金额必须是非负数：-10 |
| nano / travel_expense_settle | 94 / `call_00_ET_aRe2YS3m0XdmiqM7tmDn3879` | `1d2ca43b-6b79-4892-ad55-df2718f77628` | Error: 票据金额必须是非负数：-1 |
| nano / travel_expense_settle | 97 / `call_00_ET_Hng0aHXwV7DXFdm2j5ko1011` | `919e600a-6ff4-43d0-b338-17806985b6cd` | Error: 单项限额必须是非负数：-1 |
| codex / plugin_manager | 70 / `call_00_ET_HDxaYyI7jWLG85ygf9gh6985` | `0fe9de5d-1eb0-429b-889e-d1c96e1d54db` | applied / warnings=[] / 1次安装 |
| codex / travel_expense_reimburse | 74 / `call_00_NyHEUQro76woPWbrmnpJ2164` | `c4d22263-0a5c-400c-8fb9-1b976a73849e` | 180 |
| codex / travel_expense_reimburse | 77 / `call_00_ET_AyRb4kiUHJsHKB1C3bc85662` | `57b58098-5d0b-4a3e-82fb-3ab43c545924` | 55 |
| codex / travel_expense_reimburse | 80 / `call_00_jwgCoL14884I4pTFqNmn9271` | `185fc518-67ee-44d3-b898-79fbb7a33111` | Error: 第 1 条票据的金额 不允许为负数（收到 -5） |
| codex / travel_expense_reimburse | 102 / `call_00_ET_2CCts6YP9j7p51RE4CNt4279` | `6206663e-32d8-4d83-9b53-e025487495e5` | Error: 第 1 条票据的金额 不允许为负数（收到 -1） |
| codex / travel_expense_reimburse | 105 / `call_00_ET_izO6p8TBpYUGzty0kJlm0288` | `24bec20c-7afe-4fce-ac99-c72d89fea7bc` | Error: 第 1 条票据的限额 不允许为负数（收到 -1） |

## 受控动作定位

M的同一策略10动作共享conversation；每个callId为 `effect-<case>`，每行独立reviewId。record的session/root和持久存储主session并不总相同：Codex记录的是原生隔离reviewer session，下列session列据fixture实际记录，不冒充main。

| Case | conversation / message | session(record) / reviewId | retries / format / context | route / effects |
|---|---|---|---|---|
| nano_success | `c_wrwdiaw6` / `9b9ac30d00664d36b2a083319eab59ca` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `4b48a5bc-42dc-4bc6-964c-78fcf1e84ab4` | 1/0/0 | allow / 1 |
| nano_mixed | `c_wrwdiaw6` / `7272a247da77485d935b827cd5da8f26` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `ee53a728-4899-4975-8a69-72e5bd7cec38` | 2/1/0 | allow / 1 |
| nano_twiceformat | `c_wrwdiaw6` / `675af0ca2508413ea9680f6b23ad3248` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `12c02210-acbb-455e-893e-5af2e29621af` | 1/1/0 | interactive_pending / 0 |
| nano_deny | `c_wrwdiaw6` / `82744685815644639cb323cdcf4ed5f9` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `4c967e97-cb7d-445f-a863-ffc6f65db33b` | 0/0/0 | deny / 0 |
| nano_limited | `c_wrwdiaw6` / `c91d6db3d69645dc8185474d42a6c5fb` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `c429c180-43d5-4e05-b0ef-3f2b06111ca8` | 1/0/0 | allow / 1 |
| nano_permanent | `c_wrwdiaw6` / `5e6fd8655a354f1cbf63558af2459a9f` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `f6c198cf-6313-4f15-8b2e-56197ef3f0c1` | 0/0/0 | interactive_pending / 0 |
| nano_longdelay | `c_wrwdiaw6` / `e9fa11c34cb5453aaf6b423d7f055b69` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `80e54e12-f262-4f99-8946-1784a580b21d` | 0/0/0 | interactive_pending / 0 |
| nano_exhausted | `c_wrwdiaw6` / `bfc51158b760453985e2602355da9ae8` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `a188c3d0-a7ab-4617-97c2-71a436b3a762` | 2/0/0 | interactive_pending / 0 |
| nano_empty | `c_wrwdiaw6` / `2e83bfcbcc3d4d838f1b967dcc38b832` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `e24dc686-c842-4f63-886c-bebf8c8fc616` | 1/1/0 | allow / 1 |
| nano_secondstage | `c_wrwdiaw6` / `2a460e2d90594f60a893f46a98f087a2` | `31e52141-3b22-4103-b4c6-cf5246a3fd7f` / `26f52b57-be94-4a1d-9568-452f76824661` | 1/0/0 | allow / 1 |
| codex_success | `c_fv01zlnh` / `367bc06341784534a4036463a45319a9` | `nano-codex-4d37d08d-7a83-47c6-a8af-b664bed9922b` / `ca7622b7-9528-4fed-9db8-4c396a414462` | 1/0/0 | allow / 1 |
| codex_mixed | `c_fv01zlnh` / `795895bf8dfc4325a0e966db5e96d0cb` | `nano-codex-173bea40-5fe6-4c4a-940e-00ba7fd2688e` / `857ddd6e-1d8c-416b-bf71-d56e7fa2331b` | 2/1/0 | allow / 1 |
| codex_twiceformat | `c_fv01zlnh` / `cef8c00a18584cd2b8202f5d6719a481` | `nano-codex-2f294a7a-155f-4dd5-8d17-7af6e524a662` / `8bf3843d-5114-4e67-beb5-319a2b0c418f` | 1/1/0 | interactive_pending / 0 |
| codex_deny | `c_fv01zlnh` / `058d82d4094649e38bab01ca19c39a4e` | `nano-codex-c38533c0-555e-4a7c-9ecf-3d0552181b4c` / `336567a0-527a-4c06-8819-c4aaade87748` | 0/0/0 | deny / 0 |
| codex_limited | `c_fv01zlnh` / `2046861558e744ddb8b12a81f296d79e` | `nano-codex-c38533c0-555e-4a7c-9ecf-3d0552181b4c` / `a0a2fc13-5c00-4508-a0d6-de6bb49fdc8d` | 1/0/0 | allow / 1 |
| codex_permanent | `c_fv01zlnh` / `15924f0081714278b0be287b5edec998` | `nano-codex-c06c7eb3-d972-4a70-b40a-078ead728c84` / `f24f7a7f-1fde-49a6-a8b5-da4521026708` | 0/0/0 | interactive_pending / 0 |
| codex_longdelay | `c_fv01zlnh` / `5a378cc5cf584d7cb9efb527307625be` | `nano-codex-183fa8aa-e708-4b17-8dd9-aa35c089f95e` / `b904db5e-3526-4b37-8410-b48966a5e8a2` | 0/0/0 | interactive_pending / 0 |
| codex_exhausted | `c_fv01zlnh` / `07dd0fa7412c4453bf74cbd91532c6ab` | `nano-codex-e5450fc9-b4ff-4547-87fe-e1ba000da0f6` / `91545eb6-d4ed-4da2-af5e-37fe7fd4de2e` | 2/0/0 | interactive_pending / 0 |
| codex_empty | `c_fv01zlnh` / `604cdb5bc1a84b9c934e822baa1ea68e` | `nano-codex-1f74ddc6-2dbc-488c-a871-1fbb87546925` / `2ef10d04-48c5-45dd-97c3-d0ca8d874689` | 1/1/0 | allow / 1 |
| codex_inspection | `c_fv01zlnh` / `7339bbc9601b4131a5e26adcc5c82d27` | `nano-codex-70b9b8c3-72d4-4963-82bf-73ddde08bf36` / `50c424df-1cb2-4daa-96be-6c4499a732fe` | 1/0/0 | allow / 1 |

### 额外预算/取消/人工定位

- B `.e2e-feat625-q-r1-budget-codex` / `codex_format_exhausted`：conversation `c_ifdn94u7` message `a79c7f43e7a2495fa15aaebfa592cc90`；call `effect-codex_format_exhausted` review `6f5a3fc4-b7a8-421c-9546-c3a7dc564147`；budgets `[90000, 90000, 90000]`，retries 2，route interactive_pending，effects 0。
- B `.e2e-feat625-q-r1-budget-codex` / `codex_mixed_timeout`：conversation `c_ifdn94u7` message `c8d56266ad5540fb961acc1278abd029`；call `effect-codex_mixed_timeout` review `18c80049-290c-45e8-82ad-efdd27f0cba2`；budgets `[90000, 90000, 90000]`，retries 2，route interactive_pending，effects 0。
- B `.e2e-feat625-q-r1-budget-codex-extra` / `codex_triple_timeout`：conversation `c_87giaw2r` message `bedbb36db0b649c4900d47d3642d18c1`；call `effect-codex_triple_timeout` review `39b8d9e5-bf77-4245-8062-9985cb8bb7b3`；budgets `[90000, 90000, 90000]`，retries 2，route interactive_pending，effects 0。
- B `.e2e-feat625-q-r1-budget-nano` / `nano_stage2_full`：conversation `c_7vaqyaii` message `e61924f5494a4735ae683396e5cad447`；call `effect-nano_stage2_full` review `649d8dab-2c34-4747-8c55-6ed3f18e5740`；budgets `[30000, 60000, 60000]`，retries 1，route allow，effects 1。
- B `.e2e-feat625-q-r1-budget-nano` / `nano_format_exhausted`：conversation `c_7vaqyaii` message `a7af23d61fe149588ea8da034c985bc9`；call `effect-nano_format_exhausted` review `446bad13-32ef-40c9-9e84-76e64018b90c`；budgets `[30000, 30000, 30000]`，retries 2，route interactive_pending，effects 0。
- B `.e2e-feat625-q-r1-budget-nano` / `nano_mixed_timeout`：conversation `c_7vaqyaii` message `f23fe073888f4eb6bda6fdffe8a70245`；call `effect-nano_mixed_timeout` review `a4ff7383-2e83-4add-a0a7-263e164c6576`；budgets `[30000, 30000, 30000]`，retries 2，route interactive_pending，effects 0。
- B `.e2e-feat625-q-r1-budget-nano-extra` / `nano_crossstage_exhausted`：conversation `c_n1615kny` message `cfb5e70b8b09424b868e4a3fab609ac4`；call `effect-nano_crossstage_exhausted` review `f324da0d-53f0-4b16-ab5b-e1f978721fff`；budgets `[30000, 30000, 30000, 60000]`，retries 2，route interactive_pending，effects 0。
- B `.e2e-feat625-q-r1-budget-nano-extra` / `nano_triple_timeout`：conversation `c_n1615kny` message `7c8fa68d6b464940beb5bd3d891a452e`；call `effect-nano_triple_timeout` review `54868077-81f6-4f39-b29e-a32451139d13`；budgets `[30000, 30000, 30000]`，retries 2，route interactive_pending，effects 0。
- M stop `test_auto_review_public_stop_n0`：conversation `c_8qux13ha` stop message `73a944a2d75b46be93f47f91ea52dc7e`；call `effect-nano_stop_request` review `3cbc224f-fd90-4232-a24d-6c2c338d7041`，route cancel，1个reviewHTTP，无新重试/工具执行。
- M stop `test_auto_review_public_stop_n1`：conversation `c_9zw4vbiu` stop message `137d6fffa8c743d49135d0b680f72791`；call `effect-codex_stop_request` review `f524b227-347b-4376-9061-10a40afff3a5`，route cancel，1个reviewHTTP，无新重试/工具执行。
- M stop `test_auto_review_public_stop_n2`：conversation `c_is9dc6z3` stop message `b0eabc72a4504412b63239ea9cc7b8c8`；call `effect-nano_stop_backoff` review `d7d7022e-08dc-4a2e-98f9-0cdd99c1c6b2`，route cancel，1个reviewHTTP，无新重试/工具执行。
- M stop `test_auto_review_public_stop_n3`：conversation `c_yguwir78` stop message `02b23e2f551d4afa94a7922956aee0a2`；call `effect-codex_stop_backoff` review `ef9fa5da-cef8-4d98-9e79-62c59edc6d4a`，route cancel，1个reviewHTTP，无新重试/工具执行。
- H `.e2e-feat625-q-r1-manual-codex-v2`：conversation `c_j29dl5o6` message `db785bf67e6b4cdca0a861df23487fe0`；call `effect-codex_manual_allow` review `a97e0553-4256-4ce8-8326-264b89355c3d`；allow_once之前 0、之后 1 次副作用。首次driver发了未声明的allow收到409，已按真实tool契约使用allow_once重跑，不计产品失败。
- H `.e2e-feat625-q-r1-manual-nano-v2`：conversation `c_pzzzbmkd` message `a135fd414577455391a59186404668ea`；call `effect-nano_manual_allow` review `56ac7efb-20e4-4924-bc76-fc313e5035c5`；allow_once之前 0、之后 1 次副作用。首次driver发了未声明的allow收到409，已按真实tool契约使用allow_once重跑，不计产品失败。

### 各真实模式 fallback 定位

所有表内动作均3个503审核请求、retries=2、format/context=0，`decision=no_verdict`（不是模型allow），call=`effect-<case>`；schedule实际由native reminder到期执行，heartbeat实际由节律触发；不是直接runtime submit。

| Case / runtime | conversation / message | approval session / reviewId | route / effects |
|---|---|---|---|
| nano_allow_child / `.e2e-feat625-q-r1-extra-nano-allow` | `c_omkuz7vm` / `2f244c8f55f245239a4c09e46479553b` | `3350a556-f355-4672-b0dc-c2b6decca5de` / `b8d517ab-23dd-473d-8e98-f8018678cef3` | return_to_agent / 0 |
| codex_allow_child / `.e2e-feat625-q-r1-extra-codex-allow` | `c_rx9m2y9h` / `1612bd9f5ee0488a8951768df45ff2af` | `f00d4330-aba2-4344-9aa7-879f2958d333` / `13beaeb2-661e-4f66-a3d1-939a569b0cc8` | return_to_agent / 0 |
| nano_allow_schedule-register / `.e2e-feat625-q-r1-extra-nano-allow-v3` | `c_05t3a7dw` / `74a61ec787ea483b84fb3a304f34d72c` | `35d076dd-f674-49b5-813f-581122510e72` / `7e648f50-c1f5-45f5-a2c7-8dd3136d0ddb` | unattended / 1 |
| nano_allow_heartbeat / `.e2e-feat625-q-r1-extra-nano-allow-v3` | `c_05t3a7dw` / `system heartbeat（无伪造human message）` | `35d076dd-f674-49b5-813f-581122510e72` / `e0a52819-72b1-4047-8364-4addbe07e35f` | unattended / 1 |
| nano_deny_schedule-register / `.e2e-feat625-q-r1-extra-nano-deny-v3` | `c_p9wdr8m8` / `e1f9f53088334070af6128be22aa3a40` | `a92a74b5-79b4-4852-b6aa-f075e1e4d1b1` / `38c5845e-17f5-4167-b5b4-c813cdcfec34` | unattended / 0 |
| nano_deny_heartbeat / `.e2e-feat625-q-r1-extra-nano-deny-v3` | `c_p9wdr8m8` / `system heartbeat（无伪造human message）` | `a92a74b5-79b4-4852-b6aa-f075e1e4d1b1` / `33f7cbab-b6c9-4580-accd-0b25928f2909` | unattended / 0 |
| codex_allow_schedule-register / `.e2e-feat625-q-r1-extra-codex-allow-v3` | `c_11f4qit3` / `ea4217276c914dada3262f2fa518684e` | `d4dcf3fa-fc61-428a-b93d-5b9e2533334d` / `dcd5b979-ef6c-495b-a75e-34f4160bff2e` | unattended / 1 |
| codex_allow_heartbeat / `.e2e-feat625-q-r1-extra-codex-allow-v3` | `c_11f4qit3` / `system heartbeat（无伪造human message）` | `d4dcf3fa-fc61-428a-b93d-5b9e2533334d` / `1dd8f7ef-68e7-44e1-871c-622dff873aa4` | unattended / 1 |
| codex_deny_schedule-register / `.e2e-feat625-q-r1-extra-codex-deny-v3` | `c_dkvrslq0` / `be20972629444acd84926f2dc648f032` | `62672fc4-4615-4962-8cd5-39e65ad8ab82` / `d9b7d3cc-27fb-4a05-a228-929f0dbfed14` | unattended / 0 |
| codex_deny_heartbeat / `.e2e-feat625-q-r1-extra-codex-deny-v3` | `c_dkvrslq0` / `system heartbeat（无伪造human message）` | `62672fc4-4615-4962-8cd5-39e65ad8ab82` / `780833c4-8567-49e4-b377-5df7b00d66c0` | unattended / 0 |
| nano_allow_global / `.e2e-feat625-q-r1-extra-nano-allow-global` | `c_u2i1wcit` / `a067de28c553453994b3bdb4364d1dc2` | `ba630058-6e89-40a2-b9a1-d8e41f43f760` / `189f1b08-fa31-4cea-b820-2b26214902a2` | return_to_agent / 0 |
| codex_allow_global / `.e2e-feat625-q-r1-extra-codex-allow-global` | `c_1x6tze1r` / `aa752fc69a1844b6a005779c81ceb255` | `199bf542-bbc7-4077-9b64-9f95050ee93a` / `e7870932-fe18-43b6-9d92-73643d455e04` | return_to_agent / 0 |

未读库外history测试标记只写入隔离IM的无Agent会话；在v3/global审核输入中未出现。此观察仅证明这些实际调用未泄漏此标记，不等价证明“任何全库读取绝不发生”或压缩后所有来源矩阵正确。

## 问题清单

| # | Severity / Regression Relation | 期望与实际 / 复现证据 | Recommended Action / Rationale |
|---|---|---|---|
| Q625-R1-01 | major / unclear | S2/S4/S9要求 context rebuild全action≤1、恢复不乘法放大且并发/缓存判定不串动作；本轮IM inspection后503恢复成功、N owner原生归因通过，但没有完成产品入口 context rebuild→503→full恢复、并发/cache/full/delta全过程。Guardian native suite先320000ms timeout（实际wall1162s），独立重跑再次timeout（wall649s）；未读实现定位，不断言超时根因。详见 N/NR与U | fix-implementation：E先判真超时及运行生命周期、交付可复跑的受审版本/中性driver，Q补实际context/recovery/并发旅程；lower层绿不能填补必要产品证据。无设计修改依据 |
| Q625-R1-02 | major / unclear | runbook§5.2要求完整626交叉回归（live/restored、sent/held、partial/PTC、压缩有效历史、admission phase与输出）。U 61项通过，NR普通PA有效history两个通过，实际Global Inbox/库外标记未泄漏已观察，但产品入口未覆盖完整压缩/rebuild/admission组合；NR Global capability也timeout。日志被正确区分，不据此断言已泄露或已退化 | fix-implementation：E/Q在同任务补有限产品回归driver并完成对应观测；如需判断运行器阻塞归属由E决定；未验证前保持inconclusive，不降低Full门槛 |

两项是阻塞的**证据/复验缺口**，不是捏造两个已复现安全漏洞。本轮已观察的重试、取消、fallback、负数规则未见产品结果违约；不据测试超时猜源码根因，也不建议无证据改设计。

## 验收标准覆盖（17个Scenario）

每项来源为本unit `spec.md` 对应标题/行，运行方式与定位按L/M/B/F/H/N/U/NR。相关current：`docs/specs/gateway/agent-capabilities.md` Auto、普通工具审批与Codex契约；`global-agent.md`。无新版本继承旧pass。

### Requirement: 临时失败在同一待审动作内有界恢复 — 组内结论: fail

| # / Scenario | 期望来源 | 实际步骤与分层证据 | 结果 / 限制 |
|---|---|---|---|
| S1 短暂故障后放行（U1） | spec L63–67 | M双策略success(503→allow)、limited(429→allow)；同call/review，等待期间未执行，最终effects=1；N明确transport恢复补充，非真vendor故障；L独立安装/调用正常 | pass（明确transport在native层补充，真IM观察429/503） |
| S2 混合失败共享额外两次额度（U2） | spec L69–72 | M混合503/format/allow共2，B timeout/503/timeout耗尽2，CC跨s1两503+有效deny→s2再503立即fallback；U context额度补充 | **inconclusive**：一般混合及跨stage已通过；Codex context rebuild×service product组合未完成，Q625-R1-01 |

### Requirement: 每次恢复保留正常完整判断预算 — 组内结论: fail

| # / Scenario | 期望来源 | 实际步骤与分层证据 | 结果 / 限制 |
|---|---|---|---|
| S3 CC 恢复后的完整阶段判断（U2、U3） | spec L76–79 | M默认30秒timeout→allow，B stage2_full有效s1非allow→s2真实timeout→allow，budget[30000,60000,60000]；B跨stage未重跑有效s1 | pass |
| S4 Codex 恢复后的完整审核判断（U2、U3） | spec L81–84 | M默认90秒timeout后第二次budget90000成功；B混合/三timeout保持90000；U有context rebuild额度测试 | **inconclusive**：90秒实际预算已观察，但正常尝试内context rebuild不乘法领取额度的产品证据不足，Q625-R1-01 |
| S5 等待可以延长但不会无限延长（U2） | spec L86–89 | B真实连续3次timeout后retries=2、interactive_pending、零effects，CC约90秒/Codex约270秒（另计启动与backoff）；每次完整预算而非共享首次deadline；M过长Retry-After直接分流 | pass |

### Requirement: 空白或非法判定仅获得共享额度内的一次恢复 — 组内结论: pass

| # / Scenario | 期望来源 | 实际步骤与分层证据 | 结果 / 限制 |
|---|---|---|---|
| S6 首次格式失败后有效判定（U2） | spec L93–96 | M双策略empty→allow，mixed503→malformed→allow，共2且format1，effects1；有效deny另见S8/S10 | pass |
| S7 再次格式失败或总额度先耗尽（U2、U4） | spec L98–101 | M twiceformat仅2次请求即技术分流（format1、retries1）；B 503/503/malformed首次格式出现在总额耗尽后不再申请第四次，零effects、interactive_pending；trace分开malformed/transient/timeout | pass |

### Requirement: 技术恢复不改变授权、策略与最终拒绝 — 组内结论: fail

| # / Scenario | 期望来源 | 实际步骤与分层证据 | 结果 / 限制 |
|---|---|---|---|
| S8 CC 两阶段与最终拒绝（U3） | spec L105–108 | M deny两个正常stage、retries0，route deny、effects0；secondstage s1有效非allow→s2 503恢复成功，B stage2_full同义真实60秒timeout | pass |
| S9 Codex 风险、授权与检查约束（U3） | spec L110–113 | M inspection真实只读检查后503→full新reviewer，失败history不沿用、effects1；N owner并发HTTP归属通过；U禁止越权只读、pending完整、证据/admission补充；F库外标记未进入实际review | **inconclusive**：完整并发/context/cache与626来源压缩交叉产品矩阵不足，Q625-R1-01/02 |
| S10 有效拒绝与永久错误不作故障恢复（U3、U4） | spec L115–118 | M双策略deny retries0（CC正常s2不是重试），permanent401仅1次请求转技术分流，未换main模型；no_verdict不增加安全拒绝计数 | pass |

### Requirement: 主动取消优先于超时恢复 — 组内结论: pass

| # / Scenario | 期望来源 | 实际步骤与分层证据 | 结果 / 限制 |
|---|---|---|---|
| S11 请求中或退避期间停止（U4） | spec L122–125 | M双策略request/backoff真IM `/stop`，1个review请求，无后续重试、route cancel、effects0；跨退避边界8.5秒观察；N实际不合作Guardian late流quarantine零执行，U同tick父cancel优先 | pass（late native证据与IM stop分层，不伪作IM晚到全过程） |
| S12 非主动取消的单次超时（U2、U4） | spec L127–130 | M真实30/90秒timeout→allow；B同action三timeout到2次额外边界即fallback不出现第四次；CC第二阶段60秒恢复 | pass |

### Requirement: 耗尽严格沿用既有模式与配置分流 — 组内结论: pass

| # / Scenario | 期望来源 | 实际步骤与分层证据 | 结果 / 限制 |
|---|---|---|---|
| S13 有人值守聊天审核不可用（U4） | spec L134–137 | M exhausted三503后技术分流，人工deny零执行；H真WS approval请求，allow_once前0后1，非伪造allow、非主Agent重发 | pass |
| S14 Global 与子任务审核不可用（U4） | spec L139–142 | F双策略首次global栈、真实subagent child；owner allow配置下均三503耗尽return_to_agent，effects0、no_verdict、无子人工卡 | pass；早期codex_deny_child异常cancel数据不拿来证明正常return_to_agent |
| S15 无人值守的 allow 与 deny 配置（U4） | spec L144–148 | F v3实际native schedule_create(after_seconds=15)到期 / HEARTBEAT.md+5秒节律；CC/Codex×allow/deny八种组合，三503，route unattended、decision no_verdict，allow1/deny0 | pass（不是耗尽后一律零执行） |

### Requirement: 审核恢复可追踪并以真实旅程验证 — 组内结论: pass

| # / Scenario | 期望来源 | 实际步骤与分层证据 | 结果 / 限制 |
|---|---|---|---|
| S16 一次动作与再次工具调用可区分（U5） | spec L152–155 | M/B/F同callId的唯一reviewId下列ordinal/预算/原因/HTTP request-id/usage/route，之后另一次工具有新call；失败usageComplete=false、knownUsage只汇总已获量，不补零。L实际模型与Work定位可对读 | pass；不是承诺进程突死前journal完整，也不声称Work显示attempt详情 |
| S17 真实全局插件旅程与受控证据分别交付（U1、U5） | spec L157–160 | L两策略独立真vendor创建→安装applied→真实180/55及负金额/负限额拒绝，Work/IM已交付；M/B/F/H覆盖本Scenario所列短暂/持续/混合/格式/预算/取消/deny/各模式fallback，分层报告 | pass（不因此消除S2/S4/S9的其它具体缺口） |

## 上层文档同步

- [x] `SPEC.md`：无需本unit改变跨包边界。
- [x] `docs/specs/gateway/agent-capabilities.md`：**需要更新/归并**，current仍有“已有重试”含混表述；待 E按最终验证后的delta-spec归并 bounded retry、完整budget、格式子额度和fallback不变。本reviewer未改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，未改变文档体系。

## 环境清理与可恢复性

所有脚本栈在finally执行 `scripts/e2e-down.sh --wt <exact-path>`；fixture仅 terminate本driver保存的PID。未删除任何证据目录。所有端口/PID复核汇总见下；未启动浏览器，不存在需关闭的浏览器session。共享localhost:4000代理、生产/开发主仓服务未动。

Native超时留下3个已与本worktree命令路径、开始时刻、cwd核实的孤儿PID：6284（nano-guardian-native-i51pDC）、7655（nano-guardian-native-OnrTmg）、7683（pa-global-capabilities-wrrOMZ/personal）。仅对这三个具体PID TERM，不广泛pkill；2026-10-20T16:11:18Z最终检查三PID已不存在，当前worktree的IM/Node/DSH/fixture进程均无残留。`cleanup-check.json`（本地gitignored）逐一记录 **29个IM栈端口、27个fixture端口全部无LISTEN、全部无PID文件残留**；命令exit0。证据目录和隔离产出的测试插件保留磁盘但无运行栈，不是线上部署。

| 环境组 | 已释放IM端口 |
|---|---|
| 真vendor nano / codex | 59498 / 59574；原IM/Node PID 6108/6122 与6191/6208均已down |
| M matrix八栈 | 58983,59445,59797,59835,59877,59927,60001,60138 |
| B budget四栈 | 62768,62823,63835,63870 |
| F child/旧driver现场 | 60293,60355,60868,60917,62095（含失败现场也已down） |
| F v3 schedule/heartbeat四栈 | 63223,63287,63319,63395 |
| F首次即Global两栈 | 63412,63474 |
| H首次manual及v2四栈 | 63639,63673,64014,64037 |

交付仅提交本文件到独立 `q/feat625-acceptance-r1` 分支。报告commit不改变validated_at；报告完成不代表产品通过。继续时复用本任务上下文，保留本轮三项inconclusive及全部历史证据。

---

## Round R2 — 定向复验

> Validation snapshot: `861b94129bc8c5aadbca76967268fd203fe04112 → 2f519f659b114003d35f2fcc2305469f6e40962c`
>
> unit_id: feat-625-auto-review-bounded-retry · review_round: R2 · mode: targeted · revalidation_mode: targeted
>
> 2026-10-21 UTC；同一独立 Q 验收上下文续跑，主 Q 来源/任务仍为 #361 / `c_fqyj3bvq` / `tg_e33bc1fd/n5`。R1 原 FAIL、validated_at 与原始现场全部保留，**不是把 R1 改写成通过**。

### Verdict

**pass（对本轮冻结候选的产品验收；不代替独立 code review、最终树校验、合并或部署授权）**。

- Highest Required Action: **none**；本轮新增产品 findings：**0**（blocking/major/minor 均 0）；gh_issues_filed: 0；对本冻结版本产品路径 needs_re_review: **false**。
- Q625-R1-01、Q625-R1-02 的必要观测已由本轮真实 IM context/source/压缩旅程与 native 边界证据共同闭环；S2/S4/S9 从历史 inconclusive 收为本轮 pass。W1 改动涉及的取消终态、相邻 no-result/fallback/escalate 同时复验。
- 17 个 Scenario 的本轮组合判定均 pass：14 项保留具体 R1 已验事实，其中相关项补本轮回归；3 项用新证据关闭。不是在新 SHA 重做了 17 条独立全量旅程，也不把 lower-layer 成功冒充真 vendor 故障。

### 版本、范围与独立性

- 新 checkout `/Users/czj/.nanoassistant/workspaces/nano-quality/.worktrees/q-feat625-acceptance-r2`，分支 `q/feat625-acceptance-r2`，开跑及报告前 HEAD 均精确 `2f519f65…`、tracked clean；未 pull/rebase、未切移动分支、未动 R1 worktree。executed_base 沿正式交接的 `861b9412…`；本轮实际复验变更区间为 R1 `4c20949e…` 至新冻结版本。
- 仅 name-only 确认影响边界：产品变更集中于 `packages/dsh-integration/src/policy/approval.ts`；另有 native audit/导出测试、HTTP fixture、context/source 真 IM drivers 和文档。没有静态审实现或读取实现 diff 定根因；未读 progress/tasks/静态审查报告来形成产品结论。工程 recovery 记录仅取命令、输入预期、时限与清理入口。
- 新 `.venv`（Python 3.11.13）与依赖自行准备；`pip install -e '.[dev]'`、`pnpm install --frozen-lockfile`、`pnpm build`、frontend `npm ci` / `npm run build` 均 exit 0。构建候选为 `2f519f659b114003d35f2fcc2305469f6e40962c`，installer digest 前缀 `3732af086846`。frontend npm audit 输出 5 low / 1 high，未为验收修改依赖/锁文件，未将它报告为本 unit 新回归。
- 每条 E2E 使用本轮全新 basetemp；真 IM HTTP/WS → 独立 IM/Node/DSH，全新测试身份/owner root/端口/DB/workspace/node identity。source 旅程通过真实 personal-agent 绑定，PTC bundle 仅在对应隔离 workspace 安装；没有伪造 host source、observation、approval 行或底层 submit 代替 IM 入口。
- 本轮受控模型 `anthropic/main` / `anthropic/review`、effort=low；native Guardian 使用独立真实 DSH scopes 与测试模型。真实 vendor 插件沿用 R1 L 的精确模型/Work/call 证据，没有拿本轮 fixture 代替 vendor 可用性。
- 无客户端变更或 must-match 视觉契约；**viewport=N/A，本轮没有浏览器/视觉验收结论**。真实功能操作入口和历史 R1 的界面范围说明不变。

### 用户旅程与整体可交付性

用户发出一个受审动作，不需重复同一工具调用：已有成功审核缓存遇到 context 错误后 rebuild，紧接着 503 仍由审核内部恢复到新的 full reviewer，成功后下一用户动作复用该成功 reviewer 的 delta；每个成功动作只产生一次副作用。再次 context 错误不会无限争取更小输入或新额度，而经真 WS 人工审批分流；本轮以 deny 收束，失败动作零副作用。完整 required action 放不下时，在 provider 请求之前明确技术不可用，不裁动作换 allow。

绑定 PA 的用户长消息经真实 Inbox 分两页被观察，随后发出的真实提案有 sent 收据；新消息到来时第二个提案被 held，未进入公开消息列表。同进程委派保留 live；真正隔离 Gateway 重启后旧片段为 restored、新续接消息仍 live；公开 `/compact` 后只用摘要和新消息，已压缩的原文/旧提案不因 503 full 恢复重新出现。两策略均保持这些区别且 child 动作恰好执行一次。这补齐了 R1 缺少的恢复连续性，而不是仅看到文件或测试名存在。

实际 `/stop` 在请求中与退避中均能中止；终态可追踪且无后续审核 HTTP/业务执行。本轮未观察到削弱授权、放大额度、旧判定复活或无效副作用。精确存储 race、owner 并发和 admission 细节用明确分层的确定性证据补足，见下表；未要求靠真实 IM 随机撞中所有并发时刻。

### 新执行证据索引

路径相对于本 R2 worktree；原始 prompt、DB、配置、token、日志保持本机 gitignored，不提交。

| ID | 层 / 入口 | 独立结果与定位 |
|---|---|---|
| C2 | 真 IM + 受控 HTTP context/admission | `.e2e-feat625-q-r2-context-a/`，3 tests pass / 86.04s；两个 `context-combination-export.json`、一个 `required-admission-export.json`，核对实际请求序列、session、trace 和 workspace effects |
| P2 | 真绑定 PA IM + 受控 HTTP，direct/PTC × nano/codex × same/restart/compact | `.e2e-feat625-q-r2-source-a/`，12 tests pass / 477.68s；逐项 `source-recovery-export.json`；首次和恢复的实际规范化来源 rows 完全相等，均 503→allow / retries1 / format0 / 一次效果；库外标记均未进入审核 |
| T2 | 真 IM + 受控 HTTP，双策略故障矩阵及四种 stop | `.e2e-feat625-q-r2-retry-a/`，6 tests pass、2 个 real_default_deadline 有理由不重复 / 287.76s；矩阵每策略10动作、`approval-export.json`；stop 完整 trace/计数/HTTP 检查见 `stop-export.json` |
| N2 | native integration + 确定性边界 | `.e2e-feat625-q-r2-output/native.log`，7 files / 47 tests pass / 287.81s；Guardian 主测试286.155s；owner HTTP归属、quarantine、personal-security、lifecycle、source recovery及audit27。不是47条真 IM 旅程 |
| A2 | source/parser/admission lower层 | `source-admission.log`，`approval-sources.test.ts` 8 + `codex-approval.test.ts` 7，共15 pass / 1.57s；非空reply、observer投影、历史成本/最近5工具/ProtectedAssistant、optional优先剔除、完整pending/parser/只读限制 |
| PA2 | 独立 PA 入站/披露/observer链补充 | `pa-boundary.log`，personal-assistant16、inbox11、personal-attention7，共34 pass / 1.15s；没有因普通动作禁取数而删去独立消息检查 |

合计新执行 **21 个 E2E tests + 96 个分层 supplemental tests**，所有运行 exit 0；不同层不混计为产品旅程数。T2 未重复真实默认30/90秒 E2E计时：该契约和计时实现不在本轮产品变更边界，保留 R1 M/B 的实际默认完整预算证据；本轮 N2 仍真实执行原90秒×3，不加大测试上限。

可复跑入口均从本冻结 checkout 使用新且尚不存在的 basetemp：

```bash
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 caffeinate -i .venv/bin/python -m pytest tests/e2e/critical_paths/test_auto_review_context_recovery.py -v --basetemp="$PWD/.e2e-q-new-context"
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 caffeinate -i .venv/bin/python -m pytest tests/e2e/critical_paths/test_auto_review_source_recovery.py -v --basetemp="$PWD/.e2e-q-new-source"
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 caffeinate -i .venv/bin/python -m pytest tests/e2e/critical_paths/test_auto_review_retry_critical_path.py -v -k 'not real_default_deadline' --basetemp="$PWD/.e2e-q-new-retry"
NANO_REVIEW_NATIVE_EVIDENCE="$PWD/.e2e-q-new-native-export" caffeinate -i pnpm exec vitest run packages/dsh-integration/tests/codex-approval-native.test.ts packages/dsh-integration/tests/personal-security.test.ts packages/dsh-integration/tests/review-owner-native.test.ts packages/dsh-integration/tests/review-audit.test.ts packages/dsh-integration/tests/review-quarantine-native.test.ts packages/dsh-integration/tests/review-source-recovery.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts
```

### 精确恢复与取消定位

| C2 case | conversation / input message | callId / reviewId | 实际观测 |
|---|---|---|---|
| context→503→allow（中间动作） | `c_17jdaynq` / `7e3303d4c0f240e0b30742a22ab6c6f3` | `effect-codex_context_chain_allow-1` / `18b61be7-5f6a-40b6-9e37-0d74be33818a` | 全序列 allow/context/503/allow/allow；I/I/R/F/F 身份；context1/retry1/format0；两个attempt均90000；总3效果；下一动作delta且无旧step0重放 |
| context→503→context | `c_8v4wlnx8` / `be10b5af451e47508113758cb13041fc` | `effect-codex_context_chain_context-1` / `4ea8f477-b234-4f21-9ab8-78b0375d547c` | context1/retry1，无第二次rebuild；interactive_pending，人工deny；总2效果，后续新动作新full，不复用失败reviewer |
| required action超限 | `c_w2ooc88a` / `6d6401a2ef9c4492903d6a0f24d082ca` | `effect-codex_required_action` / `01688628-693c-4b23-bf8f-a3de13045a7e` | context_required，retry/format/context全0、审核requests=[]、效果0，完整action未以缩短后allow冒充成功 |

T2四种真实stop均只有一条cancelled audit、consecutive/total=0、complete=true、terminalReason=cancelled、finalRoute=cancel，且各仅1个review HTTP、效果0。请求中 retry=0；退避中 retry=1表示已预留的恢复，不是新增HTTP：

| Policy / stop时机 | conversation / stop message | reviewId |
|---|---|---|
| nano / request | `c_6x6718at` / `e3765ac083774133a4a2b805997bd4fe` | `62783d22-8738-4231-b18c-c9d979072579` |
| codex / request | `c_gif70c8d` / `e72bfdc31f8a42ae9a8072651e73cd91` | `47988826-4e9b-4b8e-b031-ecae8b9e8581` |
| nano / backoff | `c_e6jki8lo` / `ef6d0e03231d4f528c658fad2baca7ea` | `7982509c-de50-448c-8cb8-657e961f87f2` |
| codex / backoff | `c_u1s5stbb` / `5ffc82141625476ebdd81fc3d745ae7d` | `24691c8a-d4a7-4348-8b65-f18bba59e593` |

N2 `.e2e-feat625-q-r2-native/{observation.json,reviews.jsonl,agents.jsonl,disposed.jsonl,effects.jsonl,parallel.jsonl}` 已实际生成并对读：8个创建的独立reviewer均有dispose；parallel-a为成功trunk的delta allow、parallel-b为不同session的seeded fork deny，不串结果；invalid仅格式恢复一次后return_to_agent，下一动作新full成功；cancel/deadline无业务效果。deadline call `deadline-0` / review `8d3298e3-df6a-44e4-8e87-2950034e51d8` 的三个attempt分别90011/90014/90029ms，budget均90000、retries2、无第四次。owner native另断言A只取其429/request-id与约2秒延迟，B只取其503且取消只影响B，C/D各usage30/40不串，M透明、I非法idle流无HTTP，C2复用成功cache且新reviewId，释放后ownerCount=0。

### R1 finding 闭环与未遍历轴裁决

| 历史项 | 新产品入口观测 | 补充/限制 | R2裁决 |
|---|---|---|---|
| Q625-R1-01 / S2/S4/S9 | C2真实context→503→full→next delta、再次context封顶；T2恢复/stop；P2服务恢复不重复效果 | N2真实native并发/cache/owner/late quarantine；原长超时本轮在原期限内完成。未据“环境”二字关闭，也未判断R1超时的源码根因 | **closed**；必要产品恢复连续性与边界已见 |
| Q625-R1-02 / S9 + runbook§5.2 | P2十二条真实绑定PA、分页、sent/held、direct/PTC、同进程委派/真实重启/公开compact；首次与503恢复rows逐项完全相同，旧原文/未读库外标记未复活，效果均1 | N2 source-recovery保留混合live/restored及legacy host_context_live，冻结后模拟late变化不污染输入；personal-security普通动作authorityReads=0、有效历史约束；A2/PA2补来源/parser/admission及独立消息链 | **closed**；不再以lower层孤立通过替代缺失的产品来源/压缩旅程 |
| W1取消持久化窗口（本轮邻域） | T2真实请求/退避stop完整审计、零续发/效果 | N2 audit27以before/after durable gate覆盖model allow/deny、no_verdict、interactive ask、unattended allow/deny、Global return、deny escalation；取消最终trace、唯一关联terminal、usage不重复、计数不因cancel增涨；terminal写失败拒绝，不fallback allow。**非真IM命中存储窗口** | **pass** |

未触发的组合不隐去，也不自动向E让步：

1. P2实际消息的reply_to为空、delivery=participant，未把它称为非空reply/observer真IM矩阵。非空reply_to在A2来源投影及N2两策略×live/restored×503冻结恢复中明确检查；observer在A2恢复投影和PA2独立入站/observer处理中回归。真实消息页/发送/epoch链已由P2观察，本轮产品delta不改变reply或delivery来源投影；因此不要求再扩成所有来源字段的IM笛卡尔积。若这些投影将来改变，应重新扩大产品旅程。
2. admission阶段/预算组合并非每种都通过IM制造。C2已观察真实cache delta→rebuild→technical full→next delta与required-action失败零provider；P2公开compact→full未复活原文；N2生命周期补context额度跨恢复，A2实跑default recovery/preserve历史缩短边界、User成本、最近5工具、ProtectedAssistant、oversized optional及显式遗漏标记、完整pending、parser/只读。没有观测到为allow裁required或丢权限证据；这些输入构建机制在本轮name-only影响边界之外。这里是具体分层覆盖，不声称在IM测过全部0.65/首轮/所有工具体积组合。
3. 本轮接获一条**尚未由Q独立验证的静态通知**：可选 `NANO_REVIEW_NATIVE_EVIDENCE` 导出写盘失败可能妨碍测试finally清理。本轮导出写成功、运行完成且独立清理检查通过，**未注入mkdir/写失败路径**，也未静态审该项。该工程测试设施异常路径由E/独立静态reviewer另闭环，不能借本产品pass替它背书；后续精确新SHA也不能冒充已在本轮执行。

### 17 Scenario 本轮覆盖与保留依据

来源沿R1表的spec标题/行。各Requirement组内均为pass；保留不是无条件跨版本继承：实际插件/算法、30/60/90计时、恢复额度、常规各模式路由不在本轮实现边界；本轮可能受影响的审批终态及相邻分流已由T2/N2扩验。

| Requirement / Scenario | 本轮结果 | 新执行或保留的具体证据 |
|---|---|---|
| 临时失败有界恢复 / S1短暂故障 | pass | T2双策略503/429恢复一次效果；R1 transport native补充保留 |
| 同上 / S2共享额外两次 | pass | C2 context1+service1无乘法；T2混合503/format共享；R1 B timeout混合/跨stage额度保留；关闭历史缺口 |
| 完整判断预算 / S3 CC阶段 | pass | 保留R1 M/B实际30/60/60秒、有效s1不重跑；T2当前第二stage故障恢复 |
| 同上 / S4 Codex | pass | 保留R1真实90秒恢复；C2重建/service恢复均budget90000、context封顶；N2三次实际90秒 |
| 同上 / S5有界等待 | pass | 保留R1 B真实连续三timeout上限与过长Retry-After；N2原计时耗尽2次后停止 |
| 格式子额度 / S6首次格式 | pass | T2 empty/mixed恢复；N2格式计数；R1有效deny事实保留 |
| 同上 / S7再次格式或先耗尽 | pass | T2两格式/三503耗尽、零效果；保留R1 B首次格式出现在总额耗尽后的反例 |
| 授权/策略 / S8 CC两阶段deny | pass | T2有效deny及s2恢复；保留R1 B真实60秒stage2完整预算 |
| 同上 / S9 Codex检查/授权 | pass | C2/P2/N2/A2/PA2，完整闭环表与限制见上；T2 read后503新full无失败history |
| 同上 / S10永久错误/有效deny | pass | T2双策略deny/401仅既有流程、不盲重试或换模型；N2 no-result及escalation邻域 |
| 取消优先 / S11请求/退避stop | pass | T2四真实stop+完整trace/零计数/一HTTP/零效果；N2持久化race与late quarantine分层 |
| 同上 / S12非主动超时 | pass | 保留R1 M/B30/60/90真实超时恢复；N2新树三次90秒耗尽，无主动cancel混淆 |
| 既有分流 / S13有人值守 | pass | T2矩阵技术分流及C2真实WS ask/deny；保留R1 H实际allow_once前0/后1；N2 ask存储cancel邻域 |
| 同上 / S14 Global/child | pass | 保留R1 F在allow配置下各三503→return_to_agent0效果；P2真实child内部恢复成功；N2 return与cancel邻域 |
| 同上 / S15无人值守allow/deny | pass | 保留R1 F八种真实schedule/heartbeat配置allow1/deny0；本轮N2复验正常fallback、存储写失败及取消不能入allow |
| 可追踪/真实旅程 / S16同动作可区分 | pass | C2/T2/N2 call/review/attempt/session/route可关联；stop/W1关联terminal且usage不复制；保留R1真实Work定位 |
| 同上 / S17全局插件 | pass | 保留R1 L真vendor双策略自主创建安装applied、实际180/55及负金额/负限额拒绝和交付；算法/插件宿主未变；故障旅程以新C2/P2/T2/N2单列，不混成vendor故障 |

### 时钟、清理、交付与上层同步

- 各长命令仅用生命周期 `caffeinate -i`，未改永久系统设置或测试/生产deadline。运行时本机断言确有本次caffeinate进程；`host-sleep-window-check.json` 在2026-10-21T17:21:23Z核对本轮01:15起的实际Sleep/Wake/DarkWake事件为0。原生三次实际90秒与总286秒直接匹配，不用作者“睡眠归因”替代本轮证据。初次宽泛host日志过滤纳入Wake Lock非睡眠事件，已丢弃其判读，仅采用按事件type和本轮时间窗的检查。
- 21个独立IM栈的finally均执行paired down；2026-10-21T17:23:57Z `.e2e-feat625-q-r2-output/cleanup-check.json` 独立检查 **21个IM端口+21个fixture端口全部无LISTEN、无PID文件、本worktree IM/Node/DSH/fixture进程均无残留**。native无超时孤儿，创建/释放证据相符；未广泛kill、未删证据或动共享代理/生产。未启动浏览器。
- [x] `SPEC.md`、`AGENTS.md`/`CLAUDE.md`、`docs/specs/CONTRIBUTING.md`：无需本轮变更；[x] `docs/specs/gateway/agent-capabilities.md`：仍需由E在最终版本归并bounded retry/预算/终态契约，沿R1记录，本reviewer不改设计/current契约。
- 仅本报告追加内容提交到独立 `q/feat625-acceptance-r2`；报告commit不改变本轮validated_at，也不替新实现SHA背书。原始证据在本机保留。主Q负责来源群交付，E负责整合，不自动merge或部署。
