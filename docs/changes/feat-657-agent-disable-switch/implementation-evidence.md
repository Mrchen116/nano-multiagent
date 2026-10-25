# feat-657 实施与验证证据

## 版本与环境

实施基线 `a54d11aed`；初次集成 `701b6caa6`，R1 验证 `935510058`；审查修复 `e55e5285a`，原生空态轮询修复 `acd31de98`。最终同步 `a97c96f65` / main `f31339119` 仅引入其他 feat-658 的设计文档，不改变本 unit 实现、current spec 或测试；既有审查范围保留。最终文档归并、归档不改变运行行为。

真实验收使用本 unit 独立 `--profile daily` 栈，最新目录 `/tmp/nano-feat-657-release-check`，IM 64018，Node `wt-nano-feat-657-release-check-52895`。固定 P/E/Q 为 gpt-6.1-sol/high/Codex，PA 为 gpt-6-astra/medium/Codex，另经真实 API 增加 single_thread S；不替换审批模型，不访问生产身份或生产数据。测试配置与截图不提交仓库。

## 自动化验证

- 最新后端 build、全部 workspace typecheck 通过；后端全套 139 文件中 738 tests 通过，唯一 `task-execution-limits` 在并发负载下达到原 45 秒轮询期限；同一源码、原阈值的独立运行通过（66.43 秒整个用例）。本地覆盖合计 739 tests，保留并发失败事实，交付另以远端完整 CI 为准。日志 `/tmp/nano-feat657-backend-green.log`、`/tmp/nano-feat657-limit-isolated.log`。不修改产品逻辑或放宽阈值来消除负载问题。
- 修复后的 lifecycle/proof/migration 窄验证 15 tests 通过；包括旧 single-layout 源目录 plan/apply/verify 字节不变、重复更新清理凭证、重启后语义相等 SessionBinding 不受 JSON key order 影响。日志 `/tmp/nano-feat657-last-narrow.log`。
- Web 全套 108 文件、1,028 tests 通过；生产 build 通过。日志 `/tmp/nano-feat657-frontend-green.log`、`/tmp/nano-feat657-web-build4.log`。
- Python helper/architecture 70 passed / 32 deselected；包括执行运行时公开 export 和跨包边界。日志 `/tmp/nano-feat657-python-final.log`。
- 最新 iOS 25 tests / 5 suites 的 xcodebuild 完整 `TEST SUCCEEDED`（`/tmp/nano-ios-feat657-final-tests.log`）。此前一次所有断言通过但诊断收集找不到 simctl，未作为完整成功；显式 Xcode 工具路径后重跑解决。
- Native owner 停止测试覆盖 root/child/grandchild/continuable、受管 Bash 及忽略 TERM 的后代、PTY 前台工作；五秒期限内确认目标停止，独立 host 继续写入，最后历史 delta 与层级保留。原证据 `/Users/czj/.codex/reports/feat-657-runtime-stop/evidence.md`；最新完整后端包含该测试。
- 冷历史测试使用公开 Session/Query/Storage API，检查源文件哈希不变、零业务 Agent 创建、旧 running 无当前证据时为 unknown；迁移测试保留 SQLite/WAL、普通/PA 归属、后代、fork、附件、Nano domains 和计划记录。

## 真实产品与进程结果

- P、PA、S 的真实模型基线分别为 `FEAT657-P-BASELINE`、`FEAT657-PA-BASELINE`、`FEAT657-S-BASELINE`。PA 停用 revision2 于 10:24:57.500Z 确认（受理到确认 182ms）；停用消息保留未处理；明确启用 revision3 后新请求得到 `FEAT657-PA-FRESH`，消息 `91e074fbe8234350b57f7e021d95b680`，10:27:12.727Z。旧停用消息未补回。原记录 `pa-cycle.json`、`messages-c_73d1701610d9.json`。
- Q：真实停止 Node 并等待 IM 显示 offline 后，创建两项 doing 任务并请求停用；中心立即将任务暂停，生命周期保持 desired=disabled/revision2、applied1/stopping。重启后先应用权威，Q 确认 disabled/applied2，旧 PID 53075 已不存在且未启动新 Q host；重新启用后两图仍 paused。真人 apply 只恢复 `tg_cb22adf1`，另一图仍 paused；随后再次停用 Q。证据 `offline.json`、`offline-verified.json`；独立离线页面截图 `/tmp/nano-feat-657-review/r2/q-offline-pending.png`。
- 独立 reviewer 实际让 E 的 Bash 持续追加进度、P 同时执行 sleep 25。E 停用请求 10:27:42.131Z，确认 10:27:42.331Z，进度最后一行 18:27:41 且后续不再变化；P 在 10:27:44.354Z 正常发出 `R2-P-CONTINUES`（`dfc9bedecc2a48498079c43d60725145`），证明停用 E 后其他 Agent 仍完成工作。
- 非 owner 新测试账号通过真实 HTTP 尝试修改 P lifecycle 返回 404；同空间非管理者 403 和 Agent 身份拒绝由 IM identity 测试覆盖。原记录 `nonowner.json`。
- 原生 iPhone 17/iOS 26.4 三个独立页面：详情和 Work 各一个 Enable again 操作，配置页仅一个 Toggle；Disabled 与设备 Online 分别展示。44pt 最小操作高度已在布局中落实；最大动态字体实际可换行滚动、无操作重叠。截图 `ios-profile-disabled.png`、`ios-config-disabled.png`、`ios-work-disabled.png`、`ios-work-disabled-large-type.png`。聊天实际显示 Not processing new messages，保留历史和输入框，截图 `ios-disabled-chat.png`。最终修复使用始终挂载的 VStack 启动状态轮询，避免首次空 Group 不执行 task。

## 资源观测与边界

最新隔离栈初始 control + P/E/Q/PA 五个不同 host，Node PID 53003；观测到的 host PID 为 53013、53074、53075、53076、53083。首次模型请求之前 RSS 分别 242160、267088、276832、261824、279104 KiB（RSS 相加包含共享页，不是独占物理内存）；约 236–273 MiB/host。这是该机器单次观测，不作生产性能保证。控制进程创建至 P/E/Q 首次注册就绪约五秒，PA 为后续独立创建；原始 `process-baseline.txt`、`baseline.log` 和 gateway 日志保留时间依据。

停用确认仅覆盖 DSH 公开服务可管理的 owner 资源。macOS 上顶层 PTY 持续生成后代的早期真实 fixture 曾使 DSH 返回 surviving pids；本实现如实停留 stop_unconfirmed，禁止 Enable，并显示具体原因。用户已接受平台范围；通过普通 PTY 前台场景不代表该逃逸/持续派生模式得到修复。不撤销外部已提交动作，不额外杀其他 Agent，不 fork/patch DSH。

生产部署必须按 deployment-prompt.md 停服并执行旧共享数据离线 plan/apply/verify；本次只验证隔离副本，未做生产迁移、部署、重启或安装包发布。

## 最终补充

- iOS Release device archive 完整 `ARCHIVE SUCCEEDED`，仅本地产生未签名 IPA，未发布或安装到用户设备。日志 `/tmp/nano-ios-feat657-final-archive.log`。
- 全部 P/E/Q/PA/S 均确认 disabled 后，真实进程检查只剩 control PID 54587。模型设置 `status` 返回服务/目录/默认模型；Q 已保存配置 GET/PATCH 更新 description 成功；P Work 记录 GET 成功。管理读取和写入前后仍只有 control，证据 `alloff.json`、`alloff.log`。配置测试首次缺少既有 API 必填字段得到 422，按完整配置契约重试后通过，不是产品修复。
- Web 新会话 S 回复 `R2-S-NEW-OK`；E 重新启用后真实群提及得到回复 `4468b137d0a04241b605052442547c85`，旧 held 消息未补跑，原进度文件仍为 12 行且末行 18:27:41。独立结论见 acceptance.md。
- 全停用状态下独立 reviewer 打开 P 完整原生轨迹并看到 sleep/send_message 真实历史，截图 `/tmp/nano-feat-657-review/r2/alloff-p-native-history.png`；读取后再次检查仍仅 control PID54587，`alloff.json.afterNativeHistory` 留证。
- 对已确认独立归属的空闲 S host PID57481 注入 SIGSTOP，使真实 RPC 无响应。Web Disable 到达五秒期限后显示 stop_unconfirmed/applied5/revision6，并显示具体 deadline 原因；supervisor 已终止该 host，但不以进程退出冒充资源清理成功。Retry 仍未确认，不能 Enable；真人 API Enable 返回409。reviewer 检查1440/390/320失败/重试页面。证据 `unresponsive-host.json`、`unconfirmed-enable-denied.json`、`/tmp/nano-feat-657-review/r2/unconfirmed*.png`。不强行清除未知凭证，不恢复该故障现场。
