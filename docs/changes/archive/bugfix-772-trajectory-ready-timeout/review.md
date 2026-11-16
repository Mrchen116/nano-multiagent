# bugfix-772: Review

## 范围与版本

- 目标见 [fix.md](fix.md)：配对后的首帧等待有界退出、可手动重读，保留正常读取与票据/授权边界。
- executed_base：`b76955bf3b24bedec105b7f9130e77546e4383dc`。
- R1 validated_at：`9d7f3e1a3e4b5d7fe2d4a4464d4f2281587b4d73`；R2 和最终浏览器 validated_at：`f48840b4d8c2742458f3d6f2950bfdd6555d496b`。
- 最终同步时 origin/develop 未推进；effective_base 同 executed_base。后续报告与归档提交不改变受审代码，结论保留至本报告所在最终提交。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 首帧期限、重试、ready 后解除期限、票据与清理 | change-code-review，trajectory_code_review 独立 R1 full | pass | 核对两个连接顺序及真实 IM 红绿日志；服务端无 finding。旧 DSH 内部卡点不在已知根因内 |
| 初次失败不继续展示过时加载画面，已加载内容在中断时保留 | 同一独立审查者 R2 closure | pass | f48840b 修复 P2；核对修前失败、修后 8 项组件回归、diff check，最终契约 aligned，无新增 findings |
| 超时可理解且能点击恢复 | frontend-experience-review，主 Agent 自检 | pass | 隔离真实 IM + NodeTrajectory + RuntimeClient/DSH + Web；准备请求由夹具受控阻塞，30 秒显示超时且隐藏过时 iframe；解除阻塞后点重新读取，真实 DSH 2622 ms 返回 ready，原 Dreaming 轨迹可见 |

## Findings 与关闭

- F1，P2 / confirmed，R1：首帧超时后 iframe 仍显示“正在加载执行轨迹…”。resolution：初次失败隐藏 iframe，初始化后的网络错误保持 interrupted 和已有内容。R2 独立审查确认关闭，validated_at f48840b；主 Agent 随后在真实浏览器确认。无存活实现 findings。

## 验证证据

- 真实 IM / Node 轨迹：2 文件、11 tests passed；新增行为修前在 35 秒未关闭而失败，修后两种配对顺序超时、新观察 ready、静默 31 秒后读取均通过。
- 前端轨迹组件：8 passed；前端完整套件重跑 `--maxWorkers=2`：122 文件、1199 passed。首轮并发全量出现 5 项失败，未改实现再次通过；不能仅据此断言其根因。
- build、typecheck、check:ios-runtime、Python 136 passed、ruff check/format、docs-check 通过。npm critical audit 通过（已有 5 high、2 moderate、4 low）。
- 后端完整套件 `--maxWorkers=4`：244 文件中 233 passed / 11 failed，1375 passed / 17 failed；随后仅串行复跑 11 个失败文件：8 passed / 3 failed，63 passed / 4 failed。剩余是 workspace-tools 能力检查超时、communication-native 15 秒超时、runtime-fs-recovery 的 resume/stopped RPC 不可用。相关 DSH/PA/contracts/Node 源码、测试和锁文件与 executed_base 完全一致，均未修改；本机同时存在其他高负载进程，但未确认因果。本地全量门禁不能记为 pass；远端 CI 是下一项独立环境验证，其结果见 PR checks。
- 本机证据：`/Users/czj/.local/share/nano-multiagent/evidence/bugfix-772-20261116/`；截图 timeout-fixed.jpg / recovered.jpg、events.json、一次性 browser-fixture.ts。测试日志以 nano-772-* 保存。原始轨迹复制到临时测试 home，仅做只读回放；没有发起 LLM/Agent 任务，没有把生产轨迹提交到仓库。

## 流程收口

- 最终 delta/current spec 已由独立审查者校对 aligned。未更改 DSH、代理、协议授权、生产配置。
- 浏览器场景是受控未返回故障与真实 DSH 恢复，不能证明未知的旧进程内部阻塞原因已修复；若内部仍卡住，重读仍可能超时。
- 测试服务正常结束，19272 无监听、测试 home 已删除，一次性夹具已移出仓库；开发 worktree 按 PR 审查要求保留。
- 功能范围、独立审查与真实浏览器验收通过；本地全量遗留上述 4 项失败，保留限制并通过 PR CI 继续验证，不在本 unit 修改无关运行时。交付 PR 到 develop；不合并、不生产部署。
