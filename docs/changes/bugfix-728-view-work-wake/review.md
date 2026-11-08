# bugfix-728: 验证与审查

## 状态

Active。用户已亲自试用首版并明确否定：点A展开但B被截去。修订保留完整Work列表，消息锚点仅控制展开/滚动；非作者独立审查已APPROVED，原生视图往返finding已修复并closed。尚待用户重新确认及最终CI，不得把作者自测或待审PR当作用户验收/完整归档。审查使用用户明确批准的当前可用配置，不冒称指定了未公开的model/effort。

## 版本与范围

- 执行者：#473 主实施者（独立工作区，非用户验收者）。
- executed_base: `eeaea47921806936da20e78c9ed96167716f5037`。
- 本轮 validated_at / effective_through：`adaac2666bbbb87abe51c798aad9f4f971b94370`；`87be58c187ae3071561edfb32ec4941e8d631228`冻结完整列表修正并取得真实浏览器证据，最终提交仅修复独立审查发现的内部视图往返恢复并补窄回归。预览已重建最终源码；列表/样式未再改变，既有真实图像证据保留。后续记录提交不改变实现。
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
- 原完整Web两轮各1083通过/1失败及根因未明的限制不变；用户确认、最终CI和canonical归并/归档仍须后续据实完成。

## 人类试用与恢复入口

须在运行节点同机浏览器打开（loopback不是远程可访问链接）：
1. 打开 `http://127.0.0.1:58054/chat/c_iy796v97`，隔离测试账号 `nano / nano1234`。
2. 找到 P 的“定位验收 A…”和“定位验收 B…”两条回复，分别点击 View Work。
3. 点A时A展开，较新B仍是同一完整列表的另一行且可手动展开；点B时B展开，A仍保留在下方。浏览器返回聊天再点较早A并刷新，不能丢失任一记录；未命中的行无需自动展开。

作者自建的 `fix473` 浏览器已关闭，预览服务按待试用要求保留于 tmux `fix473-preview`，运行数据仅在本worktree。停止：`./scripts/e2e-down.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/fix-473-view-work`。不要重新执行up而清空供用户试用的两条记录。PR未合入及用户待试用，开发worktree保留。

## 未完成收口

独立代码审查及finding closure已完成。用户实际重新确认、最终CI结果、canonical delta归并和归档仍须据真实事实继续。无合并/生产部署授权。
