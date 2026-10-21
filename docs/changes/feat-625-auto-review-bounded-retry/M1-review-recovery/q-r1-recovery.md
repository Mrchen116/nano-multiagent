# Q R1 inconclusive 恢复记录（工程事实，不是 Q verdict）

## 范围与历史证据

- 开始于报告整合 HEAD `afd71206deb2220b0cddcd7840588667b62340e5`；该轮未改产品源码。保留 [acceptance R1](../acceptance.md) 的历史 FAIL、14 pass / 3 inconclusive 和原 major findings，不把底层复跑写成 Q 产品通过。
- Q 已独立确认其自生成业务插件的两次正例 180/55 **以及负例拒绝**。作者早先另一个 clamp 示例不能否定 Q 的不同产物，也不回写成作者旧旅程当时符合全部业务规则。
- 本轮目的：定位原 native 超时，补充可提交、可复跑、保留精确请求/审计与真实 IM 入口的观察驱动。受控 HTTP 并非真实 vendor，不新加授权查询、不重读消息库、不修改生产 timeout，不以通过断言代替独立 Q。

## 原 native 超时的直接因果证据

只读核对 Q 原始 `native.log` / `native-recheck.log`、其残留隔离 native domain，以及宿主 `pmset -g log`。没有更改系统节能设置、没有重跑/改动 Q worktree。

| 观察 | 原始时间/事实 | 与宿主 sleep 的对应 |
|---|---|---|
| Guardian 第一轮 deadline attempt 1、2 | 1792506600394→1792506690418、1792506690911→1792506780921，各约 90s | 正常保持默认完整预算 |
| 第三次 attempt | 1792506781985→1792507759539，约 977s；整个 test 1162266ms 后触发 320000ms timeout | `2026-10-20 22:33:51 Sleep`→`22:49:19 DarkWake`，约 928s，直接跨越该 90s attempt |
| native recheck Guardian attempt | 1792508820482→1792509466689，约 646s；Global capability test 同时约 646s 超过其 30s | `23:07:01 Sleep`→`23:17:46 DarkWake`，约 645s，两个无共同审核 timer 的测试一同停止推进 |
| 资源记录 | 两轮 reviewer created/disposed 分别 8/8、6/6；效果文件均为预期 5 条；deadline 无 allow | 没有由这些日志确认源码死锁或晚到 allow；也不据此声称其他清理组合没有缺陷 |

这是机器 suspend 导致 event-loop 与测试 deadline 同时停顿的强直接证据，**不是“所有超时都是环境”泛化**，也不能填补 context/source 产品组合的缺口。

### 原测试、不延时的 awake 复跑

```sh
caffeinate -i pnpm exec vitest run \
  packages/dsh-integration/tests/codex-approval-native.test.ts \
  packages/dsh-integration/tests/personal-security.test.ts
```

结果：**2 files / 7 tests passed，275.18s，exit 0**；Guardian 274978ms，个人安全六项 7954ms（Global capability 3816ms）。保留原 320000ms / 30000ms 测试 timeout 和默认 90s×3 审核预算。`caffeinate -i` 仅给命令生命周期添加 idle-sleep assertion，不修改永久设置、不强制唤醒、不改运行时代码。可在 Q 本机独立复跑；显式手工 sleep 仍可能暂停进程，不把 sleep assertion 当自动测试成功。

## 真 IM context rebuild → 503 → full → 下一次 delta

可复跑命令：

```sh
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 caffeinate -i .venv/bin/python -m pytest \
  tests/e2e/critical_paths/test_auto_review_context_recovery.py -q \
  --basetemp="$PWD/.e2e-feat625-context-review"
```

驱动以三条真实 IM 消息在同会话依次执行三个 bash；真实本地 Anthropic HTTP 序列为 `allow → 400 prompt-too-long → 503 → allow → allow`。不 throw 自造内部 context 错误、不直接调用 controller、不改 context quota。

中性观察/断言：首 full 成功留下 cache；下一 delta 触发标准 provider context 错误并 rebuild，rebuild 的 503 使其 dispose 后新建 full；成功后的第三动作仍复用新 cache。第二动作 durable trace `contextRebuilds=1 / retriesUsed=1 / formatRetriesUsed=0`；HTTP native identity 为 `I,I,R,F,F`，R/F 各为真实不同 reviewer；full 仍含第一条用户证据，随后 delta 不再次投影第一条；效果文件恰三条。导出包含真实 input message IDs、conversation、每步 approval/trace 与精确 HTTP request messages/system。

工程第一次单场景执行：**1 passed / 14.82s / exit 0**；最终扩大为 **3 passed / 60.97s / exit 0**，本地 gitignored locator `.e2e-feat625-context-final/`，包含两份 `context-combination-export.json` 和一份 `required-admission-export.json`：

- recovered=allow：上述 `I,I,R,F,F`，副作用恰三条。
- recovered=context：`allow → context → 503 → context → allow`，第二次 context 不能再 rebuild；第二动作 `contextRebuilds=1 / retriesUsed=1 / terminalReason=context`，ordinary permission fallback 由真实用户 API deny，工具零执行；第三动作新 full，不能复用失败 cache，总效果两条。
- required action：公开配置 review 模型 window=20000，主模型发完整 action（5000 次固定注释证据），不改 tokenizer 或内部 admission。完整 action 无法放下时 `terminalReason=context_required`、retry/format=0、provider review HTTP=0、无 allow/无效果；普通 permission deny 闭合。不是通过 service retry 裁掉动作换 allow。

初次组合断言曾假定新 full 最后一条 message 必为业务行；实际 native 在 full 末尾附 workspace 指令。最终改为在完整 full messages 查新动作，只对真实 delta 的末条验证非重复前缀；没有改产品输入或配额。早期 action_size=25000 超过原生帧可观察范围、未取得可判定 trace，不能当 admission 成功；最终受控体积 5000 仍足够超20k声明窗口且得到明确审计。以上是工程观测，不改 Q 原 inconclusive。

## 真实 runtime 并发/缓存与 W1 定向复验入口

```sh
NANO_REVIEW_NATIVE_EVIDENCE="$PWD/.e2e-feat625-native-review" caffeinate -i pnpm exec vitest run \
  packages/dsh-integration/tests/codex-approval-native.test.ts \
  packages/dsh-integration/tests/personal-security.test.ts \
  packages/dsh-integration/tests/review-owner-native.test.ts \
  packages/dsh-integration/tests/review-audit.test.ts \
  packages/dsh-integration/tests/review-quarantine-native.test.ts \
  packages/dsh-integration/tests/review-source-recovery.test.ts \
  packages/dsh-integration/tests/codex-approval-lifecycle.test.ts
```

工程实际：**7 files / 47 tests passed / 277.01s / exit 0**，Guardian 276683ms；原超时文件与 Global capability 都未改 timeout。新增的 `NANO_REVIEW_NATIVE_EVIDENCE` 只是 test opt-in 导出：`observation.json`、精确 `reviews.jsonl`、实际 `agents/disposed/effects/parallel.jsonl`；普通运行仍按原 finally 清理临时 home。它不更改模型、scope、timer、断言、controller 或 fallback。Q 必须给全新 gitignored 目录，不把不同轮的文件混写。

- `codex-approval-native` 使用真正 native reviewer，而非同一 parent ID 假扮：cache 初 full、后 delta、并发两个 inner checks 分别 delta/fork、一个 allow 一个 deny；失败后新 full、标准 context rebuild；最终 native created=disposed，业务 effect 恰 first/inspect/parallel/after-failure/overflow 五项。与真 IM context 组合驱动是不同层证据，二者分开核对。
- `review-owner-native` 使用真实 agents.create + barrier + HTTP，idle cache 与 active trunk/fork/另 parent/主流/CC 同时发流；检查相同 carrier ID 的手工 CC 与主流透明、429 header/delay/usage 不串、取消一支不影响另一支、恢复新 full 身份及下一动作重新绑定。不是纯 mock scope 测试。
- `review-quarantine-native` 保留真实原始流不合作 12s/5s cleanup；晚 allow 不执行，quarantine 内不得创建第二 reviewer，实际 drain/dispose 后新动作才成功。
- `review-audit` 的 27 项覆盖 W1 延迟终态写入前后：cancel 与 allow/no-result/fallback/escalate 的最终一致性、原始 verdict/usage 保留且不重复成本、不增加拒绝计数、原 detailed row 与 linked cancellation 终态同一原子 update，以及写失败不 return allow。**这是可控存储承诺的 facade 测试，不冒充真 IM 刚好击中持久化 race**。真 IM request/backoff stop 在独立入口复验；原 Q 已通过的其他模式 fallback 仍按原版本归属 retained。

## 证据边界与清理

- HTTP fixture 原本只记 header/ordinal；本轮新增受控 reviewer 的精确 `messages/system`。这都是该隔离栈的人造测试输入，但包含完整 prompt，仍只写 gitignored 临时目录，不提交原始 body、token、DB、config。
- 每个 pytest driver 自己创建 fixture 进程和完整隔离 Node/IM/DSH 栈；`finally` 用 e2e-down 清理，fixture 只终止保存的 PID；down 后复查自己的 IM health 不可达。失败导出同样留在 pytest basetemp，不能用下一轮相同 basetemp 覆盖旧证据。
- 全部场景关闭后按自己的 stack/fixture 命令行与端口核对；不以“finally 被调用”单独证明底层 drain，native quarantine 的实际 created/disposed/drain 另查上一节。

## 真 PA 来源、PTC、真实恢复与有效上下文矩阵

```sh
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 caffeinate -i .venv/bin/python -m pytest \
  tests/e2e/critical_paths/test_auto_review_source_recovery.py -q \
  --basetemp="$PWD/.e2e-feat625-source-review"
```

入口/输入：使用隔离 IM 的真实 owner 登录，新建 owner 绑定 PA（`POST /im/v1/personal-agent`，不是普通 Global 冒充 PA）。先在另一未观察群写大段库内历史标记，再向 PA 发 7500+ 字符用户消息；主模型仅脚本选择公开 `inbox check/read`、`send_message`、`subagent` 和 `bash`，读页使用真实 opaque cursor。没有注入 Inbox result、source/observation 标签、host_context、审批行或 compact event。

| 轴/情境 | 实际动作与独立可核对的预期 |
|---|---|
| 策略 | nano / codex 各自真正审核；子 bash 效果动作固定 `503 → allow`，每次新 full 重试。review HTTP 的完整 messages/system、native identity、durable approvals 与实际文件效果一同导出 |
| 同 epoch | live Inbox → 同进程真实同步 subagent → 子动作503→full；两页观察在首次和恢复中均 live，规范化 inbox rows 逐字相等 |
| 真跨进程恢复 | 先等公开 work view main idle，再经现有 restart_gateway 重启**本测试的**Gateway；等节点重连、发真实 Continue 入站、读真实 Inbox 再委派。旧两页 restored，新 Continue live；503前后逐项不变 |
| 真压缩 | idle 后用户公开 `/compact`，由真正 compaction purpose HTTP 返回仅目标的 summary；等产品“已压缩”响应再读新 Continue 并委派。首次及恢复 full 只含新live Inbox和summary，旧输入message ID、两端正文与sent proposal均不能复活 |
| direct / PTC | direct 两页各一次；PTC 使用公开 plugin_manager 安装 test workspace bundle，其唯一插件语句为 `ctx.tools.presentAs('both')`，不改权限。一次真正 `run_code → tools.inbox` 的分页事实、下一页 direct 和一次 distinct direct read 都保留；不同call的同页正文不当重复删掉；Codex同call不得同时泛化投影tool_result |
| sent / held | 两路径均有真正sent proposal。PTC同epoch另在真实第一sent后发新用户消息，等host Inbox确实接收后release HTTP barrier；第二send真正返回held_for_revalidation，proposal不在公开消息中，继续读新用户事实后委派。不得把held当sent |
| partial / identity | 原message分为2页（part1/2、真实next_cursor）；完整sender.type=user、is_owner、delivery=participant与原message ID保留。PTC额外distinct读保留自己的call ID。source rows在503前/后严格相等；库内未观察标记不出现，文件效果恰一次 |

最终工程实际：**12 passed / 283.47s / exit 0**（2策略 × 3 epoch × 2 flow），`.e2e-feat625-source-final/` 每个场景留 `source-recovery-export.json`、fixture.jsonl 与 stack日志/domain。非空reply链/observer/PA独立入站链、旧格式host_context_live和authorization读取0还有现存分层回归入口，不伪称这12场景制造了所有这些情境。PTC第一页被真实观察后仍有未消费fragment，因此模型显式执行distinct direct read完成host消费；保留两个不同call，未改host消费或取消重验证规则。

### 如何独立运行与判断（不采纳作者 verdict）

- 前置：本worktree依赖/本地构建已就绪，Python虚拟环境含 pytest/httpx/pytest-timeout，正常 `scripts/e2e-up.sh` 能启动；上述变量只开启隔离栈。macOS用命令生命周期 `caffeinate -i` 防止已定位的idle sleep；非macOS去掉该前缀但保持测试内deadline不变。
- 单项可选：pytest `-k 'direct and restart and codex'`、`-k 'ptc and same and nano'`、`-k compact`；context `-k required_action` / `-k next_delta`。每次用**未存在的新basetemp目录**；pytest会清理既有basetemp，不覆盖旧证据。
- 每source场景上界180s（held barrier15s、最终IM poll120s）；context每chain180s/required120s；全12source正常约5分钟，允许逐项取证，不通过调大生产预算取得绿灯。native Guardian保留320s/90s×3，所列7文件正常约277s。
- 原始定位：每个pytest场景目录内 `stack/gateway.log`、`stack/.im.log`、`.e2e-ports.env`、`fixture.jsonl`、`.dsh-runtime/**/storages/nano_approval/sessions/*.json`；exports只归集该动作，不改domain。若断言前失败，fixture和stack日志仍留本次目录；不要只凭pytest尾行忽略实际请求/效果。
- 故障清理：驱动finally调用 `scripts/e2e-down.sh --wt <本场景stack>` 并关闭保存的fixture PID；下线后IM health必须不可达。若命令被系统强杀，先核对该目录 `.e2e-ports.env` / PID命令行和cwd，再只清理本场景；不可killall/杀生产或Q进程。早期一次PA创建504/Cordis HMR初始化失败及一个空启动日志的孤立runtime已按cwd核实并清理，后续最小agent_ids=['e2e']重新起栈；不把该设施失败算产品pass，也不归因于sleep。

## 626 admission/来源与 W1 的分层边界

```sh
caffeinate -i pnpm exec vitest run \
  packages/dsh-integration/tests/approval-sources.test.ts \
  packages/dsh-integration/tests/codex-approval.test.ts \
  packages/dsh-integration/tests/review-audit.test.ts \
  packages/dsh-integration/tests/review-source-recovery.test.ts \
  packages/dsh-integration/tests/codex-approval-lifecycle.test.ts
```

本轮实际 **5 files / 53 tests passed / 1.18s / exit 0**；与上列47 native组合有交集，不相加成独立测试数。预算/保护策略的精确行边界仍由这些长期控制输入测试观察：User计入message allowance、最近5tool/ProtectedAssistant、先删超大optional、显式guardian_truncated、required完整动作不可裁；同epoch旧格式live/跨epochrestored、partial/reply、codex去重。零额外全库查询/PA独立入站链/observer与owner DM豁免由前述47项组合内personal-security六项检查，并非此53项都覆盖。真IM context/source驱动补组合输入与真实冻结rows证据；不把分层测试叫成vendor旅程或声称每个admission保护类别都已在真IM故障里触发。

W1持久化精确race仍以27项deferred存储门控测试为准；保留静态R2 closure，不把本轮真IM stop替代写入前/后gate。Q针对no-result/fallback/escalate定向复验可先跑27项并查首次original verdict/usage、唯一详细trace finalRoute=cancel、linked cancellation同reviewId、fallbackOutcome移除、拒绝计数不因取消新增、写失败拒绝；再用普通真IMstop核对公开路由。Q已通过的其他执行模式fallback与真实vendor业务插件保留在原报告，不无关重做或重解释。

### W1本轮真IM stop及旧fallback回归

```sh
NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 caffeinate -i .venv/bin/python -m pytest \
  tests/e2e/critical_paths/test_auto_review_retry_critical_path.py \
  -k 'not real_default_deadline' -q \
  --basetemp="$PWD/.e2e-feat625-stop-review"
```

实际 **6 passed / 2 deselected / 223.23s / exit 0**，`.e2e-feat625-stop-final/`。两策略各10真实HTTP恢复/有效deny/永久不可用/格式/限流/inspection场景，以及请求中和8秒退避中4条真正 `/stop`；后者新增断言 durable trace `finalRoute=cancel / terminalReason=cancelled / complete=true`、拒绝total/consecutive均0，无allow，跨原退避边界HTTP仍只有1次，业务effect0。stop-export现在同时保留完整approvals与实际requests，不只作者trace摘要。默认30/90s成功恢复本轮未重复（两条deselected），保留原Q和工程默认时长证据；native90s×3本轮确已重跑。

## 最终设施校验与清理

- `pytest tests/contract -q`：**28 passed / 0.64s / exit0**；曾因已有主驱动新增导出后403行触发400行门禁，压缩仅文件顶端重复说明为单行后398行，通过且无行为改变，不忽略失败或调整门禁。
- 五个改动Python文件 ruff check/format-check均exit0；`scripts/docs-check` **251 Markdown / 67 routes / exit0**；`git diff --cached --check` exit0。
- 最后按本worktree `.e2e-` 路径核对进程命令行，自己的隔离IM/Node/fixture活动进程 **0**；各场景finally已检查本栈IM health不可达。所有后台job均收集，没有遗留本轮测试。
- 工作区`async-boundary-validation` Skill追加可复用的真实来源/观察与消费分离/公开压缩与恢复验证配方，不写本unit暂态数据，不属于产品git diff。

## 待独立结论

上述是原 major evidence gaps 的可复跑恢复入口与工程观察，不修改 [acceptance R1](../acceptance.md) 历史 FAIL。产品源码与开始HEAD相同；提交delta仅测试/fixture/本记录和runbook/progress。父E核定新的冻结HEAD后交原Q节点定向复验：context/full/cache/concurrency、626来源/压缩/admission组合、W1取消终态/no-result/fallback/escalate；静态审查仅按新增测试设施影响判断是否需patch审。没有Q pass，不canonical/archive/Ready PR，不merge/deploy。
