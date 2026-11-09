# bugfix-728: 验证与审查

## 状态

Completed / archived。首版被用户真实试用否定后，修订保留完整Work列表、消息锚点仅控制展开/滚动；用户对同一A/B入口完成连续复验并明确确认“Good job，我觉得我的真实测试没问题了”。非作者独立审查APPROVED，原生视图往返finding已修复并closed，新版远端CI实际success；canonical已按审过delta归并。归档不代表PR已合并或生产部署。审查使用用户明确批准的当前可用配置，不冒称指定了未公开的model/effort。

## 版本与范围

- 执行者：#473 主实施者（独立工作区，非用户验收者）。
- executed_base: `eeaea47921806936da20e78c9ed96167716f5037`。
- 本轮源码validated_at：`adaac2666bbbb87abe51c798aad9f4f971b94370`；`87be58c187ae3071561edfb32ec4941e8d631228`冻结完整列表修正并取得真实浏览器证据，最终代码提交仅修复独立审查发现的内部视图往返恢复并补窄回归。预览已重建最终源码；列表/样式未再改变，既有真实图像证据保留。报告9db9a5bed不改源码。
- 归档前effective_base：`00972141a836c24bc574a7cef90b1c6efd8c8832`；sync commit `0a80622a70710186b0a31f5a060a51ce246941d6`。相对已验证9db9a5bed仅新增bugfix-729/731的3份独立unit文档，没有源码/配置/测试/current spec变化；本次代码审查、测试和用户路径证据retained。最终归档提交再只改验收记录、按原文归并已审delta和路径/索引，不改变产品行为；effective_through由PR实际head标识，不倒写为曾执行全量测试的版本。
- 首版历史验证版本：`606ad3da50b508f7c6fabb97091f61ccb298ad0c`（报告补充至`739378ee3`）；其“仅目标展开”的自测不构成完整旅程通过，已被用户真实反例否定。
- 本任务 dirty 范围：Work API/records/types；Web message-pane 链接与测试、Work panel/API/测试、双语提示；本 unit 文档与 backend focus 回归。主 checkout 的用户修改未操作。

## 首版自动化与静态检查（历史，非修订版本结论）

- 最窄 backend 真实进程/socket：`pnpm exec vitest run apps/im-server/tests/e2e/work-message-focus.test.ts` 通过1项，覆盖同Agent25轮、最新页之外的早期回复、两条不同回复/重复早期定位、续页、过程读取、缺失锚点及认证。
- 最终完整 IM 回归低并发通过：65文件 / 405项，`pnpm exec vitest run apps/im-server/tests --maxWorkers=1`，本地原始输出 `output/im-tests.log`。
- 最终完整 Web suite 低并发通过：113文件 / 1082项（含 message-pane102项、Work panel28项；后者覆盖延迟body后滚动/刷新不抢阅读），本地原始输出 `output/frontend-tests.log`。
- `pnpm build`、`pnpm typecheck` 通过；冻结实现后再次前端 `tsc -b && vite build` 通过（已有大chunk提示，不影响构建成功）。
- helper/contract pytest：135 passed / 28 deselected（`python -m pytest -m 'not e2e' -q`）；`ruff check .`、`scripts/docs-check`（279 maintained sources / 69 routes）、`git diff --check` 通过。
- 完整 pnpm test 曾在共享机器 load≈34 时出现无关 DSH 集成超时，已取消该全并发运行，不能声称完整 runtime suite 通过；本地原始输出 `output/backend-tests.log`。以上低并发 IM 回归是实际通过的范围，不替代全 runtime suite。

## 首版真实用户路径：作者自测（完整性结论已失效）

环境：隔离 daily 模板，UI/IM `http://127.0.0.1:58054`；node `wt-fix-473-view-work-95711`，开发分支源码；测试用户 nano。没有生产数据或公网隧道。

使用真实模型 P（daily-product、codexOAuth:gpt-6.1-sol/high）在“研发日常”生成两次独立 Inbox wake-up；两次分别读取输入、执行只读 bash，再实际 send_message。

| 回复 | 消息ID | 实际执行/轮次 | 真实路径观察 |
|---|---|---|---|
| 定位验收 A：已核查当前目录。 | `d7ea73916e094eaca9e3cf72755813dc` | `6b96f92c-1617-4710-aebc-5e325f202390` / `1` | 气泡链接点击进入同Agent Work，自动展开，8工具可见；bash展开核实 `$ pwd` |
| 定位验收 B：已核查日期。 | `01587998798544179009e8fc4329028f` | 同一执行 / `2` | 点击B进入轮次2，4工具可见，未误定位A；返回后再次点击A仍正确 |

最终滚动方案实测：A/B目标行均位于 viewport top≈47.8px（固定主栏下方），open=true，直接看到工具，而非仅验证URL。首次空摘要阶段滚动过早的自检发现已修正为首批过程就绪后滚动一次。

本地原始产物（不提交）：
- `output/playwright/reply-a-work-final.png`、`reply-b-work.png`：1200×732实际画面；冻结实现production build重新加载后 `reply-a-frozen-build.png` 仍准确展开A及实际bash输出。
- `.playwright-cli/page-2026-11-07T17-51-33-103Z.yml`：重复点击A的真实快照。
- `.playwright-cli/page-2026-11-07T17-52-21-258Z.yml`：A的实际bash内容。
- `output/playwright/delivery-provenance.json`：测试DB中两条真实投递事实，无凭据。

这些为作者自测，不是独立产品验收或用户确认；真实浏览器仅有两轮，默认20轮外历史另由25轮真实socket回归覆盖，不冒称真实模型生成25轮。

## 用户否定后的完整列表修订

### 反例与根因

用户原话：“打开Work的页面，看到的永远是全量的呀。只是说你展开哪一个的问题。”首版真实A返回列表只有轮次1（DOM只有一个 `.im-work-turn`），轮次2/B不存在。`WorkRecords.turns`将目标当作inclusive上界，查询`seq <= target`，所以准确展开与截去其他轮次同时发生；仅核目标展开的旧自测遗漏了不变量。

补充红测先在首版运行：backend期望最新`[25,24]`却收到`[1]`；Web正常最新页未自动加载至历史目标，找不到目标正文。修订撤销目标上界及主执行列表替换：后端只提供focus元数据，客户端在原有连续摘要列表补载到目标；历史主执行通过关联面板定位，当前主列表不丢弃。滚动保留72px上方余量，不把紧邻折叠轮次推到固定栏之外。

### 修订自动化与静态检查

- 真实进程/socket回归通过：同Agent25轮，分别锚定1/24/1，首屏始终保留25/24；全部续页精确覆盖25→1，无重复/遗漏，且仍核验实际发信items、当前状态及权限。
- 完整IM回归：65文件 / 405项通过，`output/im-list-correction-tests.log`。
- 完整Web两轮均112文件通过 / 1文件失败、1083项通过 / 1项失败；本次Work30项与message-pane102项两轮均通过。初轮为未改动的Task根概览`View Video product`等待超时，单独Task文件18项全部通过（该用例499ms）。串行复验为另一个未改动的ChatWorkspace interactive draft用例等待`Reply draft`输入框10秒超时；其首轮9362ms通过，窄复测同一c1用例仍超时、c2通过。未查明深层原因，不武断归因为本次改动或机器负载，也不把完整Web套件报为通过；不扩展修改无关功能。原始输出为`output/frontend-list-correction-tests.log`、`output/frontend-list-correction-serial-tests.log`。
- `pnpm typecheck`、`pnpm build`、前端production build通过；helper/contract pytest135通过/28 deselected；`scripts/docs-check`（283 maintained sources / 69 routes）、`git diff --check`通过。

### 修订真实路径（作者自检，不代替用户重新确认）

复用原有真实A/B消息与同一daily数据库，未制造替代记录。只刷新自建隔离IM进程以载入新二进制，保留原端口、JWT、账号、node与数据；前后均核实原执行的轮次1/2仍在，未重跑e2e-up或清库。

1. 从原聊天点击A：列表按2→1保留，B为折叠行，A展开且8工具可见。B行top≈70.8px，A行top≈119.8px，两条均在同一画面；`output/playwright/reply-a-complete-list.png`。
2. 仍在A锚点页直接展开B：能读到B实际4工具、日期核查与实际投递，A未丢弃；`output/playwright/reply-a-open-neighbor-b.png`。
3. 浏览器返回原聊天，再点击B：列表仍为2→1；B展开，A仍存在（本地先前已展开，保留既有展开状态）。DOM：B top≈119.8px，A top≈592.8px；没有把A从列表去掉。
4. 取得物理桌面释放后补齐连续路径：保存B最终画面`output/playwright/reply-b-complete-list.png`，浏览器返回原聊天重新点A，再刷新。列表始终2→1，A展开且top≈119.8px，B仍为保留在上方的完整记录；`output/playwright/reply-a-repeat-refreshed-complete-list.png`。此前已手动打开B，重复A/刷新保留其展开状态，不将屏外B误报为列表缺失。完成后已关闭作者自建的headed/headless浏览器并释放桌面。

原两条真实模型记录只覆盖两轮；25轮默认页之外的完整性由真实socket回归与Web多页回归核验，不冒充真实模型生成25轮。

## 独立审查能力差异

native subagent工具不能指定model/reasoning_effort；原固定审查配置为gpt-6.1-sol/high，首版因此保留能力差异。用户本轮现已明确批准：“当前派工工具不能指定流程原定的模型和推理档位。是否允许本轮 #473、714、716、720 用当前可用配置做独立审查。允许”。本轮实际采用平台当前默认/继承配置，具体model/effort标识未公开；不声称已显式指定原配置，未降低审查内容或由作者自审替代。

### R1：非作者完整审查

- 独立reviewer：`a6792933-c9a4-4996-9eeb-985c129c1283`。
- base：`eeaea47921806936da20e78c9ed96167716f5037`；head：`87be58c187ae3071561edfb32ec4941e8d631228`；覆盖完整base..head和4份修订unit文档，而非只审列表补丁。
- 能力：change-code-review + frontend-experience-review（仅完整列表与展开定位）。只读核查源码/current spec/测试/日志/实际图像，没有操作浏览器、服务或数据库，没有重跑全量。
- 结论：Request Changes，1项CONFIRMED P2。精确发信关联及权限、正常完整分页、历史main保持当前列表、缺失/迟到关联均有实现与测试；A/B完整列表实际图像PASS，修订delta文本aligned。整体因下面的原生往返恢复回归为implementation-mismatch；当时尚未补齐的重复A/刷新证据列为inconclusive，不把待人类确认另造为缺陷。

| ID | file/line（R1） | finding / failure_scenario | severity/status |
|---|---|---|---|
| F1 | `agent-work-panel.tsx:154-161`，关联renderTurn/Turn focus effect与showNative/showRecords | 带message_id首次定位后手动折叠目标，切原生轨迹再回工作记录；内部replace产生新location.key，被误认为新回复入口，重开目标并再次scrollIntoView，覆盖阅读恢复。独立全内存真实组件/Router/Query复现滚动1→2、targetOpen=true。 | P2 / CONFIRMED |

### 作者修复与R2 delta closure

F1已判真并修复；新增同路径组件红测在87be58c上复现目标被重开（30通过/1失败，`output/native-anchor-red.log`）。最终冻结于`adaac2666bbbb87abe51c798aad9f4f971b94370`，使用仅随Agent/消息锚点或重新进入而更新的回复入口token，内部record/trajectory URL变化不重置token；补折叠后native往返保留320px阅读位置/不追加定位滚动的回归。Work31 + message-pane102共133项通过（`output/native-anchor-green.log`），最终前端`tsc -b && vite build`通过（`output/frontend-native-closure-build.log`）；不以窄回归替代完整Web全绿。

原reviewer对87be58c..adaac2666的实现/测试2文件（30增/5删）、4份dirty unit文档及追加真实截图完成closure，保留R1未变范围结论：**APPROVED；F1 CLOSED；存活findings=[]；corrected-delta ALIGNED**。不是另一次全产品设计或未声明的完整重审。

- 独立全内存运行真实AgentWorkPanel与React Router/Query（网络及展示子组件stub），验证首次定位→折叠→320px→native→records仍折叠/320px/scroll仅1；真实A→B→A导航计数1→2→3；同一A从聊天重新挂载仍定位，计数4；missing关联迟到后定位，计数5。没有改文件、启服务、操作浏览器或数据库；不将jsdom当真实像素证据。
- 独立核看`reply-a-repeat-refreshed-complete-list.png`，并结合已核看的A/B完整列表及邻近B展开截图，完整列表、分别点击A/B、重复A/刷新为PASS。图像在87be58c产生；closure仅改入口token，不改列表、样式或首次呈现，证据retained；R1重复/刷新inconclusive已由追加证据补齐。native返回仅有代码/组件核验，未另称真实浏览器native画面已实测。
- 原完整Web两轮各1083通过/1失败及根因未明的历史限制不变；R2时用户确认、CI和canonical收口尚未发生，随后取得的实际结果见下文，不倒写为R2已经验证。

## 人类实际验收与保留预览

用户对原有A/B消息入口亲自走完“点A保留B→返回聊天点B保留A→再点A并刷新”后反馈：“这个流程做了一遍。我看到应该没问题。”随后询问并确认现有展开/折叠记忆范围（事实查询，不是新需求），最后明确：“Good job，我觉得我的真实测试没问题了”。此为本事项修订路径的人类验收通过，不涵盖其他并行事项、不授权merge/deploy，不再要求重复试用。

当前记忆事实由源码轻量核查：同一origin/tab的sessionStorage按Agent保存各轮展开/折叠；A已展开时点B只将B设为展开，不收起A；A手动折叠后点B保留A折叠。本次新回复入口会强制展开其目标，native内部往返及后台数据刷新不重新强制。没有代码级TTL或跨设备同步承诺；关tab/浏览器后的恢复由浏览器会话机制决定，不承诺永久保存。未新增GUI、模型调用或功能变更。

预览继续按原要求保留；须在运行节点同机浏览器打开（loopback不是远程可访问链接）：
1. 打开 `http://127.0.0.1:58054/chat/c_iy796v97`，隔离测试账号 `nano / nano1234`。
2. 找到 P 的“定位验收 A…”和“定位验收 B…”两条回复，分别点击 View Work。
3. 点A时A展开，较新B仍是同一完整列表的另一行且可手动展开；点B时B展开，A仍保留在下方。浏览器返回聊天再点较早A并刷新，不能丢失任一记录；未命中的行无需自动展开。

作者自建的 `fix473` 浏览器已关闭，预览服务按原要求保留于 tmux `fix473-preview`，运行数据仅在本worktree。停止：`./scripts/e2e-down.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/fix-473-view-work`。不要重新执行up而清空用户已经验收的两条记录。PR未合入，开发worktree保留；合入后按工作流核对预览保留要求再清理。

## CI与快修收口

- 新版CI [run42498850342](https://github.com/Mrchen116/nano-multiagent/actions/runs/42498850342) 在`9db9a5bed9a920cbe6bed22bd5e6e9aee3409a0c`实际completed/success；TypeScript backend/tooling、Frontend checks、iOS检测success，iOS构建因未变iOS路径skipped。Frontend的完整vitest步骤success；后端native runtime/IM及helper/architecture、build/typecheck、ruff、docs步骤均success。不拿首版旧绿CI代替，不覆盖本地两次完整Web失败及根因未明的历史事实。
- 本地受影响窄回归、IM完整回归、typecheck/build、helper/contract、文档与diff检查已通过；完整Web在该远端干净CI通过提供补充的完整套件证据，不能称本机失败已被诊断或修复。没有修改无关Task/ChatWorkspace。
- 已审corrected delta按原文归并至canonical Agent Work，IM入口计数14→15，完整unit整体归档；验收及路径/索引更新不改变实现，不机械新增审查round或重跑人类旅程。归档后已通过文档完整性（281 maintained sources / 69 routes）、逐字delta归并及15条requirement计数断言、whitespace检查；最终PR head的远端CI结果以实际run回执交付。
- 首次交付时独立代码审查、finding closure及本事项人类验收均已完成，尚无合并/部署授权；后续用户明确授权解冲突后合并的接续记录如下，仍不授权部署。

## Post-PR integration closure

用户后续原话：“https://github.com/Mrchen116/nano-multiagent/pull/480 有个冲突，解了之后可以merge了”。本轮只接续#473，解决集成冲突、验证后合并并回收所属worktree/临时资源，不部署、不改其他PR。原A/B/A人类验收不重做；用户原先保留的58054预览现随本次收尾回收，保留必要非敏感证据，精确清理结果以PR实际回执归集。

### 范围与静态复核

- pre_sync_head：`e1274c94b32899ac7a3adc4be4101c2ea4358530`；本轮executed/effective_base：`3b8fecea69a147f75fe80ddee0ccc08196a0c2da`；受审/窄测试validated_at：`970e809e57c60c3419b86a465807d84f4254c5f9`。后续只补本段事实，不改变实现；最终effective_through与CI以PR实际head标识。
- 唯一冲突为`docs/specs/im/spec.md`顶部对齐标记728/731；采用target较新731，完整保留本PRAgent Work15条和上游WebChatUX33条。无产品代码冲突，中英文自动合并未删除Work提示、上游toast keys或新版fallback。canonical的已审delta仍逐字一致。
- 原独立reviewer `a6792933-c9a4-4996-9eeb-985c129c1283`只读检查完整target..head、本次merge两亲及双方索引/双语/相邻调用链，integration closure **APPROVED；findings=[]；F1仍CLOSED；corrected-delta ALIGNED**。本轮仅静态git/read/grep，不冒称动态重验；配置例外同R1/R2，未虚构显式model/effort。
- Work panel/API/CSS/测试、message-pane/测试、backend Work/types/routes/socket、鉴权及WorkThreadLink/user-stream相对已接受版本未变。上游App仅toast入参、chat会话缓存不覆盖agent-work缓存/路由token；interactive-only发送仍从真实call/turn追加同一message_sent身份，View Work不依赖正文非空；CSS不影响Work行。原完整列表/正常分页/邻居展开与折叠/native往返及权限结论、已接受真实旅程retained，无证据要求新增模型/浏览器或重复人类验收。

### 本轮实际测试与限制

- 在父级协调的串行1worker窗口中，真实socket1项PASS（25轮、1/24/1锚点与完整分页/权限），Work31项PASS，message-pane90项PASS/12项FAIL；合计Web121通过/12失败。#473链接用例通过。11项5秒timeout、1项missing dialog，分布在未改composer/menu，日志`post-conflict-socket.log`、`post-conflict-web.log`原样保存，不报133全绿。
- reviewer逐一核失败用例：直接render MessagePane，不挂App/toast、不传globalAgentIds、不含interactive payload，onSend/onFork为mock；涉及实现/测试及依赖版本未变。静态未发现与本次merge或#473的实质执行链关联，但根因仍UNKNOWN；测试后观察到高load及共享主机磁盘事件不等于已证明原因，不将红测改写为环境已确认。
- 一次区分实验拟筛原失败force-scroll case；npm脚本shell包装拆散多词regex，实际匹配17项，原case在636ms输出PASS，17项输出PASS/85项skip。随后文件报告后超过7分钟未给总汇或退出，已SIGTERM取消并收回job；该命令不是PASS，不提高timeout、不重复跑整个102项或扩修无关功能。部分输出`post-conflict-isolated-case.log`保留。
- 本轮合并实现未改，文档完整性282 maintained sources/69 routes与diff检查通过。最终完整CI须取当前PR head的实际结果，不使用旧绿或用户验收覆盖此轮技术红测；若当前CI仍红，继续最窄定位/target对照，不强行merge。
