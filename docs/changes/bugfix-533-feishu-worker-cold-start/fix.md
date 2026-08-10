# bugfix-533: Feishu worker 冷启动无法就绪

## Relations

- Blocks: refactor-522
- Related: feat-464, bugfix-496
- Closes: #267

## 原始报告

> 为啥之前我好多feature都做了，他们那些agent也没反馈这个问题，而且我看他们实际上确实也用了飞书做测试，是偶发问题吗，

> 要怎么修复？

> 好，你可以去修

> Issue #267：https://github.com/Mrchen116/nano-multiagent/issues/267

## 澄清记录

- Q1: 是否按上一轮推荐把它作为独立 bugfix 修复：恢复 Feishu worker 的轻量启动 seam，不靠放宽 timeout，并用真实飞书冷启动旅程验收？
  A(原话): 好，你可以去修
  Agent 解读: 用户确认独立修复 Issue #267；refactor-522 不吸收这项既有启动缺陷，修复完成后对其执行定向 Feishu 复验。

## 现象 / 复现

Gateway 配置有效飞书 channel 后，干净启动有时能正常进入飞书消息收发，有时会在外层启动脚本等待 30 秒后失败，Gateway 报告 `feishu worker did not initialize`。失败发生后，用户无法从飞书向 Bot 发起消息，内部 IM 也不会产生对应 shadow 消息。

该问题已在 refactor-522 验收树、其修复前快照和 clean main 上复现；凭据、飞书 provider 网络、SDK 运行期崩溃和 refactor-522 的 session-continuity 改动均已排除。诊断时，子进程在父进程的固定 worker-ready 等待到期后仍处于 `lark_oapi` 冷导入阶段，尚未进入 worker bootstrap。相同生产路径在此前 feat-501、refactor-521 和 refactor-522 早期验收中也曾真实成功，因此这是受冷导入耗时、系统调度和缓存状态影响的启动不稳定，而不是飞书消息语义每次必坏。

用户可观察的目标状态是：在支持的普通机器负载下，无预热启动或重启配置了飞书 channel 的 Gateway，都能稳定进入可用状态；用户随后从真实飞书发送消息，能收到 Bot 回复并在内部 IM 看到唯一对应 shadow。启动稳定性修复不得改变正常消息、控制命令、审批、channel 状态和 Gateway/listener 共同退出生命周期。

## 根因

`FeishuWorkerRuntime` 使用 `multiprocessing` 的 `spawn` 上下文。子进程反序列化 `personal_assistant.channels.feishu.worker` 中的 bootstrap target 前，Python 必须先初始化 `personal_assistant.channels.feishu` 包；包级 `__init__.py` 当前立即 re-export `FeishuAdapter` 和 `FeishuClient`，因而继续加载 `adapter.py`、`client.py` 以及 `client.py` 顶层的完整 `lark_oapi`。这批重依赖实际发生在 `worker.py` 的 `ready_event.set()` 之前，超过父进程约五秒的 worker-ready 等待后，父进程会终止仍在导入的子进程。

这违背了 feat-464 引入隔离 worker 时的原始意图：`_default_worker_target()` 特意在函数体内延迟导入 SDK worker，使进程 bootstrap 先完成、再进入 provider 实现。bugfix-496 随后要求 bootstrap 在 listener target 前建立 parent-sentinel watcher，保证父 Gateway 消失时 listener 同步退出。修复必须恢复该既有 seam，同时保留 parent-liveness watcher、正常 stop/join、worker crash 上报、IPC 顺序和真实飞书消息路径。

问题能长期存在，是因为包级 re-export 没有被当作 spawn 启动成本的一部分验证；现有多数 worker 测试又通过测试专用包装把 ready 等待延长到 30 秒，未固定“只导入 worker 不应加载 Feishu SDK”的架构契约。因此真实验收是否暴露问题取决于当次冷导入能否撞进较短的生产门限。

## 修复

恢复 Feishu worker 的轻量 spawn seam，不改生产 timeout。`personal_assistant.channels.feishu` 包不再 eager re-export adapter/client；Gateway 的静态与托管 Feishu 调用方改为只在实际构造 provider runtime 时导入现有正式 `FeishuAdapter` 子模块。这样 macOS spawn 重执行 `personal_assistant.main` 并解析 worker bootstrap target 时，不会先加载 `client.py` 与 `lark_oapi`，worker 能先建立 parent-sentinel watcher、设置 `ready_event`，再进入既有 provider target。

修复没有增加 lazy compatibility shim 或新抽象，也没有修改 `worker.py`、`client.py`、五秒 worker-ready budget、测试专用 wrapper、parent watcher、正常 stop/join、crash status、IPC 顺序或消息投递语义。

实现 commits: `03319c87a789e7d8f93cb677f93540fbc9a9537d`、`045373db0b07dcea18a0b44602965501822d1f89`。

## 验证

- 新增 fresh interpreter contracts：隔离导入 `personal_assistant.channels.feishu.worker` 与 spawn 重执行入口 `personal_assistant.main` 均不得加载 `feishu.client` / `lark_oapi`。两层 deterministic red 分别暴露 package re-export 与 Gateway 顶层 adapter import；最终 startup 文件 `3 passed in 1.91s`。
- 新增真实 `multiprocessing.get_context("spawn")` 回归，使用未包装的 `FeishuWorkerRuntime.start()` 生产默认 ready budget，验证事件发布、worker 存活与 stop/reap；不复用现有 30 秒测试 wrapper。
- 最终 Feishu/Gateway/lifecycle focused suite `167 passed in 15.19s`；完整 non-E2E `3195 passed, 20 warnings in 51.67s`。`ruff check .`、touched Python focused format、`git diff --check` 与 `docs-check` 通过。
- 专用非 default Feishu E2E profile 完成两轮无预热 clean start。最终真实 user → Bot → Gateway 旅程新增一条 user 入站、两个正常完成的可见 assistant 气泡；Lark 为 `user=1, app=2`，内部 IM 为唯一 external conversation、唯一 user shadow、两个 completed agent bubbles、零 failed bubble 与唯一 saga。两轮均无初始化/crash 标记，且配对下线后进程、端口、listener lock 和敏感 runtime 文件均已清理。
- 全仓 `ruff format --check .` 仍只报告 dispatch base 已有的四个 eval 路径；本 milestone 未修改这些文件，相对 `origin/unit/bugfix-533` diff 为 0，最终 main sync 前需重判。具体路径与 live 取证见 `M1-fix/progress.md` 和 `M1-fix/evidence/cold-start-live-validation.md`。
