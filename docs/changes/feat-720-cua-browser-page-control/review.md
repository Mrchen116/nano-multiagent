# feat-720 — 实施验证与独立审查状态

本文件由实施 owner 串行归集。**当前未完成独立实施审查，未通过发布验收，不可据此发布。** 设计审查记录见 [design-review.md](design-review.md)；历史直接驱动验证见 [M1 evidence](M1-page-actions/evidence/real-driver-checks.md)。

## 版本与有效范围

- 当前实现/测试版本：`054ab52ea381dd9740f4c41fe4dbe58f48da24b9`，分支 `codex/feat-720`；本轮配置例外已由人类批准，独立 code/Context/corrected-delta 审查进行中，尚非发布冻结。
- 集成的 develop 基线：最初为 `eeaea47921806936da20e78c9ed96167716f5037`；现已用 merge `a904d32faf813430ef620bb19af18ec2331c41f4` 无冲突集成 `94d663626`。该段仅新增 bugfix-729/731/732 三项 unit 文档、无源码/配置/锁文件变化，既有源测试证据不因该 merge 失效；最终 PR 前仍须核对目标分支后续增量。
- `a1fab20f4` 修复等待驱动 probe 期间资格失效仍会 prepare 的竞态，并按行为拆分 browser-control/lifecycle 测试。`de3b838a1` 再修复真实产品暴露的 Cordis 服务注入接线错误；`fa6c7ad68` 修复非作者 reviewer 发现的登记失败后 cleanup 失败却丢失占额漏洞；`054ab52ea` 再修复已排队销毁状态被提前回收。旧 daily 最初从 `4804e785e` 启动，首个失败产品样本确已加载 `a1fab20f4`；最新 Sol 样本 A 已核实加载当前 `054ab52ea` package 构建，不拿旧进程当新版本验收。
- Gate 2 R7 只批准 `9612ea5d1` 的设计，不是实现或真实旅程批准。
- 本轮自检均由实施 owner 执行，不冒充独立 reviewer。

## 已完成的 owner 验证

| 范围 | 结果与边界 | 本机原件定位（不入库） |
|---|---|---|
| 修复前有意义失败 | 8 failed / 43 passed，覆盖主窗口丢失后错误采纳弹窗、窗口错误吞掉、异步消费轮次锁、混合窗口归还、销毁并发、缺少 Inbox 原始时间 seam | `/tmp/feat-720-red-tests.log` |
| 截图目录、驱动诊断、错误传输回归 | 分别先复现 symlink 越界、输入文本出现在空响应诊断、原生工具仅传 `Error.message` 导致附加证据不可见，再修复 | `/tmp/feat-720-screenshot-red.log`、`/tmp/feat-720-driver-red.log`、`/tmp/feat-720-error-evidence-red.log` |
| 窄测试 | `4804e785e` 的 browser、approval-sources、PA inbox：98 tests / 9 files 全通过，单 worker、禁止文件并行；不是根目录完整 CI | `/tmp/feat-720-browser-suite-final.log` |
| Inbox→BrowserControl 接线 | `3da5cb40d` 的 browser-control：30 tests 全通过，包含 native/PTC × root/child；系统 wake 单独不启动，live 完整真人 Inbox completion 后才可启动 | `/tmp/feat-720-inbox-browser-integration.log` |
| 构建与类型 | 受影响 DSH/PA typecheck、顺序 workspace build 通过；后续完整链中 workspace build、Node installer candidate、workspace typecheck、evals tsc、iOS runtime check 均已进入后续阶段，未见该阶段错误 | `/tmp/feat-720-typecheck-final.log`、`/tmp/feat-720-build.log`、`/tmp/feat-720-backend-ci.log` L1–51 |
| 文档/Python 静态 | 文档完整性、ruff check、ruff format check 通过；新增本报告后另跑 `git diff --check && ./scripts/docs-check` 通过，最终归档后需按最终版本补验 | `/tmp/feat-720-tooling-static.log` |

窄测试命令：

```sh
pnpm exec vitest run packages/dsh-integration/tests/browser-*.test.ts \
  packages/dsh-integration/tests/approval-sources.test.ts \
  packages/personal-assistant/tests/inbox.test.ts \
  --maxWorkers=1 --no-file-parallelism
```

### 中断后的分组 CI 补验与有效性

2026-11-08 +08，旧完整链在异常共享负载下中断：workspace build → Node installer candidate → workspace typecheck → evals tsc → iOS runtime check 已进入后续阶段；根 Vitest 原始输出 `/tmp/feat-720-backend-ci.log` 止于 L386，`capabilities.test.ts` 6 项中 2 项失败、无最终栈或总汇。旧链仍记为中断，不把后来补验改写为旧链 exit 0，也不增大 timeout 或跳过失败。

父级后续明确分配单组非 GUI 验证窗口；在 `5bc1cfbc2` 代码不变时顺序完成：

| 范围 | 实际结果 | 本机原件定位 |
|---|---|---|
| 原 capabilities 失败重跑 | 6/6 通过，首项 12.53s、末项 5.374s。该窗口未复现旧失败；不因此证明负载是唯一根因或不存在间歇竞态 | `/tmp/feat-720-capabilities-isolated.log` |
| 根 Vitest 剩余集合 | 190 files / 784 tests 全通过，exit 0；复用 33 个版本不变且完整通过文件的 464 tests，覆盖当时全部 223 files / 1248 tests。不是单次 fresh `pnpm test` 全量 exit 0 | `/tmp/feat-720-root-remaining.log` L3720–3726；逐文件版本与来源 `/tmp/feat-720-root-coverage-manifest.json` |
| Python 非 E2E | 134 passed / 1 failed / 28 deselected；唯一失败为本分支新增 browser-control 测试 475 行超过 400 行。未豁免，后续按生命周期行为拆分 | `/tmp/feat-720-python-ci.log` |
| 前端 | 113 files / 1078 tests 全通过、pretest interactive assets 检查通过、exit 0；`npm audit --audit-level=critical` 通过，但仍报 11 个非 critical 漏洞（4 low / 2 moderate / 5 high），不声称零漏洞 | `/tmp/feat-720-frontend-ci.log` L57、L7562–7568 |

### 后续启动门禁竞态：有意义红测与最小修复

owner 静态核对发现 `ensureInstance` 在初次在场判定后 await `driver.probe()`，随后直接 prepare；该等待期间祖先轮次可能过期、关闭、换轮或被 sibling 的真窗口归还消费。无 GUI deferred-driver fixture 在修复前取得 **4 failed / 5 passed**：前三种错误地成功启动，第四种已越过 prepare 后才返回窗口歧义，均不是预计的资格拒绝（`/tmp/feat-720-launch-race-red.log`）。

`a1fab20f4` 在 probe 后、prepare 前无额外 await 地重验同一祖先 session/turn seq、当前在场与消费锁；不借用后来的真人轮次。晚拒绝不调用 prepare 或对未准备 label 调用 end_session，finally 释放预留槽。既有生命周期/并发/冷却测试迁至 browser-lifecycle，browser-control 378 行、新 lifecycle 175 行；不改测试上限。

修复后 **10 files / 106 tests** 全通过（browser 全集、approval-sources、PA inbox，单 worker/无文件并行），包括晚拒绝零 driver call、槽位可被新合格请求使用、等待期间 sibling 消费锁；`/tmp/feat-720-launch-race-green.log`。受影响 DSH typecheck/build、`NANO_TEST_BASE_REF=origin/develop ...pytest tests/contract/test_test_naming_and_size_contract.py -q` **2 passed**、`git diff --check` 均通过。该窄测不替代真实桌面验证。

以上根/前端/Python 的分组证据具有各自版本边界：旧全集不是 `a1fab20f4` 的 fresh 全量证明；新增源码已补受影响窄测与构建，最终 sync、独立审查后须再判断哪些结果有效。Python 原失败已由未放宽规则的窄重验修复；最终归档检查尚未到可运行阶段。单组重型窗口已释放，未经重新协调不新增重型全量。

## 已观察到的真实产品链

最初从 `4804e785e` 构建的代码启动隔离 daily 栈，独立端口、数据库、Gateway config、runtime home、workspace 和节点身份；以下 1–3 为当时的默认态/接线观察。随后已重启本栈 Node/DSH 至 `a1fab20f4`、核实 profile 解析当前 package 与 `NANO_CUA_DRIVER`，再由 headless Playwright 经本栈 Web IM 发起真实产品浏览器尝试。该首次尝试在驱动前失败，**未调用 CuaDriver prepare/click，不是 V2 前台归还成功证据**。

1. 在真实 PA 设置页看到 `browser_read` / `browser_act` 默认均未选中。禁用态的真实 PA 回复为“当前不可调用 browser_read 与 browser_act，没有启用浏览器能力。”；该轮没有浏览器或替代工具调用。另建的隔离 single-thread 测试 Agent 同样观察到两项默认未选中。
2. 通过同一设置 UI 显式选择并保存后，仅发送可用性查询；真实测试 Agent 列出两项能力，未调用浏览器。此项只证明设置可发现/启用，不证明实际浏览器动作链。
3. 真实 PA 原生轨迹的 Inbox `read` call seq25 / 原始 result seq26 保留了真人消息原始 `created_at`，同时带本地化展示时间，participant/user 身份未变；恢复后追加的替换结果不作为新的 live 完成来源。此项证明原始时间已跨 PA→runtime 投影，但不是 browser gate 实际启动或 provider 输入验收。

定位：worktree `.e2e-daily.json` 为本栈清单；默认态 snapshot 为 `.playwright-cli/page-2026-11-07T18-17-54-499Z.yml` L302–303；本轮提取的 PA 轨迹 `/tmp/feat-720-pa-session.jsonl`。以上均为本机测试产物，不提交日志、截图、配置、数据库或认证内容。

### 本次已披露范围内的产品尝试与修复

此前 2026-11-05 直接 CLI 的三启动/弹窗批次确被 `NanoApprovalDenied / classifier_block` 拒绝，原理由为发现抢前台后原授权未覆盖继续重复；旧拒绝没有被抹掉。本轮用户收到具体风险后追问“为什么不能直接去试”，父级结合既有“Chrome 必须验透（…新窗口）”与首次/新窗口可能占前台的原话，撤销其自行附加的 8 分钟预约条件，按已披露的最多 3 启动/2 弹窗范围直接接续，仍接受当前工具检查、意外即停；不是安装/TCC/用户既有 Chrome 的新增授权。共享物理 GUI 由父级在执行者间协调，不再要求用户另约空闲。

首个产品样本（`a1fab20f4`）的 PA 原生 session `06040d4d-5e81-42f4-acab-62f2159ba26c` turn 3：fresh Inbox read seq93/94 保留本次 `created_at=2026-11-08T15:53:22.759Z` 和 user/participant 身份；`browser_act(open)` seq101/102 立即返回 `Error: cannot get property "nanoApproval" without inject`。模型随后把实际错误送回测试聊天并停止，未读取/点击/重开实例。证据 `/tmp/feat720-pa-sample1.jsonl` L96–120；只读前台元数据 `/tmp/feat720-fixture-20261108/foreground.jsonl` 430 个采样只见原 Chrome660/ChatGPT89352，未见新自持 Chrome。此错误不是在场 5 分钟拒绝、分类器判拒或 TCC 缺失。

根因为 NanoRuntime 的同步 `liveHumanTimes` callback 直接从未 inject 的父 `ctx` 读取 `nanoApproval`。`de3b838a1` 改为捕获现有 `ctx.inject(['nanoApproval'])` 解析的服务引用；服务未就绪时返回空时间、仍 fail closed，不增资格或伪造来源。新增 actual installed DSH + probe-sentinel executable 回归先复现同样 Cordis 错误（`/tmp/feat720-inject-red-valid.log`）；该 fixture 从不启动真实 Chrome。修复后 system/heartbeat 轮次在驱动前被拒，host-human 测试输入只到 fake `--version` 探针。package build 和 browser/approval-sources/PA inbox **107 tests / 11 files 全通过**（`/tmp/feat720-inject-green.log`）。最初 fixture 的未知 provider 配置失败另存 `/tmp/feat720-inject-red.log`，不计作有意义红测。后续当前构建已完成 Sol 样本 A 的真实 open，未再现注入错误；popup 与截图消费仍未闭环，见后文。

### 首次登记失败后 cleanup 丢失占额：独立 finding 与修复

非作者 reviewer 在 `de3b838a1` 用无 GUI fake 确认：prepare 已返回 owner pid，首次 `list_windows` 超时、`end_session` 又失败，旧实现吞掉 cleanup 错误并释放 launching 槽、未登记实例也不计 cap，连续三次 read 会在 max=2 时产生三份 prepare。owner 新增回归先取得 **2 failed / 9 passed**（`/tmp/feat720-registration-red.log`）：未返回人工恢复错误、cleanup 也没有一次重试；不把该红测当真实窗口实验。

`fa6c7ad68` 从实际发出 prepare 前保存宿主生成的 label；准备超时/响应缺 pid/登记失败均只清理同一 label，重试一次。清理成功才释放 ownership 并保留原始错误；连续失败返回 `browser_foreground_release_failed`、明确手动关闭提示，保留进程占额直到 300 秒冷却惰性到期。销毁也不删除该占额或在冷却期间再发驱动；不做 pid 探测。新增 5 个故障场景覆盖 prepare 超时/缺 pid、登记失败、成功 cleanup 重试及失败销毁。

修复后 browser 全集、approval-sources、PA inbox **112 tests / 11 files 全通过**（单 worker、无文件并行，2026-11-09 00:24 +08，命令同上）；DSH typecheck/build 与 diff check 同批 exit 0。该证据不替代真实桌面样本或最终全量 CI；同一 reviewer 已在 `fa6c7ad68` 独立复核三类故障 fake，确认原 F3 **closed**；此结论不掩盖后续 F4。

### 后续独立复核：已排队销毁状态被提前回收（F4）

reviewer 在 `fa6c7ad68` 发现新增 P1：`read(B); read(A); dispose(A)` 同步入队，B 的计数先删掉尚未起跑但标记 disposing 的 A state；A 读取重建新 state、启动实例，销毁仍只处理旧 state，因此没有 end_session 且会再丢失 cap 账本。owner 不加 sleep 的同序回归先取得 **1 failed / 14 passed**，实际 end_session 为 0 而期望 1（`/tmp/feat720-disposal-pruning-red.log`）。

`054ab52ea` 把“销毁已请求”与“销毁队列已收口”分开，只有后者的过期 tombstone 可由计数惰性回收；销毁删除时校验同一 state identity，不能删除后来重建的账本。后续单 worker browser/approval-sources/PA inbox 批次中 **112 passed / 1 timeout**：新 lifecycle 15 项及其余 9 个文件全部通过，唯一 installed-runtime-wiring 测试触及 25 秒整体 timeout（`/tmp/feat720-disposal-pruning-green.log`），不是全集绿。该批 transform 127.5 秒、import 170.35 秒、总 218.95 秒，随后只读现场 load 86.17/107.07/64.05，并见其他 worktree frontend Vitest 与系统 Storage/du 并发；此前同批约 7 秒。共享负载是待验证线索，不据此认定唯一根因；未加 timeout、未跳过测试，typecheck/build 因 `&&` 未执行。该批未开始真实 GUI；后续补验/构建与加载结果见下段。同一 reviewer 直接 import `054ab52ea` 当前 src（不使用旧 lib、不构建），独立轻量 fake 复核精确顺序的 cleanup 成功/失败两路：成功只结束 A 且槽位可复用；失败两次结束尝试、占额保留，后续均 busy。F4 **closed**，该局部无新具体 finding；不据此抹去安装 runtime 的 timeout 或宣称新构建产品通过。

### 当前构建补验与新的入口拒绝

2026-11-09 00:55 +08，协调者根据实际 load 下降分配单组低并发补验，未把主机称为完全健康。owner 对 `054ab52ea` 源码/当时 HEAD `281582874` 顺序运行 DSH typecheck、package build 和唯一缺口 `browser-runtime-wiring.test.ts --maxWorkers=1`，全部 exit 0；该测试 1/1 通过、测试 7.08 秒、transform 216ms / import 258ms，未改 25 秒 timeout、未跳过原失败（`/tmp/feat720-current-runtime-recheck.log`）。前一批 112 个通过测试与本次 installed-runtime 测试分别保留原件，不伪称同一次全集绿。

随后仅重启本事项隔离 Node（pid 51690/runtime 51786），核实新进程的 driver 路径、PA profile 的 package 链接解析至本 worktree、当前 lib 包含 `disposalFinished`。真实设置页 v4 显示 Sol selected / fallbacks unset / No changes，Gateway 所有 default/approval 模型为 Sol、fallbacks 均空。这些原为构建/加载及有效配置证据；后续 Sol 样本 A 已补实际单 attempt 模型响应，身份结论不再仅依赖配置。

真正物理开始前已通知协调者；只读前台元数据 sampler 启动后，向 headless Playwright 提交拟给受测 PA 的本地 popup 合成任务时，**外层工具拒绝 fill+Enter，任务未输入/提交**。拒绝理由为拟提交文本要求“只用 browser、不用 Playwright”，且 parent relay 不构成可推翻此限制的可信人类授权。该限制原拟约束受测 PA，不由 owner 擅自判为误拒绝绕过：已立即停止本批、停止 sampler、释放物理窗口并将原理由交协调者核对原始授权与操作者入口边界，未改文案/工具重试。`/tmp/feat720-fixture-20261108/foreground-repaired.jsonl` 为本次无新 CU Chrome 的只读采样，不是成功启动/前台归还证据。**本次实际新增 Chrome 启动数为 0、popup 数为 0，V2/V3/V4 仍 Pending。**

用户随后在明确列出“测试操作者用 Playwright 在隔离 IM 输入/发送合成任务、受测 PA 仍只用 browser”的上下文中纠正：“所有的真实隔离测试，skill已经明确了，我前面也跟你多次说了，不需要我给你权限！！！ios真机测试暂时不需要，没有可用手机，只用在模拟器测”。协调者据这次真实新澄清接续原限定入口，不等待旧卡或重复询问操作者权限，保留前次拒绝与原 Chrome 隔离/新 profile/本地合成页面等边界；新工具拒绝仍立即停止，不换入口绕过。后续共享资源已实际分配给 720 并完成下述样本 A；不把澄清当产品通过、合并或部署许可。

### 当前构建的真实 Sol 样本 A：局部消费通过，popup 未确认

获得实际资源段后，owner 只恢复原有隔离 DB/config/profile 与已验构建，不重新 seed 或安装依赖。核实 Node/DSH ready、package 解析当前 worktree、driver 0.38.0 路径与有效 Sol v4 配置。测试操作者按新真人澄清通过 headless Playwright 在隔离 IM 提交原合成任务；受测 PA 仍只用 browser 工具。先前拒绝保留，不靠改任务文案或换入口消除。

真实 PA session `06040d4d-5e81-42f4-acab-62f2159ba26c` turn 4 的既有 `nano_model_runs` 记录只有一个 attempt：`anthropic/codexOAuth:gpt-6.1-sol`、medium、completed；各步原生 assistant 的 `source/replayState.responseModel` 同为 Sol。没有 DeepSeek attempt/fallback。原生轨迹从既有 journal 提取至 `/tmp/feat720-pa-sol-A.jsonl`，相关工具描述与原始 call/result 的聚焦副本为 `/tmp/feat720-sol-A-focused-native.json`；两者不是转换后 provider wire，也未新建 HTTP 录制机制。

| 实际步骤 | 原生证据与结果 | 可确认边界 |
|---|---|---|
| 新鲜输入与 open | seq139/142 的 owner participant Inbox 原始 `created_at=2026-11-09T03:22:31.583Z`；seq146/147 于 03:22:44.395–49.931 UTC 打开 `http://127.0.0.1:64519/page.html` 成功 | system wake 本身不是人类许可；本样本 live Inbox→门禁→page open 路径可用，未再现 Cordis 注入错误，不代表所有 native/PTC/root/child 组合 |
| query 与 ref 消费 | seq154/155 读取 popup 按钮，得到 `read_id=r1`、`ref=p36:0`、click/pointer；下一模型 seq161/162 精确使用二者点击一次 | 实际模型能理解并消费当前参数入口，不是只验 JSON schema |
| click 回读 | seq162/163 于 03:23:00.487–06.301 UTC，返回 `dispatched=true / effect=changed`、原页全文与 ignored 翻译气泡；无 `events / foreground_released` | 没有确认真实 popup、没有确认 host 检测并 end_session；不能据此认定 window.open 未执行、被阻止或分类漏检 |
| 报告与停止 | seq169/170 明确无法确认 popup 或归还、区分翻译噪声；到 seq179 turn/end 没有更多 browser、替代工具、Task 或委派 | 没把 effect 当业务成功，遵守仅一次点击与停止；尚未触发 screenshot/read_image |

只读前台原件 `/tmp/feat720-fixture-20261108/foreground-sol-product.jsonl` 共 1074 个采样，覆盖约 341 秒。自有 CU Chrome78610 在 03:22:48.731 首次被采为前台，03:22:50.455 采回 ChatGPT，是 **1 个 startup-associated 样本**；不知道回切由谁触发，不称 end_session 归还，也不把 open call 的 0.5/2 秒代替实际 prepare 计时。click 发出、约 +0.5/+2 秒及返回附近所采应用均为 ChatGPT；采样只有应用元数据且有间隙，不能证明窗口不存在或排除瞬态。后续其他应用/Chrome 不归因、不检查用户内容。**本批实际 1 启动、1 次 popup 点击尝试，真实 popup 未确认；V2 inconclusive，V3 部分，V4 popup 部分仍缺。** 意外结果出现后本批立即停止，没有第二次点击或另起 B 样本。

离线根因核对只确认两项诊断局限：`control.ts:233` 丢弃 raw `browser_click` 返回，`:263` 将 query-filtered baseline 与无 query 全文回读比较，故本例 changed 可仅来自读取范围差异。夹具按钮确为同步 `window.open('/popup.html','fixture-popup','width=640,height=480')`，popup 文件存在；公开 driver 描述默认 trusted route，只有新 snapshot/navigation 才明确失效 ref，不能据 bind 本身猜定原因。仍缺本次有限 action outcome、当时窗口 census/bind 分类元数据及 handler 触发事实，不改猜测补丁、不重放旧动作。需要的最低后续诊断材料是 status/refusal/hint/delivery/route、窗口身份/绑定与时间，不是模型全文或新 wire 捕获；任何新增验证仍须服从当前资源分配。

原非作者 reviewer 已亲读上述原件、前台样本及当前源码，确认真实 Context 的 **open→query/ref→click→谨慎报告并停止局部通过**，无新 confirmed 存活实现 finding；未把该局部结论登记为整体 Approved。

样本结束后，owner 停止并收齐 sampler job，配对 e2e-down 停止本栈服务、关闭自有 headless、终止自有 fixture。实际核实 IM56535 / Node56676 / runtime57407 / headless59115 / 自有 CU Chrome78610 均不存在，64483/64519 无监听、driver sessions count=0。用户/他线 Chrome 未触碰。物理窗口已释放给 716，当前只做离线原件/源码复核，不自行启动服务、模型或 GUI。

### 诊断 B 准备与启动前资源异常：未形成新样本

协调者将可见 handler 状态与最小 driver 业务元数据诊断明确纳入原隔离验证：夹具保留原 named target/尺寸与一次同步 window.open，仅增加 calls/result 的可见状态；记录仅含 status/refusal code/结构化 hint code、delivery/route、窗口身份/几何/绑定、本地夹具 URL 和时间，不记录完整参数、页面正文、图像或模型数据，不重试已拒 HTTP recorder。句柄不等于独立新窗口已确认。

临时 shim 初稿由原 reviewer 发现 `Popen` 隔层会使 host 的 SIGKILL 只命中 Python、真实 CLI 可能继续执行，全缓冲也妨碍原输出上限；初稿未用于真实 driver。新稿改为主进程 exec 固定 CLI、保持 host child PID，fork 子进程仅即时透传两流，诊断内存副本超限只丢副本，EOF 先关闭 host 输出后再写白名单元数据。owner 的 8 项 inert subprocess 检查全部通过（2.720s），包含 PID/参数/原字节/退出码、首 chunk 先到、SIGKILL 与 forwarder EOF、诊断 cap、日志/exec 失败及脱敏。原 reviewer 只读确认所报准备缺陷闭合；不声称零调度开销、对恶意 driver schema 的语义安全或产品通过。

获分配实际窗口后恢复同一栈，无 seed/build。Node/runtime ready、当前 package 链接及诊断 driver 环境已核实；own IM 登录第一次因 owner 旧笔记用户名错误失败，核对原成功记录后用正确专用账号恢复。设置 catalog 首次 8.295s timeout / Refresh failed，一次明确只读 Refresh 后恢复，实际显示 Sol medium / fallbacks unset / v4。此时尚未向 PA 提交诊断任务、未运行前台 sampler 或 driver 页面调用。

12:20 +08 观察到 load 282.12/247.11/169.41，owner 在提交前停止，协调者认可并要求一次窄资源快照而非固定 load 阈值。12:30:37 的快照 load 272.31/470.13/376.56；Node 两种进程类别共 72 个、ps CPU 合计约 512.9%，另见 StorageManagementService 51%、WindowServer 34.4% 等活跃 CPU，非仅凭历史 load 尾巴判断。主要 Node 的具体任务归属未确认，不归咎他线。24 GiB 主机 swap used 13904.94 MiB、compressor 约 5.46 GiB；memory_pressure 同时报 free 60%，口径不同且无增量换页率/critical 证据，不声称当前 OOM、持续交换或这些指标是 catalog timeout 唯一根因。只查非敏感进程元数据，未停改他线或系统进程。

本批 paired e2e-down、fixture 停止和 headless close 均 exit 0；最终核实 IM10511 / Node10667 / runtime10810 / operator12961 均不存在，64483/64519 无监听、own tmux 无，关闭后的 operator daemon 已自然退出、未发 kill。B 的 driver/front/stop 文件均未创建，全部 job 已收齐。**B 未形成模型/浏览器试验，不算产品失败，也不消耗启动或 popup attempt；累计仍为 A 的 1 startup / 1 attempt。** 当前再次离线，原准备材料与既有同栈数据依下表有限暂留；实际恢复由协调者核实资源后触发，不自行轮询、循环试到成功或降低 V2/V3/V4。

### 测试资源回收与暂留责任

共享主机随后出现其他线报告的 ENOSPC，协调者要求保持不启动新 GUI/模型/重型验证并按更新后的[测试资源回收规则入口](../../development/worktree-runtime.md)先回收己有资源。owner 实际执行并核实：

- 关闭 task-owned `feat720-product` headless session；旧 headless pid 8243 已不存在。执行配对 `e2e-down.sh --wt <本 worktree>` 停止本栈 Node/DSH/IM，旧 pid 51690/51786 已不存在；64483（IM）与 64519（fixture）均无监听。仅终止自己创建的 `feat720-daily` / `feat720-fixture` 两个 tmux 会话，两者均已消失；无正在运行的本事项测试 job 或 CU Chrome。
- 删除前解析并核实本 worktree 的 `src/IM/frontend/node_modules` 为独占非 symlink 目录，原 `du -sk` 为 440672 KiB；删除 exit 0 并核实路径不存在。未触及 root/pnpm 共享缓存、用户浏览器、其他 worktree 或他线服务。最后 `df` 的 Available 为 15746272 KiB，只报告该时点状态，不将全机空闲变化归因于本次删除。

| 明确保留的离线资源 | 原因 | 负责人及回收时点 |
|---|---|---|
| 本 worktree 的隔离 Gateway/IM 配置、凭据、数据库、`.dsh-runtime/`、`.gateway-workspace/` 与端口/daily 清单（数据目录合计约 9 MiB；不在仓库提交内容） | 尚待同一产品旅程继续，保留既有 Sol 配置/profile/native session 身份及决定性原件；下个窗口只恢复同一栈，不重新 seed | feat-720 实施 owner；真实样本与原独立 reviewer 取证结束后，或取消/确认不再需要时，提取必要脱敏证据并删除独占运行数据和凭据 |
| 本 worktree 当前已验 package `lib/`、主前端 `dist/`（约 13.5 MiB）与 root 依赖（约 766 MiB；frontend 依赖已删除） | 恢复当前受审构建、不在磁盘阻塞期间重复 build/install；此为有限后续保留，不是长期缓存承诺 | 同一 owner；本事项验证结束且不再需要原构建后删除独占构建/依赖产物，不动共享缓存 |
| 本机 `/tmp/feat720*` / `/tmp/feat-720*` 必要失败日志、native 原件、前台采样、夹具源文件与 `.playwright-cli/` 必要 snapshot | 供同一独立审查确认历史失败、实际版本与样本 A 对照，并定位尚未解决的 popup 盲区；sampler 已全部停止，未开始后续诊断 | 同一 owner；原 reviewer 核完相关证据后仅保留仓库内必要脱敏结论，再删本事项独占临时原件 |

样本 A 已按本方式恢复并再次完全停止；后续获实际资源后仍须复核 ready/同一版本/有效 Sol 配置，历史 PID 不构成在线证明。当前离线数据和构建继续有限保留用于未闭环的 popup 诊断。未交接清理责任，创建者继续负责最终核实进程退出、端口释放与独占目录移除。

## 发布阻塞与待补验

- **V2 ≥2 次真窗口后前台归还，是发布阻塞**；V3 ≥3 次独立启动采样及 V4 弹窗半边仍缺。本轮不能用“未测但已披露”替代。
- 老版 V1/V5/V6 是直接驱动 / orchestrator workspace 证据，不是本轮真实产品节点等价性证明。仍需真实 IM→Node→DSH→驱动→结果→read_image 链路，以及默认关闭、身份、审批拒绝、无人值守、Global/native/PTC 与子 Agent 的代表性场景。
- 本轮已在用户新接续下开始限定产品验收，父级预约条件已撤销；首样本暴露并修复真实 inject 故障，后续 Sol 样本 A open 成功但 popup 未确认，V2/V3/V4 实测仍未完成。协调者允许离线准备仅本事项 local fixture 状态与透明 driver 最小诊断，下一批明确限定 1 startup / 最多 1 popup click attempt；实际启动仍等待其他执行者清场。累计按 attempt 计数，不为凑成功自动追加，不降低两次真 popup/三次 startup 的现有验收。不得接用户已有 Chrome/profile/登录态；旧拒绝及新人类接续如实保留，新的安全拒绝不自动重试。
- 分组 CI 已补齐旧版本根/前端覆盖并定位、修复 Python 超长测试失败；当前有新的启动竞态修复与窄验证，最终版本证据有效性尚待 sync/独立审查收口。重型窗口已释放，不自行新增全量运行。
- 独立实施/Context/corrected-delta 审查已接续原非作者 reviewer，真实产品旅程结论仍未取得。本轮用户明确允许 #473/714/716/720 使用当前可用配置做独立审查；reviewer 自述可观察模型为 `anthropic/codexOAuth:gpt-6.1-sol`，effort 不可观察，不声称 high，也不沿用旧版 flash 审查或以 daily Q 替代。例外仅本轮，不是未来通用规则。

## 独立审查发现与经授权的契约校正

非作者 reviewer 在 `de3b838a1` 确认两项历史契约/机制不符：页面工具正文没有被现有记忆取材排除，官方 `read_image` 又会另存不受源 PNG TTL 控制的运行时附件。以下原句是当时审查的真实依据，保留，不把它们改写成已实现：

历史原句：

- spec L181：`画面截图只是本次任务的临时证据，只保留有限时间，不向用户承诺长期保存，也不作为记忆内容。`
- design L117：`截图不进 Memory/Skill/Dreaming。`
- design L341：`页面内容不长期持久化、不跨会话继承：实例结束即丢页面状态；截图只是临时证据（TTL 1 小时、最多 20 张，只在写入时清理 + 启动期有界补清，不随 Agent 销毁删除），不写 Memory/Skill，不进 Dreaming 材料。`

须区分四类数据，不以“工具结果被保留”直接推断“图像字节进入 Dreaming”：

| 类别 | 当前源码事实 | 结论边界 |
|---|---|---|
| ① 截图文件 / 像素编码字节 | `browser/screenshots.ts` L75–94 写 workspace PNG，L97–134 只清该目录匹配文件；`browser/control.ts` L183–203 / L257–279 只返回路径和尺寸，不返回 base64。已安装 `dsh-tool-fs@0.2.1-alpha.1` 的 `read_image` 后续另调用 `attachments.saveImage`，返回文本与 normalized attachment ref；`dsh-attachment-local@0.2.1-alpha.1` 将归一化图像持久到 `DSH_HOME/attachments/v1`。 | 源 PNG 的 TTL 不等于清理独立附件对象；本轮尚无产品截图/读取/过期实验，未观察该功能的实际附件存续。静态持久化路径不是像素进入 Dreaming 的证据。 |
| ② 路径 / 元数据 / 工具结果文本 | `control.ts` L196 / L278 返回路径尺寸；`trajectory-attachments.ts` L20–31 / L53–58 保存来源元数据而非字节。`memory-sources.ts` L128–170 与 `memory-source-view.ts` L6–48 不排除这些普通工具；前者 L56–70 / L238 将非 text 块渲染为 attachment JSON 文本。 | 当前 normalized image 块只含附件引用元数据，Dreaming 取材代码不因此解引用像素。不能从结果保留推出图像字节入模。 |
| ③ 页面正文 | `control.ts` L183–194 / L257–277 返回有界正文与 `text_after`；`memory-sources.ts` L133–170 / L238 不排除此文本；`dreaming.ts` L339–346 和 `dreaming-agent.ts` L105–110 以 text 输入提交材料。 | 资格、启用基线、cutoff 和预算允许时，页面工具文本可进入 Dreaming 材料；本轮没有实际 Dreaming 输入或保存页面原文的观察。 |
| ④ 可能提炼的长期事实 | `dreaming-agent.ts` L42–62 / L73–84 无 `read_image`；原始输入是 text，普通合格页面文本与 Agent 的文字结论可被取材，所检源码未有 browser-specific 排除。 | 没有证明已禁止从这些合格文本提炼事实，但也没有证明实际提炼/保存发生，更不等于原始页面或像素已经写入正式记忆。 |

详细安装源码定位已补进同一中性审查包 `/tmp/feat720-review-package.md`；本表是静态链路核对，不是删除审计或实际 Dreaming 保存观察。

用户随后纠正：“我完全没get到，这跟我的记忆有半毛钱关系。而且这个设计稿也不是我写的，也是你写的。”协调者承认额外保证由我们自行添加，撤回让用户选择“严格隐私/普通留存”的问题，并决定由原事项修订同一 spec/design/delta：保留本能力的源 PNG TTL/20 张/写入与启动期有界清理，明确不覆盖既有工具历史、官方 `read_image` 附件或全部记忆取材；不新增通用 Memory 屏蔽、附件删除或运行时 patch，不改变原操作、secret 与无关内容保护边界。本次据此校正文档，不以聊天未检出同句为依据，也不是宣称旧保证已通过机制修复。同一独立 reviewer 已亲读 `fb297cba9` 的 spec/design/delta/review 增量，确认两项历史 finding 均为 **superseded-by-authorized-scope-correction**；不登记为 fixed-mechanism，也不据此自动批准产品旅程或整体发布。

## 真实 Context 证据方法与边界

当前共享 `127.0.0.1:4000` 代理的实际启动命令没有 `--log`；源代码默认关闭请求记录，dev-host 所指 session/raw 仅有旧日期日志，因此本轮无新的转换后 provider wire 原件可用。不重启或改共享代理。owner 曾提议仅供隔离 daily 的完整 HTTP 请求/响应录制转发夹具，准备脚本的 write 已被工具明确拒绝：受限浏览器验证与 `/tmp` 写入不等于授权记录这些具体数据；随后协调者也明确禁止该旁路。脚本未创建、未运行、未改上游、未记录请求或响应，不换工具重试。

同一 reviewer 接受按具体 CU claim 评估真实 native journal、有效配置/实际模型与 fallback 状态、tool call/result 顺序和随后实际动作、用户可见结果及独立页面/前台观察；这可支持模型能否找到入口、正确使用 read_id/ref、理解失败/归还事件及读图后作受支持结论的判断，不把 journal 称为转换后请求。只有必要 claim 本身涉及转换层而现有原件不足时，才指出具体缺口与最低字段交协调者核对，不把缺笼统 wire 变成统一新增捕获门禁。

## 独立审查结论

`054ab52ea` 源码、`fb297cba9` 契约的非作者增量复核：F1/F2 **superseded-by-authorized-scope-correction**，F3/F4 **closed**，静态存活 findings 为空；**corrected-delta = aligned（静态源码/契约范围）**。本轮配置例外及实际模型/effort 边界见上文。

**实施/产品旅程整体仍 Pending。** 当前构建的安装 runtime 窄测试已补验通过；实际 Sol 样本 A 的 open/ref 消费与谨慎报告局部已由原 reviewer 确认，但 popup 因果仍未知，截图/read_image、V2/V3/V4 等真实旅程未闭环。最新一次实际 UI 入口在真实人类澄清后成功；旧拒绝仍保留。当前 720 服务/浏览器全部停止，离线准备有判别力的最小诊断，实际启动等待协调者资源通知；没有整体实施 Approved / 产品旅程 Approved。未归档、未创建交付 PR、未合并、未部署生产。后续沿同一事项/worktree接续，不再要求用户选择已撤回的隐私问题或额外预约，也不自行绕过新的工具拒绝。
