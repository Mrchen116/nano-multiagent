# M1 实施与真实运行证据

## 基线与边界

- Branch: `codex/feat-596-node-update`。首轮实现 `a9fc640ee2becbc5314019dd799bebaa81db1ff2`；HTTP 鉴权及聊天恢复修复 `2690627d6`；final sync `40a60f9` 合入 `origin/main=0e0c56797`；第二次发布提示修复 `e5cbeec26`。
- 产品验收后的终态修复 `eba3f5cfc`：一次性升级已达到推荐版本后不再展示旧失败。指南修复 `f5fcb1da9` 仅增加更新卡片 `min-w-0`，使窄屏升级/恢复指南正文换行、命令在内部横向滚动。`fcb4524b0` 只增强后台 review 的真实 DSH 屏障回归，不改变运行代码。
- 独立 worktree：`/Users/czj/.codex/worktrees/feat-596-node-update/nano-multiagent`。IM `http://127.0.0.1:60837`；测试身份 nano；电脑 `wt-nano-multiagent-17159`；助手 `update-assistant`；会话 `c_xg12nvmf`。所有操作仅作用于该隔离环境。
- 真 IM、SQLite、安装目录、Node、DSH、CLI、后台更新进程和 Web 浏览器。私有配置、凭据、PID、DB、原始日志及缓存不提交。
- 受控部分：固定 GitHub URL 的下载 transport 映射到本地真实构建的 tar；模型使用本地 OpenAI SSE fixture；新版本进程可注入启动失败或 12 秒启动延时，以稳定观察切换窗口。没有修改产品 URL/hash 校验，也没有用 mock Node/DSH 替代真实进程。
- 0.2.0 / 0.3.0 / 0.4.0 是本次候选包演示版本，**没有发布 GitHub Release，也没有部署生产**。0.2/0.3 来自 `a9fc640`；0.4 来自 `40a60f9`，后续前端修复不改变包内 Node 实现。

## 实施验证

| Claim | Method / locator | Result / limit |
|---|---|---|
| TypeScript 包装配与类型 | `pnpm -r build`、`pnpm typecheck` | 全部通过；构建不是产品体验结论 |
| Runtime / IM / PA 回归 | `pnpm test`，`/tmp/nano596-final-tests.log` | 最终 79 files / 294 tests passed；`pnpm typecheck` 同轮全通过 |
| HTTP report 在完整服务钩子下鉴权 | `pnpm exec vitest run apps/im-server/tests/node-updates.test.ts` | 7 passed；覆盖 runtime token 在 WS 断开时通过 report、普通管理接口仍拒绝该凭据 |
| 包验证、取消、进程切换/回退、worker 丢失 | `apps/node/tests/node-updater.test.ts`、`update-process.test.ts`、lifecycle / release / installer 相关测试 | 6 files / 21 tests；其中 OS 进程 fixture 的 registration 是模拟，不能替代下文真栈 |
| DSH 安全边界 | `update-barrier-native.test.ts`、Workflow、model-setup、PA 控制/heartbeat tests | 真 DSH 的 idle hold、queued inbox/cold recovery、Cron 保留、child/paused Workflow、未提交模型事务及 PA delivery 边界通过 |
| Web 回归 | `npm run test`，`/tmp/nano596-final-frontend-tests.log` | 最终 93 files / 865 tests passed（`/tmp/nano596-final-frontend-race-tests.log`）；包含旧终态与发送等待竞态新增回归 |
| 第二次发布仍展示新版本与说明 | `node-update-panel.test.tsx` | 4 passed；真实 0.3→0.4 发布场景暴露并修复旧 succeeded 结果遮挡新版本 |
| Web 构建与依赖 | `npm run build`；`npm audit --audit-level=critical` | build passed，0 vulnerabilities；仅已有 bundle-size/dynamic-import 提示 |
| 工具及架构 | `pytest -m 'not e2e' -q`；`ruff check .`；`ruff format --check .` | 56 passed / 31 deselected；ruff 均通过；独立 reviewer 另跑架构契约 13 passed |
| 已有原生客户端 CI | `NANO_IOS_SIMULATOR_ID=34BB4D05-8D23-498E-929E-B57C11FFF2DA NANO_IOS_BUILD_ROOT=/tmp/nano596-ios-build ./src/IM/ios/scripts/build.sh test`，随后同 BUILD_ROOT `archive` | Xcode 26.4.1 / iOS 26.4；28 tests passed；Release archive succeeded。专属临时 Simulator 已删除；不是新增原生更新管理界面的验收 |
| 后台 review 不被更新打断 | `pnpm exec vitest run packages/dsh-integration/tests/knowledge.test.ts` | 4 passed；真实 review child 暂停在模型 fixture 时 prepare 返回 busy，放行后 memory/skill facts 正常完成；无新增产品代码 |

## 真栈操作记录（2026-10-14，UTC+8）

### 点击前不下载、忙碌等待、取消

1. 真实安装 0.2.0 后 Node PID `17807`、DSH PID `17811`，IM 报告 `managed/0.2.0`。浏览器 `/chat/c_xg12nvmf` 的“我的 MacBook 有新版本”直达该电脑卡片。
2. 下载记录在点击前只有 0.2.0；0.3.0 首次下载为 `00:24:53`，对应真实更新按钮操作。取消安装阶段操作 `0ff60522-1911-4d62-9109-4733aaebaf52` 后仍是原 PID/版本。
3. 模型下一次回复延迟 90 秒。发送“请继续整理项目进展，我会等你完成。”后发起更新 `25236614-772b-4897-84ad-a6ffffdd5b2f`。新包准备好后显示“等待任务结束”，而原任务继续；手机 390×844 点击取消后显示“已取消更新”，Node 仍为 PID `17807` / 0.2.0。
4. 该任务最终完成并回复，未被更新取消。重新发起 `ac579d41-d730-4379-9f4d-87983d0942f7`，任务结束后切换；0.3.0 Node PID `25848` / DSH `25853` 实际上线后才 succeeded（`00:27:03.919`）。

### 切换时消息等待、刷新与恰好一次恢复

1. 第一次真实切换中发送消息 `7aabf70c82ef4d4187b3e90d50da1ed2`（`00:27:01.749`），成功之后才开始回复 `c903ae387bcd4e459086ae7c894e2110`（`00:27:03.947`）。仅一条 relay 和最终回复。
2. 0.3→0.4 的操作 `256417a1-c564-4a25-a929-54f7f3050429` 使用 12 秒受控启动延时。切换中发送“这条消息在更新时发送，更新后继续处理即可。”，消息 ID `c1563d50cc8f415ba6d27f094dcf6778`，幂等键 `c1563d50cc8f415ba6d27f094dcf6778:update-assistant`。
3. 浏览器显示“正在更新”和消息下方“等待电脑更新完成”；立即 reload 后同一消息与等待说明仍在，输入仍可用。真实截图 `update-chat-waiting-final.png`、`update-chat-refreshed-waiting.png`。
4. 0.4.0 Node PID `27623` / DSH `27642`、正确 hash/commit、ready+connected 都成立后，操作于 `00:32:03.481` succeeded。观测到该 relay 从 queued→sent→completed，只有一条回复；无重发动作。结果截图 `update-chat-completed.png`、`update-desktop-succeeded.png`。

### 下载失败与新版本启动失败

- 注入下载 transport 失败，操作 `370ac02a-efc5-4619-aa07-579b5f2250b5` 于 `00:30:16.445` failed；原 0.3 继续在线，UI“更新未完成”提供重试，没有成功误报。
- 清除下载故障，注入只针对新 0.4 进程的启动失败。操作 `461e14a6-bb07-473c-a6e4-c51124a38ad6` 经实际 CLI 启动超时、停止新进程、启动原 0.3、核对上线后，于 `00:31:15.196` rolled_back。页面“已恢复原版本”，可重试。随后解除故障，上一节 0.4 成功路径完成。
- 历史旧代码 `0b2bab6cf` 已在 `output/playwright/node-update-fixture/legacy-source` 独立安装依赖并构建，供产品 reviewer 从真实无更新能力的旧进程走一次性 setup 过渡；结果由独立 acceptance 报告给出。

## 真实视觉与视频定位

桌面 1280×900 与手机 390×844 已实际检查：设备身份、更新阶段/版本、解释和单一主动作能分辨，更新按钮独立于名称保存。等待态未遮蔽设备身份；聊天提示位于电脑入口和对应消息下方，不挡输入。820 viewport、全场景整体裁决及 must-match 对照由独立产品验收补齐，不能从这些局部检查推导完整 pass。

原始证据在本 worktree 的 `output/playwright/`：

- `update-desktop-downloading.png` 实际截图时已进入 waiting（文件名保留，结论按画面）；`update-mobile-waiting.png`、`update-mobile-cancelled.png`。
- `update-download-failed.png`、`update-rolled-back.png`、上文消息等待/完成截图。
- `node-update-wait-cancel.webm`、`node-update-complete.webm`、`node-update-rollback.webm` 是真实浏览器录制；初次调试录像不是最终演示。
- `node-update-fixture/switch-observations.jsonl` 是仅含操作/进程/relay 状态的时间序列；`downloads.jsonl` 和 `model-events.jsonl` 记录受控传输与模型条件。运行目录不会进入提交；交付视频保存至仓外持久目录。

## 已发现问题与闭环

- 真栈的合法 updater report 返回 401：preHandler 已走严格 runtime 鉴权，但 onSend 再用 browser principal 拒绝。为同一窄路径加上匹配豁免，新增完整 createServer hook 回归；其余管理接口鉴权不变。
- 全量前端的恢复名称回归：own-node 查询旧快照覆盖联系人新快照。保留联系人显示名称权威，节点查询只补充更新信息和缺省名称。
- 第二次发布仍显示上次“已更新”：active/available 优先级补正并加现有组件回归。
- 独立产品验收发现一次性 bridge 已成功后仍显示旧失败：当当前已达推荐版本，非 succeeded 的旧终态不再覆盖 current；5 项组件回归通过，产品 reviewer 的 R2 刷新确认三宽均显示“已是最新版本”。

## 测试归属

保留既有生命周期、安装、Workflow、Knowledge、模型、聊天恢复测试并在风险所属 seam 扩展。共享 manifest 校验、持久授权/取消与 report 接线、本机 worker/lease、真 DSH idle hold、Web 更新交互分别需要自己的最低层保护；临时发行包、进程观测和浏览器脚本只用于本次真栈验收，不进入永久测试套。没有添加第二套 Agent Loop 或改动 DSH 上游。

## 最终集成有效性

- Final sync 在产品代码冻结 `f5fcb1da9` 后再次 fetch，`origin/main` 仍为 `0e0c56797`；没有新增 main 差异。
- `e5cbeec26` 之后运行代码涉及 Web 更新面板的旧终态优先级、指南宽度及 `56f1f5776` 聊天 POST/WS 顺序修复。后端全量、架构和 iOS 结果保留；最新前端全量与 build 通过。独立 reviewer 的复验和静态 delta 审查分别记录在 acceptance/code-review 报告。
- M1 产品代码未新增第二套执行循环、源码更新入口或生产部署行为；最终归并和归档仅改变文档路径与 current spec，不使实现审查结论失效。

### 录屏暴露的消息先后顺序修复

真实操作 `036b9ec4-848f-4121-bcef-34af2e772d21` 切换期间，消息 `7fbec13bdc7a4656b5e14da7c95cff0c` 在 00:58:54.345 被接受，新版成功 00:59:06.600 后仅回复一次，但发出后气泡没有即时等待提示。原因是 `message.created` echo 先创建同 ID 气泡，发送 POST 的最终 `update_wait` 被 append_optimistic 的重复 ID 早退丢弃。新增现有 workspace integration 回归，先 echo 后响应，修复前准确报缺 Waiting for computer update。`56f1f5776` 移除该早退，沿已有按 ID 合并更新同一个气泡；完整 workspace 55 tests passed、Web build passed，随后全前端 93 files / 865 tests passed。实际重走发送、刷新、一次回复的视频与独立复验见最终交付记录。

## 最终视频交付

- 真实 Web build：`56f1f5776`；1280×900；连续录制 78.48 秒，MP4仅转码、没有拼接或伪造状态。`/Users/czj/Movies/Nano-Node-Update-20261014/01-node-update-overall.mp4`；原始 `01-node-update-original.webm`。补充失败回滚视频 `02-update-rollback.mp4` 保留早一轮未受影响的真实运行证据。
- 画面：聊天新版提示→点击更新→下载准备→忙碌等待→取消→重新更新→切换中发送→即时等待→刷新仍等待→自动回复→电脑已更新。模型本次任务延时40秒，目标进程延时18秒，仅用于真实运行中的稳定观察。
- 取消操作 `eeb9b70d-6128-4338-bd52-075ffdb8b555`；随后成功 `12baed71-ef25-4d6d-b1ee-b130ec7060a7`，01:05:53.661（UTC+8）。消息 `639a01da0d6d47ea8b4bf8dc48bcc81b` 于01:05:35.921发送，唯一relay key `639a01da0d6d47ea8b4bf8dc48bcc81b:update-assistant`，完成后唯一回复 `1690f50a41d64d9ebab6fa1e4bda2f78` 于01:05:53.892。
- 同目录 `delivery-message-wait.png`、`delivery-message-refreshed.png`、`delivery-message-completed.png` 是本次实际页面截图；主agent已逐图核实等待文案和回复。独立产品复验的R4另记在acceptance报告。
- `independent-review/` 持久保留验收原始失败、修复后及多宽截图。所有媒体/日志/私有配置均不提交Git；交付目录位于worktree外，不随清理删除。
