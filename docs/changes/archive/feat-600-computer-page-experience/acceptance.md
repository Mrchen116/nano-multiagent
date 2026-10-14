# feat-600 — 验收报告

> 对齐：[spec.md](spec.md) S1–S8、[design.md](design.md) M1 A–D 与原型 must-match。
>
> Round 1 · full / revalidation_mode=full · 2026-10-14 08:37–08:52（Asia/Shanghai）
>
> Validation snapshot: `290652ada2bf5fafbd4ac9f27a1514680ff78ca9 → 4068b2cfdd138c8bbe3b0b9d839a910fca9d36dc`

## Verdict

**pass**。S1–S8 全部通过；0 blocking、0 major、0 minor。Highest Required Action: `pass`。本轮独立操作真实 Web 后判断：电脑页的身份、可用性与当前动作形成清楚的阅读顺序，桌面与手机均可完成受影响旅程，达到交付标准。

这是 Web 电脑页验收，不能延伸为物理 iPhone、安装器实际执行、全局 toast 或创建助手下游页验收。恢复门禁与不可更新原因的部分状态使用明确标记的响应投影，范围见下文；不把投影当作后端真实恢复成功。

## 版本、环境与证据边界

- checkout：`/Users/czj/.codex/worktrees/feat-596-node-update/nano-multiagent`；分支 `codex/feat-596-node-update`。开始时核实 HEAD 为受审 SHA。期间其他 reviewer 提交报告不改变受审产品；主 agent 告知的文件末尾空白清理未重建运行前端，本轮结论始终针对上述 SHA。
- 入口 `http://127.0.0.1:56745/settings/nodes`，专用 `nano` 测试账号；独立 Playwright CLI session `computer600-review`。真实 IM、managed Node `wt-runtime-67128`、DSH；0.3.0/0.4.0 为本地候选包，无公共发行或生产操作。
- 实际服务返回 `/assets/index-D9js0oX-.js`、`/assets/index-CYZZh8ip.css`，与 caller 提供的受审构建一致。后端构建 `bbc487e6da9cd69cfc5868906b2ce17ddbff3b6e`；独立检查该提交至受审 SHA 的 `apps packages pnpm-lock.yaml` diff 为空。不读取实现定位原因，不更改源码/测试/设计。
- 第二台“家里的 Mac mini”为隔离 DB 的离线场景记录，没有第二个运行 Node。它只证明离线列表/详情体验。
- 真实链路：UI 发起更新与取消；受控模型 hold 形成真实等待；真实下载故障、目标进程启动失败、回退旧进程及成功登记。CLI 仅准备故障条件、重启本地旧版本与观察状态。
- 浏览器网络故障：PATCH 改名失败、首次/刷新列表读取失败、安装说明读取失败；clipboard writeText 拒绝仅用于复制失败反馈。
- 响应投影：从真实 `/im/v1/nodes` 响应改动当前 node 的 reason/operation/installation，显示 `legacy`、`source`、`incompatible`、`unpublished`、`recovery_required`、`rolling_back`；空列表与 `install.available=false` 也为投影。没有向服务写入伪造成功。真实回退发生很快，`rolling_back` 的阅读截图来自投影，真实日志另证明该阶段与回退终态。
- 模型输出为固定 fixture，仅用于真实 DSH 工作占用，不作为模型能力评估。没有借用实施者自检通过结论，本轮不重新宣称聊天投递链路通过。

证据主目录：`/Users/czj/Movies/Nano-Computer-Page-20261014/independent-review/`。以下文件名均相对此目录；同份原始证据在 worktree 的 `output/playwright/computer600-review/`。媒体与运行日志不入 Git。

## 用户旅程体验

### 从“哪台能用”到“现在该做什么”

1440×960 英文首屏与 820×900 布局中，两台电脑名称、文字在线状态、现用版本、助手数聚集在各自卡片顶部；更新按钮只出现在有可执行更新的卡片。离线电脑为中性灰，已知有新版本时只提示上线后操作，没有灰色不可点击更新按钮。没有统计大卡、原始 ID 或常驻改名输入框抢占首屏。证据 `01-desktop-en.png`、`05-tablet-en.png`。

真实页面与原型的最大内容宽度、轻摘要、卡片内动作区、主次按钮关系一致。与相邻聊天参考画面 `evidence/adjacent-chat.png` 对照，沿用浅色内容表面、青绿色主动作与克制边界，没有引入重型管理仪表盘。真实卡片顺序和 release notes 内容不同属于真实数据；离线记录有可信 0.4.0 target，因此比原型“同版本离线”多一条上线后更新提示，符合设计的条件性行为。

390×844 和 360×780 从“我”实际进入节点入口，再返回“我”。长名称在列表省略，进入全屏详情后完整换行；更新按钮另起一行，英文内容自然折行，未观察到水平溢出或按钮互挤。360 高度需要纵向滚动，底部导航没有封住主要动作。证据 `06-mobile-390.png`、`07-mobile-detail.png`、`08-mobile-360.png`、`33-english-360.png`、`34-english-detail-360.png`。滚动后进出详情实际位置为 90→90，见 `scroll-return.txt`。

### 按需管理，失败后继续原任务

桌面详情在右侧抽屉中保留列表背景，手机详情独立占满窗口；名称与详情箭头都能进入。真实保存长名称后列表/详情同步；取消与 Escape 放弃草稿，Escape 后焦点回到打开详情的“详情”按钮。空白名称显示就地错误。对保存请求注入网络失败后，原名称没有被覆盖，输入保持“失败时保留的电脑名称”，错误紧挨输入与保存操作。见 `02-rename-desktop.png`、`03-rename-success.png`、`04-rename-failure.png`，空值验证见本轮操作记录。最后用 Enter 真实保存恢复“我的 MacBook”。

离线详情显示绝对最后在线时间、回对应电脑打开 Nano 的说明，改名/创建助手停用且解释原因；技术标识只在展开连接诊断后出现，见 `09-offline-diagnostics.png`。切换过程中详情显示“正在更新”，并解释恢复后才能改名/创建，见 `17-switching-detail.png`。暂存草稿在停留期间保持；不把停留截图本身当作独立 heartbeat 注入测试。

### 更新阶段与失败后的决定

手机真实下载时显示“正在下载”、可以继续工作与取消；真实模型任务被占用时显示“等待任务结束”，可取消且不会强停任务。取消后旧版本仍是 0.3.0，页面重新提供更新。切换时没有取消按钮，消息等待的说明可读；刷新仍显示活动更新。成功显示现用 0.4.0 与“已更新”，刷新不丢结果。见 `10-update-start.png`（实际等待）、`11-cancelled.png`、`12-preparing.png`、`13-success.png`、`14-success-refresh.png`、`15-switching.png`、`16-switching-refresh.png`、`30-preparation-cancel.png`。

真实目标启动失败最终回退 0.3.0，页面显示“已恢复原版本”和助手可继续使用；真实下载失败则显示当前版本仍可使用并让用户检查网络重试。两者均有可执行重试；已实际从回退终态重试到下载故障，再清除故障重新发起并在准备阶段取消。见 `22-rollback-result.png`、`23-download-failure.png`。这些终态有真实进程与 operation 日志佐证。

门禁未恢复的投影呈现琥珀色“电脑需要恢复”“上次版本”，不宣称旧版可用；恢复说明明确目标电脑、先结束任务、保留身份/助手/模型/文件，并提供当前服务恢复命令。legacy/source/incompatible/unpublished 均没有可执行的一键更新。见 `projection-recovery_required.png`、`projection-recovery-guide.png`、`projection-legacy.png`、`projection-source.png`、`projection-incompatible.png`、`projection-unpublished.png`、`projection-rolling_back.png`、`37-legacy-guide-en.png`。

### 连接与读取异常

日常列表和空态均从本页打开连接说明，不把已有用户送回首次设置。手机可切换本地 Agent/手动安装方式、滚动到复制和刷新入口，并返回列表。复制成功给出反馈；clipboard 被拒时提示手动复制，命令仍可读取。没有发布安装包时只说明等待发布，不提供不可用命令。见 `18-connect-mobile.png`、`19-copy-success.png`、`20-copy-failure.png`、`27-empty.png`–`29-no-installer.png`、`36-connect-english.png`。

首次加载为占位，不先闪现“没有电脑”；初始网络失败显示重试，解除故障后真实重试回到两台列表。已有数据刷新失败保留卡片，在列表上方说明“以下是上次读取的状态”。安装说明读取失败限定在详情内，列表保留，解除故障可重试。见 `24-initial-loading.png`–`26-stale-error.png`、`35-connect-read-error.png`。

## Reference Artifacts Reviewed

实际打开并渲染 [prototype.html](prototype.html)，观察日常列表、桌面详情；结合 design 原型契约与状态信息组织对照真实产品。原型只作为 reference，不作为实际产品成功证据。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype / design M1 A | 标题摘要、紧凑卡、身份优先、单一更新动作 | 01、05、06、08、33；reference-prototype.png | 1440×960、820×900、390×844、360×780；在线/离线/长名；中英 | match；相同阅读顺序与轻层级，离线的额外说明由可信新版本数据决定 |
| prototype / design M1 B | 桌面抽屉/手机全屏、原位改名、按需诊断、失败草稿 | 02–04、07、09、17、34；reference-detail.png | 桌面/手机；保存、取消、空值、失败、离线、切换 | match；管理不占列表，名称完整可读，错误就地且保留操作上下文 |
| prototype / design M1 C | 准备/等待/切换/成功、取消、失败/回退/恢复、不可更新 | 10–17、22–23、30、projection-*、37；observations.jsonl | 手机真实更新；桌面不可更新与门禁投影 | match；无虚构百分比或剩余时间，真实终态与恢复说明分开；投影边界见前文 |
| prototype / design M1 D | 空态/加载/失败、stale 数据、连接与安装包不可用 | 18–20、24–29、35–36 | 桌面/360 手机；空、读失败、stale、无安装包、复制成功/失败 | match；下一步明确，读取失败与没有电脑不混淆 |

## 问题清单

本轮未发现需要修改的问题；没有创建外部 issue。没有用“仍可点击”降级整体体验问题，也没有以实现自检替代上述实际观察。

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| — | — | 无 | — | pass | 受影响旅程完整可完成且 must-match 成立 |

## 验收标准覆盖

### Requirement: 浏览以电脑身份、可用性与当前动作优先 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| S1 多台电脑的日常浏览 | spec S1；design M1 A / 原型列表 | 真实列表辨认在线/离线、版本、唯一更新动作，中英文桌面与平板 | 01、05、06、08、33 | pass | 离线电脑仅为 DB 场景数据；无一键更新按钮 |
| S2 手机与长名称 | spec S2；design M1 A/B | 从“我”进入、真实保存长名、全屏详情/返回/滚动恢复 | 06–09、33–34、scroll-return.txt | pass | 四种 viewport 均实际观察；不是物理手机验收 |

### Requirement: 编辑与诊断按需进入 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| S3 改名与失败恢复 | spec S3；design M1 B | 真实保存、取消、空白拒绝、Enter 保存、Escape 关闭；PATCH 网络失败保留草稿；离线禁用 | 02–04、09、31–34；操作记录 | pass | 失败由浏览器网络故障注入，未改写后端成功 |
| S4 查看连接详情 | spec S4；design M1 B | 离线详情查看最后在线与上线指引，展开诊断 | 09-offline-diagnostics.png | pass | 绝对时间明确，技术标识渐进展开 |

### Requirement: 更新反馈表达真实阶段和可行的下一步 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| S5 更新与取消 | spec S5；design M1 C | 真 UI 更新、真实模型占用等待与取消、下载/切换/刷新/成功；准备期再次取消 | 10–17、30；observations.jsonl | pass | 实际 0.3→0.4；waiting 和准备取消均真实 |
| S6 更新失败与恢复 | spec S6；design M1 C | 真下载失败、真启动失败回退；门禁/旧安装/源码/不兼容/未发布呈现投影；实际打开恢复指引 | 22–23、projection-*、37；observations.jsonl | pass | 真实回退与呈现投影分开；没有宣称手动恢复链路本轮执行 |

### Requirement: 首次连接和读取失败有清楚的下一步 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| S7 连接电脑 | spec S7；design M1 D | 日常/空列表打开连接；Agent/手动切换，复制成功/拒绝，返回；缺安装包 | 18–20、27–29、35–37 | pass | 空与无安装包为响应投影；不执行安装器 |
| S8 加载与读取失败 | spec S8；design M1 D | 网络延迟首载、abort 首次/刷新请求、解除故障重试 | 24–26、35 | pass | 首载占位、初始重试、stale 保留三种形态明确 |

## 真实 operation 索引与接管状态

`observations.jsonl` / `downloads.jsonl` / `model-events.jsonl` / `startup-events.jsonl` 仅复制本轮时间段，不含鉴权缓存。

| operation | 本轮实际结果 |
|---|---|
| `7d5f5293-f2c4-4fff-b109-82de4f820e54` | 真实任务等待 → UI 取消 |
| `279ce075-7477-4b9c-89f1-12cb6a447559` | 下载/安装/切换 → 0.4.0 成功 |
| `c075eb01-705e-40d0-a4be-dd796f410b1b` | 目标进程失败 → rolling_back → rolled_back，0.3.0 ready+connected |
| `b75560df-a435-4975-b864-d719289eeb24` | 真实下载失败，旧版仍运行 |
| `d60791d4-9f2e-406c-b6bb-81c956d9663f` | 清除下载故障后 UI 重试并准备期取消 |

浏览器路由/故障均清除，两个独立浏览器 session 已关闭。reviewer 自己的原型 HTTP 18761 已停止。共享真栈按交接要求保留：0.3.0 在线，Node PID 80147 / DSH PID 80152，最后 operation cancelled，无 active 更新；model_hold/download_fail/start_fail 全 false，下载延迟恢复 2000ms，启动延迟恢复 14000ms；电脑名恢复“我的 MacBook”。详见 `final-runtime-status.json`。最终真栈清理由 caller 接管。

## 上层文档同步

- [x] `SPEC.md`：无需更新；本 unit 无跨包职责变化。
- [x] `docs/specs/im/agents-nodes.md`：需要更新；本轮读取 canonical 仍为 feat-596，尚未含 feat-600 渐进管理与连接入口承诺。由 orchestrator 将本 unit [delta-spec](specs/im/agents-nodes.md) 归并后交付；reviewer 不改 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；文档体系未改变。
