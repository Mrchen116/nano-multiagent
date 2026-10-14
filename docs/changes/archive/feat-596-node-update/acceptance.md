# feat-596 — 产品验收报告

> 对齐：spec.md、design.md、prototype.html；独立 reviewer 真实产品验收。
> Round 1 full snapshot：`0e0c567978a89b33248cf1c342fb3311df45025b → e5cbeec26d150393f32ce46ae6936a5fa895aff9`。
> Round 2 targeted：`eba3f5cfc39d89ed7be2f952153f418febb4e247`，修复旧失败覆盖已安装版本。
> effective_base / executed_base：`0e0c567978a89b33248cf1c342fb3311df45025b`。
> R3 validated_at / effective_through：`f5fcb1da95182a4867cd145ae59114f6a8a2e738`。
> 最终 validated_at / effective_through：`56f1f577691db6a4046eaefca3dff1f7200c0c9f`。
> Round 3 targeted：`f5fcb1da95182a4867cd145ae59114f6a8a2e738`，修复升级/恢复指南宽度。

## Verdict

Round 1：**fail**。真实更新、等待、消息恢复主链路成立，但结果真实性与手机升级指引各有一项 major。

Round 2：第一项关闭，第二项继续阻塞。

Round 3：**pass**。A1/A2 均已关闭，无遗留 blocking/major，全部必验 Scenario 通过。Highest Required Action: pass。

## 环境与证据边界

- 独立 Playwright session `nano596-review`，真实浏览器、IM `http://127.0.0.1:60837`、账号 nano，节点 `wt-nano-multiagent-17159`、助手 `update-assistant`，聊天 `/chat/c_xg12nvmf`。操作未涉及生产、主仓或个人助手。
- 初始 Web build 对应 e5cbeec26；后续只替换 caller 明确冻结的两次 Web 修复产物。IM 与 Node 没有在复验中变更受审代码。
- 0.3.0/source a9fc640 与 0.4.0/source 40a60f9 是实际构建、按 hash 安装的隔离候选包；不是已发布版本。下载 transport、模型回复延时、进程启动延时/失败是受控 fixture；IM、Node、DSH、持久消息、下载校验和 worker 进程真实运行。
- 真正无更新能力的历史代码 0b2bab6cf 用于旧版过渡；实际 source CLI 用于源码部署分支；新的独立安装根目录 fresh 经真实安装器下载、冻结依赖安装、浏览器绑定，得到节点 `computer-87bea7e9`。
- 证据持久副本统一为 `/Users/czj/Movies/Nano-Node-Update-20261014/independent-review/review596-*.png`；worktree 原件为 `output/playwright/`（均不提交）。下文短文件名省略 `review596-` 与 `.png`。模型输出是受控回复，只证明工作/消息连续，不证明模型任务质量。

## 用户旅程体验

设备卡片先呈现电脑名字和在线状态，再呈现版本变化、说明、更新动作；设置名称的保存动作位于另一行。用户能判断正在操作哪台电脑，理解短暂停顿的后果，并一次点击开始；未出现重复确认。1280、820 与 390 下，正常更新区域均沿用现有卡片、边框、低饱和背景与文字层级。手机改为纵向排列，按钮没有挤压设备名字。

聊天入口只在助手身份下方加轻量电脑提示，点击直达对应电脑；更新期间消息输入仍可使用。真实切换时发送“切换期间请等待恢复后再核对会议议程。”，刷新后显示“等待电脑更新完成”，恢复后出现一条助手回复，未要求重发。桌面和手机都能把等待状态与具体消息对应。发生新旧均启动失败时，提示改为“电脑恢复后继续处理，无需重发”，电脑入口转为恢复提示，而不是无限显示正常更新。

忙碌时显示“等待任务结束”，取消按钮可见；实际取消后旧版保持在线，原先延时 60 秒的任务完成。下载失败显示原版仍可用与重试；新版启动超时后，只有旧版真实恢复才展示“已恢复原版本”。第二台新装电脑在第一台反复更新、失败和恢复期间一直在线，PID 35011 未被重启。

两个问题使 Round 1 不能交付：已完成一次性升级后仍被旧失败结果盖住，用户无法判断是否成功；手机展开指南后长命令撑宽整个内容，正文被截断，妨碍读懂升级与恢复步骤。它们分别涉及结果可信度与关键指引可读性，不能因为按钮仍可点击而降为 minor。

## Reference Artifacts Reviewed

读取 design 原型契约、共同体验标准、prototype.html 及原型实际截图；未读取实现定位问题，未继承 worker 的成功结论。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype-desktop.png / 电脑更新区域 | 设备、版本、主动作分层，更新不与别名保存混合 | current-1280、available-1280、cancelled-820、available-390、busy-390 | 1280/820/390，完成/可更新/等待/取消 | match：保持相同阅读顺序；手机取消使用次级按钮，但动作含义仍清楚 |
| prototype-mobile-chat.png / 聊天入口与等待 | 不遮聊天；发送后持久等待；恢复无需重发 | real-queue-390、queue-desktop、restored-1280、recovery-resumed | 390/1280，刷新等待/恢复 | match：真实聊天布局与原型示意背景不同，核心信息关系和交互结果一致 |
| prototype-820-recovery.png / 失败与恢复 | 状态真实且有下一步，说明可读 | download-failed-final、rollback、offline、recovery-chat-final、recovery-nodes-820 | 1280/820/390，失败/离线/需恢复 | 状态与下一步 match；390 展开指南在 R1 deviation，见 A2 |
| prototype.html / 旧版和源码边界 | 旧版一次性指引、原身份保留；源码不提供受管更新 | legacy-1280、legacy-guide-390、source、fresh-latest | 1280/390，历史旧版/源码/首次安装 | R1 旧版说明被裁切；功能路径成立，R3 定向复验 |

## 问题清单

| ID | Severity / Relation | 期望与实际、复现证据 | Recommended Action / Rationale | 状态 |
|---|---|---|---|---|
| A1 | major / direct | 下载失败后运行真实历史旧 CLI，再用新安装 setup 桥接到 0.4.0。进程与 release 均为 0.4.0 且在线；刷新仍显示“更新未完成 0.4.0；下载或准备失败…请检查网络后重试”，同时没有重试按钮。bridge-result.png | fix-implementation：当前已达目标版本后旧操作错误不能误导恢复用户 | R2 closed：eba3f5cfc 刷新显示“已是最新版本”，fixed-1280、fixed-820、fixed-390-detail |
| A2 | major / direct | 390 宽展开“查看升级方法”或“查看恢复方法”，长命令把整个说明区域撑宽，正文右侧被裁切；legacy-guide-390、recovery-nodes-390 | fix-implementation：关键操作指引需在手机完整可读，代码可独立横滚而非撑宽正文 | R3 closed：guide-fixed-390/820 与 recovery-fixed-390/820，正文完整换行，命令独立横滚 |

## 验收标准覆盖

所有来源均为本 unit spec.md 相应同名 Scenario；视觉另外对齐 design.md 的 must-match 契约。表中状态为 R3 最终累计结果；R1/R2 原始失败保留在上述轮次与问题清单。

### Requirement: 用户主动发起单台电脑更新

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 发现并点击新版本 | 聊天轻提示直达精确节点；版本 0.3.0→0.4.0 与说明可读；单击立即推进，无确认；available-1280/390、doubleclick；第二节点持续在线 | pass | 点击前只呈现版本，未观察到自行切换；受控候选不是生产发布 |
| 离线与无新版 | 真实 stop 后显示“电脑上线后可更新”、更新 disabled；独立新安装显示“已是最新版本”且无更新动作；offline、fresh-latest | pass | A1 特殊恢复后的旧结果遮盖已在 R2 关闭 |

### Requirement: 下载与等待不打断工作

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 下载后等待任务 | 真实 DSH 模型调用延时 60 秒；点击后显示“等待任务结束”，仍为在线 0.3.0；busy-390；后续聊天可见原任务完整回复 | pass | 使用受控模型延时制造真实在途工作 |
| 取消或重复点击 | 等待时点击取消，卡片“已取消更新”、0.3.0继续在线；双击更新只见单次流程并最终一次成功；cancelled-820、doubleclick、close-reopen-success | pass | UI 在操作开始后立即收掉可重复更新动作 |

### Requirement: 切换期间聊天连续且状态可恢复

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 更新期间发消息并刷新 | 等到切换提示后发送会议议程消息，刷新后看到原消息等待；恢复后只出现一条对应回复；real-queue-390、queue-desktop、restored-1280 | pass | 早期一次截图落在 reload 初始空态，未用该截图作为通过依据 |
| 关闭网页仍完成 | 真实更新中关闭产品 tab，以空白 tab 留存浏览器，再重新进入；版本 0.4.0成功；close-reopen-success。配置与自建工作目录文件 SHA-256 前后相同；同 node/助手/聊天继续可用 | pass | preservation.json 仅保存 hash，不保存配置秘密；文件保留亦覆盖旧版桥接 |

### Requirement: 失败可恢复且结果真实

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 下载失败 | 将目标缓存目录改名保存，fixture拒绝下载；真实 worker 报失败，旧0.3在线且可重试；download-failed-final。随后原缓存完整恢复 | pass | 未删除用户资料，未放宽URL/hash验证 |
| 新版启动失败 | 新版启动延时超过 readiness 后真实恢复旧0.3；rollback。新旧启动均失败则“需要恢复电脑”，消息改等恢复；recovery-chat-final。解除fixture后真实启动旧版，排队消息自动回复一次；recovery-resumed | pass | R3 真实重走新旧启动均失败，恢复指南390/820复验通过，A2关闭 |

### Requirement: 新旧安装用户都能进入按钮更新

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 首次安装与旧版过渡 | 全新 root 跑来自真实 IM 的 install.sh，真实下载/依赖安装/绑定 computer-87bea7e9，显示最新。旧节点实际切至无更新功能历史 CLI，再用新安装 setup桥接，原配置与工作文件 hash相同，原助手聊天保留；fresh-latest、legacy-1280、guide-fixed-390 | pass | R1 A1/A2影响过渡结果/指引；R2关闭A1，R3指南复验通过关闭A2 |

## 上层文档同步

- [x] `SPEC.md`：无需更新，未改变跨包架构边界。
- [x] `docs/specs/im/agents-nodes.md`、`docs/specs/im/gateway-relay.md`、`docs/specs/gateway/service-lifecycle.md`：需要由 orchestrator 归并本 unit delta；验收读取时 canonical 尚未包含此增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，未改变文档体系。

未创建 GitHub issue；未修改受审实现、测试或生产配置。按 caller 明确交接要求，报告不单独 commit，由主 agent 统一提交。

## Round 3 收口与保留证据

修复范围只涉及卡片结果优先级与指南容器宽度，没有更改 Node/IM/更新进程；因此保留 R1 实际成功更新、等待取消、刷新消息恢复、下载失败、回退与安装证据。R3 重新运行真实历史旧节点观察指南，并再次触发新旧均启动失败，实际查看390/820恢复页面，非伪造状态或静态原型。两个指南正文全部可读，版本与动作仍与设备身份关联，命令滚动限于代码块，见 guide-fixed-* 与 recovery-fixed-*。

最终恢复主验收电脑至受管0.4.0，故障开关全部false、启动延时12秒；停止本 reviewer 新装的 fresh 节点进程，保留其隔离身份/数据供追溯。未停止IM或fixture。截图已复制持久目录，原始失败截图一并保留。用户要求的整体验收视频由 caller另行录制；本报告不以视频缺省内容替代独立截图与实际操作证据。

## Round 4 — 发送后即时等待提示定向复验

- mode：targeted；validated_at / effective_through：`56f1f577691db6a4046eaefca3dff1f7200c0c9f`。
- executed_base / effective_base：`0e0c567978a89b33248cf1c342fb3311df45025b`；fix_delta：`f5fcb1da95182a4867cd145ae59114f6a8a2e738 → 56f1f577691db6a4046eaefca3dff1f7200c0c9f`。
- Verdict：**pass**；Highest Required Action：pass；未遗留 blocking/major。

### 原验收边界与新增问题

R3 的 pass 是当时真实观察的结论，保留不抹去。此前“切换发送并刷新”的证据证明刷新后等待状态及恢复回复，**没有覆盖 WS 消息回显先于 POST 返回时，发送后不刷新能否即时显示等待**。主录屏随后发现该顺序下等待提示缺失，属于当前聊天可理解性的遗漏，不能由此前刷新后的截图反推已验证。caller 修复了同 ID 消息的返回合并；本 reviewer 不读实现根因，仅对实际用户结果定向重验。

### 实际操作与证据

复用同一真实 IM/Node/DSH、同一助手聊天。reset 到0.3.0，真实页面点击更新，等到切换状态后发送独特消息：“请在本次更新完成后核对周四会议材料，保留这条请求。”启动延时18秒只用于保留可观察窗口，故障开关均false。

| 检查点 | 实际观察与用户含义 | 证据 | 结果 |
|---|---|---|---|
| 无刷新即时反馈 | 点击发送后等待文案直接出现在本条气泡下面，电脑chip为正在更新；用户知道消息已经收下，无需猜测或重发 | r4-no-refresh-1280、r4-no-refresh-390 | pass |
| 刷新后持久等待 | 同一条消息仍在，“等待电脑更新完成”保留，输入框可用；手机文字与气泡对应且没有遮挡 | r4-refreshed-1280、r4-refreshed-390 | pass |
| 恢复一次处理 | 0.4.0上线，等待提示消失，独特消息后只有一条助手回复；随后读取实际聊天尾部再次核对没有第二条回复 | r4-completed-1280、r4-completed-390 | pass |

这一轮补足 spec“更新期间发消息并刷新”与 design聊天must-match的发送后即时等待部分。R1-R3的安装、取消、下载失败、回退、恢复、指南与其他布局结论仍按各自具体证据保留；未因这次局部消息合并修复重新宣称复跑所有场景。

所有 R4 截图已复制到 `/Users/czj/Movies/Nano-Node-Update-20261014/independent-review/`。交回时主节点受管0.4.0在线，PID39881；IM与fixture未停止。报告未commit。最终累计结论：**pass**。
