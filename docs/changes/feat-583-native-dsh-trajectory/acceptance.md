# feat-583 — 独立产品验收

> 对齐：`spec.md` 全部 Scenario、`design.md` D2.1 与原型对齐契约。
>
> Review mode: full；日期：2026-10-12。Executed base: `1128a2b6e30911e4658ed0d935dfff6b1424c740`。首轮验收其上的 feat-583 working tree；针对修复的复验内容已冻结为 `7e22a91d28fff92d07980845cfbabb9821cd1316`（本 reviewer 已用 `git rev-parse HEAD` 核对）。首次发现与修复后结果分开保留，不将首轮失败改写成一次通过。

## Verdict

**fail（存在必验交互的 inconclusive；不等于已证实该交互有实现缺陷）**。

大部分真实用户旅程已通过。两项实测缺陷已修复并复验关闭：空 Agent 显示空白已连接轨迹；两种查看方式往返丢失选中工具的检查器。Round 3 已补充并独立核对区间聚焦与 Escape 复位的实际截图；尚缺时间线缩放的有效交互结果。IAB 拖拽输入受限，滚轮尝试只移动了外层页面，不能把聚焦成功或控件存在替代缩放成功。

## 环境与证据边界

- Checkout：`/Users/czj/.codex/worktrees/native-dsh-trajectory/nano-multiagent`，branch `codex/feat-583-native-dsh-trajectory`。
- 真实产品：`http://127.0.0.1:51650/settings/agents/trajectory?view=work&work_view=trajectory`。本 reviewer 使用独立 IAB 标签页，不操作用户／root 标签页；所有业务数据为隔离环境。
- Runtime：`.dsh-runtime/feat-583-review`；已独立检查 `/health` 返回 `{"status":"ok"}`，Node PID 43553 的 cwd 为上述 checkout（后续 root 依约停止／恢复过同一隔离 Node）。IM 未被 reviewer 停止。
- 前端 `src/IM/frontend/dist/index.html` mtime 为 `2026-10-12T13:35:24`；对这次重新构建页面执行 reload 后复验两项修复。产物与提交的内容归属由 caller 的冻结交接支持；未把 Git HEAD 当作进程版本证明。
- 身份：`nano` owner；`reviewer` active 非 owner。reviewer 被 caller 通过公司成员 API 停用后，已打开页面自动回登录；最终浏览器恢复为 nano。reviewer 保持 suspended，未擅自修改其状态。
- 主执行 `54b2dd44-fa32-4863-8b24-8c23a5d5bbff`；真实普通 subagent `9a6de34e-5e7a-4334-92d0-89f6d35aec86`，名称 `Verify addition in doc`；测试聊天 `c_1xc3gqlb`。
- 使用真实 IM → Node → DSH 日志及 LLM 执行；未读实现定位根因，未修改源码、测试、配置、设计。未用单测或 API 200 替代界面结果。
- 本机截图目录：`output/feat-583-acceptance/`，不提交截图。下文截图名均相对此目录。完整原始观察记录保留在本轮浏览器工具输出。

## Round 1：实际发现

| ID | Severity / relation | 期望与实际 | 处置与理由 |
|---|---|---|---|
| A1 | major / direct | R1.2：尚无执行应显示明确空态。`empty-trajectory` 未收到任何任务，进入原生却显示“已连接 · 实时更新 · 只读”、空表、“无计时数据”。`empty-desktop.jpg`。 | fix-implementation。用户不能分辨尚无执行与成功读取的空记录。 |
| A2 | major / direct | R2.2：子执行选择 read 的“结果”，切工作记录再切原生，子执行 ID 保留但检查器消失，`事件详情` 数量从 1 变成 0。reload 后仍复现。 | fix-implementation。检查位置丢失，违背两种查看方式往返保持位置。 |
| A3 | evidence gap | R3.4：时长、轮次、调用、搜索、时间条选择均有实际结果；区间拖拽被 IAB 工具拒绝。 | 补真实拖拽／缩放交互证据；不要据工具失败断言产品失败，也不要降级为 pass。 |

## Round 2：修复后复验及全场景矩阵

### Requirement R1：在 Work 内切换查看方式 — pass

| Scenario | 期望来源 | 实际旅程与结果 | 证据 | 结果 |
|---|---|---|---|---|
| R1.1 从工作记录进入原生轨迹 | spec R1.1；prototype 宿主切换；design D1 | 同一 Agent Work 内切换，看到主执行／明确只读与连接状态及真实原生记录；返回工作记录看到保存轮次及原工具数。桌面和手机均操作。 | `desktop-system.jpg`、`mobile-result.jpg`；离线保存记录中两轮分别 6/33 工具，随后增加至 7 轮 | pass |
| R1.2 尚无执行 | spec R1.2；prototype empty | 修复版 reload 后 empty-trajectory 显示“暂无可查看的执行”和“返回工作记录”，不再加载空原生表。390×844 同样可见。A1 关闭。 | `empty-fixed.jpg`、`mobile-empty.jpg` | pass |

### Requirement R2：主执行和关联执行定位准确 — pass

| Scenario | 期望来源 | 实际旅程与结果 | 证据 | 结果 |
|---|---|---|---|---|
| R2.1 查看已选关联执行 | spec R2.1；design D1；prototype 执行选择 | 主执行包含 inbox、read、subagent、send_message；切子执行只见其 read 与加法结论（12+30=42），归属在同一主 Agent 页面。切回主执行恢复主记录，没有子执行结果混入主记录。桌面与手机均做切换。 | `mobile-child.jpg`、`desktop-timeline-tool.jpg`；子执行 URL 的 execution 为 9a6de34e… | pass |
| R2.2 两种查看方式保留选择 | spec R2.2；design D1 | 修复后：子 read→结果→工作记录（仍有该子侧栏）→原生，检查器恢复 read、结果 tab 与原文。随后选择主 Agent 往返，当前执行仍为 54b2dd44…。A2 关闭。 | `selection-restored.jpg`；复验 DOM selected 结果 tab、同一 read 内容 | pass |

### Requirement R3：按需读取并支持连续检查 — fail（含 inconclusive）

| Scenario | 期望来源 | 实际旅程与结果 | 证据 | 结果 |
|---|---|---|---|---|
| R3.1 按需进入 | spec R3.1；design D6 | 工作记录模式不呈现 iframe；切原生先见“正在连接节点并读取原生轨迹…”和“正在加载执行轨迹…”，随后显示记录。返回记录时 iframe 销毁。未据此宣称内部所有 lease/监听计数已验证；该内部生命周期由 worker 的协议证据负责。 | 切主子及退出视图时的真实 DOM 快照 | pass |
| R3.2 历史与实时过程 | spec R3.2；design D2.1 | 连续看到30个独立 sample read 的新增记录。重新进入较长主执行时有“加载更早的历史”；点击后从请求#3以前读回初始系统、上下文和请求#1。选择旧第1轮助手后，后续第6/7轮到来仍停留旧表位置和详情，没有拉回尾部。 | `desktop-system.jpg`、`desktop-resize.jpg`；工具输出中轮次数增长与旧选中状态并存 | pass |
| R3.3 检查真实记录 | spec R3.3；design D2.1 | 已完成、进行中、失败、压缩及取消均实测。read 失败展示 FsError: FS_NOT_FOUND 与原始 not found；压缩展示摘要、原始输出、8,141ms，Token 未报告保持“—”；请求/助手包含真实用量和时间。第9轮 sleep30 被取消后原生工具状态为“失败”，结果明确 AbortError: ABORTED_BEFORE_DISPATCH / tool call aborted before dispatch，时长227ms，与普通文件错误和完成结果可区分；没有伪造成工具已完成。 | `tool-failure.jpg`、`compaction.jpg`、`cancelled-tool.jpg`；真实请求统计输出 | pass |
| R3.4 原生工具条和联动完整 | spec R3.4；design D2.1 | 时长切换实际改变时间条长度；轮次折叠为“7个步骤·6个工具调用”“7个步骤·33个工具调用”；调用折叠保留助手，工具收为“10个工具调用·read”。搜索不存在字符串得到空表，搜索文件名返回对应记录。点击子执行时间条第7记录打开同一 read 的结果/Schema。Round 3 新截图确认点击空白产生蓝色区间、区间外记录淡化，Escape 清除范围并恢复正文。缩放仍未得到有效结果。 | `desktop-timeline-tool.jpg`，四控件逐项 DOM 结果；`range-click-before.jpg`、`range-reset-after.jpg`，见 Round 3 证据来源边界 | inconclusive |
| R3.5 完整模型输入和类型化检查器 | spec R3.5；design D2.1 | 系统完整提示词／工具目录；上下文概述、预览、原始内容、来源 Nano-system；仅工具调用助手仍有行与检查器；工具参数、结果、Schema、计时；请求#4 provider anthropic、deepseek-v4-flash、reasoningEffort high、输入11807/cache11648/output87、总1s/TTFT800ms/生成201ms/432.8tok/s。桌面分隔器 ArrowLeft 实测宽度398.5→415.5；关闭按钮使详情消失。手机结果完整换行可读并能关闭。未以当前配置补历史缺失字段。 | `desktop-system.jpg`、`desktop-resize.jpg`、`mobile-result.jpg`；真实类型化检查器输出 | pass |

### Requirement R4：读取失败和节点离线可辨认 — pass

| Scenario | 期望来源 | 实际旅程与结果 | 证据 | 结果 |
|---|---|---|---|---|
| R4.1 打开时无法读取 | spec R4.1；prototype offline | caller 正常停隔离 Node，重进原生显示“节点离线，原生轨迹暂不可读取”，有重读/返回。返回工作记录显示“节点离线，正在显示已保存记录…”。1280×900 和390×844均检查。 | `offline.jpg`、`mobile-offline-open.jpg` | pass |
| R4.2 查看中断开及恢复 | spec R4.2；prototype interrupted | 已加载后 Node 停止，父状态变“更新已中断”且已有表保留。相同配置恢复后重新读取原 session 成功；窄屏点击重读恢复“已连接 · 实时更新 · 只读”。未产生查看导致的新任务。 | `mobile-reconnected.jpg`；断线时与恢复后的 DOM，保存工作轮次继续可读 | pass |

### Requirement R5：沿用查看权限、不会变成控制 — pass

| Scenario | 期望来源 | 实际旅程与结果 | 证据 | 结果 |
|---|---|---|---|---|
| R5.1 公司成员查看他人工作 | spec R5.1；design D4/D5 | reviewer 能读同一主轨迹，只有工作/资料，轨迹无指令输入、审批、取消、配置。直达原聊天只显示暂无会话/选择会话，不见其消息。工作区read_image棋盘格可预览；仅私聊Inbox的private-only.png不能预览，父状态“无法验证附件访问权限”；owner随后同条图片解码为32×32。 | `nonowner.jpg`、`chat-denied.jpg`、`private-attachment-denied.jpg`、`workspace-image-nonowner.jpg`、`private-image-owner.jpg` | pass |
| R5.2 失去访问资格 | spec R5.2；design D6 | 退出登录后原页面清除并回登录；换 reviewer 后读取以其权限执行。caller suspend reviewer 后无需reload，当前原生iframe/正文消失并返回登录。最后恢复nano登录。 | `suspended.jpg`，停用前后真实 DOM | pass |

## Reference Artifacts Reviewed

阅读了 `prototype.html` 与 design 原型对齐契约。原型仅是宿主结构，不把其占位内容当作真实轨迹。原用户两张截图只有附件名、无可读本地路径，因此不宣称对其逐像素对齐；原生内容按 design D2.1 对应真实组件逐操作核对。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype 宿主导航、执行选择 | 原页内切换、主子返回 | desktop-system、selection-restored、mobile-child | 1280×900、390×844；主/子 | match |
| prototype loading/empty/offline/interrupted | 有文字状态、重试、保留已保存记录 | empty-fixed、mobile-empty、offline、mobile-offline-open、mobile-reconnected | 两种 viewport；加载、空、离线、恢复 | match；错误下仍有加载占位见minor |
| design D2.1 工具条、三轨、完整输入、检查器 | 每项真实操作，历史/实时/Schema | desktop-timeline-tool、desktop-system、compaction、tool-failure、mobile-result、range-click-before、range-reset-after | 两种 viewport；主子与不同记录类型 | 聚焦/复位新增证据成立；缩放仍 inconclusive |
| design D2.1 原生角色颜色/密度/关闭伸缩/响应式 | 不用摘要卡替代原生记录 | desktop-resize、mobile-result | 桌面分栏；手机覆盖详情 | match，宽度用官方分隔器键盘操作验证 |

## Remaining Issues / Side Findings

取消证据边界：第一次 `/stop` 发生在原生尚无对应 bash 记录时，不能单凭 Work“已中断”证明原生取消。最终采用第二次第9轮真实工具记录；其原文明确在 dispatch 前 abort，因此本报告不声称验证了一个已运行30秒的 OS 进程被终止。所属助手已完成指输出工具调用的模型响应完成，工具自身为失败且带取消原因；两者没有混为一项状态。

| ID | Severity / relation | 现象 | Recommended Action / rationale |
|---|---|---|---|
| A3 | blocking evidence gap / unclear | 区间聚焦与复位已由 Round 3 实际截图补证；必验缩放仍缺有效结果，IAB 滚轮仅移动外层页面。 | 在支持原生缩放输入的真实浏览器补测。拖拽不是唯一验收动作，未覆盖的拖拽仅记录工具限制；当前不作源码根因结论。 |
| S1 | minor / direct | 节点离线父提示正确，但 iframe 内仍显示“正在加载执行轨迹…”，两种viewport皆如此。 | 后续可改善错误占位一致性；不阻止理解离线或返回记录。 |
| S2 | minor / unrelated-existing | Node离线时详情顶栏小圆点短时仍显示online，侧栏和Work已离线；恢复后偶见反向陈旧状态。 | 已有 #331 范围，原生可用性以真实读取结果正确提示；不扩大本unit修复范围。 |

## 上层文档同步

- [x] `SPEC.md`：需要反映 browser/client 依赖边界；caller 收尾负责，reviewer未改。
- [x] `docs/specs/im/agent-work.md` / Gateway relay：需要归并只读原生轨迹、生命周期、权限契约；caller根据最终实现归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需因这次用户旅程额外更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，未改变文档体系。

## 交付状态

本报告只描述独立产品验收，不替代技术验证、代码审查或生产部署。服务按用户要求保留，reviewer未清理共享隔离栈。截图为本机证据；报告由caller随unit统一提交，reviewer不并发提交其他角色文件。

## Round 3：A3 定向复验尝试

产品源仍为 `7e22a91d28fff92d07980845cfbabb9821cd1316`；本轮没有修改产品或需求。重新核对 R3.4：要求是保留原生时间区间聚焦与缩放能力，并未指定拖拽为唯一允许动作。因此，若通过原生空白区域点击创建范围、滚轮改变范围及 Escape 复位得到真实可观察结果，也足以关闭 A3；拖拽输入未覆盖只需记录为工具边界。

本次复唤醒时原 IAB browser 3 已不可用，重新创建 IAB 也返回 `Browser is not available: iab`；CUA inventory 仅列出连接失败的 Chrome，原生 App 通道报告 Mac 锁定且自动解锁失败，因此 reviewer 未执行新的页面输入。第一次读取 `range-click-before.jpg` 时该文件还是加载中空容器，这份旧截图不能证明聚焦。caller 随后用不触发布局重置的截图方式覆盖了同名文件，并提供复位后的第二张图；以下结论基于 reviewer 重新打开这两份当前图片的独立视觉核对，不再沿用旧文件内容。

| 实际图片 | 独立可见结果 | 来源与结论 |
|---|---|---|
| `range-click-before.jpg`（覆盖后的当前文件，1280×720） | 子执行 `Verify addition in doc` 已连接；时间线有蓝色边界和浅蓝范围，范围内两条上下文保持正常对比度，外部系统、用户、助手和工具记录淡化。 | caller 执行原生空白区域点击；reviewer 独立核图确认区间聚焦与联动结果。caller 另交接只读 DOM：selection left43.75%、width12.5%，domain100%；百分比来自该交接，不是 reviewer 从图片精确测量。 |
| `range-reset-after.jpg`（1280×720） | 同一子执行范围填充及两端边界消失，仅保留中心指示线；系统、用户、上下文、助手和工具正文恢复正常对比度。 | caller 执行 Escape；reviewer 独立核图确认清除区间与正文恢复。caller 交接只读 DOM selection[] 与图片一致。 |

**A3 当前仅剩缩放缺口。** caller 的截图坐标和 fresh AX element 滚轮输入均只移动外层页面，domain 始终100%，没有缩放成功证据。区间聚焦／复位的两张真实结果不证明缩放，因此 R3.4 仍为 inconclusive、总 verdict 保持 fail。本轮未再次尝试 UI，也未新增全量验收；其余通过场景保留。
