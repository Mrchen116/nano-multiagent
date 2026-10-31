# 实施与验证记录

## 基线与范围

- 2026-10-31：从生产基线 `4cea0166d70a604da6a7dcea9246d81e37b1e1bb` 创建独立 worktree，随后以 fast-forward 集成已提交 main，实施基线 `7c3fba7fddfb11eb27fe18cc1029e661442529e9`。原主仓两个诊断 patch、报告和 `.pnpm-store` 保留。
- 用户明确只改后端；无前端交互、文案、只读规则变更。
- Gate 2 R3 Approved。以 change-orchestrator-simple 实施；独立 IM 协调器任务由 catalog_im_cache 完成，主 Agent 负责 integration/Node/Channels 和集成。后续修复主 Agent 直接处理。

## 已执行证据（实施中，非最终验收）

- 基线 `pnpm build` 通过，日志 `/tmp/refactor-682-baseline-build.log`。
- 基线 agent-settings/node-rpc/native capabilities 三文件 27 tests 通过，`/tmp/refactor-682-baseline-tests.log`。
- native preview 残留红测：3 次 catalog 在执行 home 留下 3 个 preview 目录及 lock/jsonl 文件，`/tmp/refactor-682-preview-red.log`。首次检查仅看顶层而未失败，纠正为 native sessions 下递归观察后真实复现；未把首次错误探针记为失败证据。
- 移出临时执行后该回归及原 empty tools/Skill/preview/apply 行为 2 tests 通过，`/tmp/refactor-682-inspector-first-tests.log`。尚未代表全部 native 保真通过。
- IM 新行为红测 `/tmp/refactor-682-im-red.log`；最终 focused catalog-reads/node-rpc/agent-settings/control/onboarding 共 78 tests 通过，`/tmp/refactor-682-im-tests.log`。含 30 并发共享、读不占写锁、旧代次不写 snapshot、pending recovery 不阻塞读。IM contracts typecheck 通过。
- Channels expired/failed inspection response 红测 2 tests 失败，`/tmp/refactor-682-relay-red.log`。实现后的完整相关测试结果后续补记。
- daily 隔离栈基线成功启动并完成 seed；已执行 e2e-down，尚未用它证明新实现。日志 `/tmp/refactor-682-e2e-baseline.log`、`/tmp/refactor-682-e2e-baseline-down.log`。

## 现有覆盖处置

- keep：现有 native capabilities/personal-security/workspace plugin tests；通过默认 RuntimeClient reverse inspector 接线覆盖同一原生消费路径，不以 Node 不存在跳过。
- extend：capabilities.test.ts 增加真实 Session 持久化不变量；agent-settings/node-rpc/relay 追加对应公开 HTTP/协议/清理保护。
- new：IM CatalogReads 拥有新的 bounded cache/coordinator seam，单独测试失效/TTL/容量；native ConfigurationInspector 的进程所有权/故障恢复是不同 owner，拟使用独立行为测试。

仍需完成：真实挂起/超时/取消/崩溃恢复与 generation 竞态、100 次真实刷新与 30 分钟 soak、全量 CI、独立 code review/verifier/product acceptance、delta 归并、archive 和 PR。未部署、未发布。

### 首轮集成修正

- 5 项真实 inspector 测试通过：30 waiter 合并/单 waiter 取消、同步死循环插件硬超时及后续恢复（聊天 PID 不变）、generation 取消、强杀 owner 后接管仍活 worker、PID 标识不符保留并拒绝新工作。`/tmp/refactor-682-inspector-tests.log`。
- daily 初始化发现 `prepareProfile` 的 JSON 被原生 settings 改写为 YAML；reverse inspector 改用已有 js-yaml 读取后，model-setup/providers 5 tests 通过，`/tmp/refactor-682-model-regression.log`。
- daily PA 配置 patch 暴露初始 workspace 挂载也触发 catalog change，取消在途 prepare。区分初次挂载与真实 mutation/file refresh；初次仅刷新 tool selection。修正后 daily seed 完整 ready，`/tmp/refactor-682-e2e-current.log`。
- 原 workspace-tools test 发现冷 preset 的异步 Nano composition 尚未结束即投影目录：临时诊断观察 mount.tools 有 workspace_echo，但 catalog 投影时 installed 为空且早于 mount 完成。ConfigurationScopes 明确持有自身 attach readiness，preview 投影前等待；未依赖私有 DSH exports、睡眠或扩大 deadline。诊断代码已移除。原 workspace-tools 与 capabilities 共 6 tests 通过，`/tmp/refactor-682-native-presets.log`。
- 配置 apply 的条件轮询预算按新增冷检查上限调整为 8 秒；仍断言忙会话的撤销即时在当前回合结束前生效，没有把等待当前回合结束视为成功。
- 本地 Python 113 passed / 28 e2e deselected，ruff check/format 通过；`/tmp/refactor-682-pytest.log`、`/tmp/refactor-682-ruff.log`。首轮全量 native 被具体失败中止，不能记为通过；修正后再跑。

### 独立审查修正（待冻结/复验）

- Round 1 head `0812c67ef` 独立审查报告提交 `516c2b6f4`，两项 confirmed P1：startup cleanup_error 误阻断整个 Node；退出 leader 后未回收仍活同组 child。
- 修复让 Node 记录 inspector 初始化错误后继续启动，inspector 保留 cleanup_error 拒绝新检查；回收对整个拥有的进程组 TERM→宽限→KILL并确认无非zombie成员，之后才删 home/释放名额。startup 若 leader 已死但组仍有活成员且无法确认随机身份，保留并拒绝检查，不能误删。
- `/tmp/refactor-682-startup-check.py` 使用本轮 daily 实例+独立 sleeper PID 制造 identity mismatch：Node online、settings ready=false/read_failed、cron section source=current、未知进程和目录仍在；停止后删自建残留并重启恢复。结果 `/tmp/refactor-682-startup.json`，日志 `/tmp/refactor-682-startup-recovery.log`。未接触生产或发送模型消息。
- 新真实 native 子进程回归与 ordinary selected preview 对照已通过（`/tmp/refactor-682-fix-tests.log` 中 inspector/capabilities 两文件；同轮新 PA/workspace断言另有fixture问题，不把整轮记为绿）。PA 比较实际section正文而非渲染后不存在的section名称。workspace完整候选需关闭没有对应所选工具/Skill的Features，不能把原始不完整fixture当有效preview输入。
- workspace预览补测还复现重复文件watch误触发generation，造成无实际mutation时取消新检查：把generation通知收敛到原生plugin mutation完成，普通挂载/重复watch只刷新实际tool selection；外部文件变化按既定TTL有界。
- 历史preview迁移隔离副本 `/tmp/refactor-682-migration-check.mjs` 使用锁定DSH真实v4压缩header，选择2项，保留普通Session、真实binding、伪造名、header不符及损坏头共5项；rename后/ledger前中断恢复、二次重跑、移回后的字节hash均通过。结果 `/tmp/refactor-682-migration.json`；自建副本已删除。
- 首次高并发全量与100刷新/soak同时运行造成多项native deadline/测试失败，已停止本轮并保留日志 `/tmp/refactor-682-full-tests-r2.log`、`/tmp/refactor-682-refresh100.log`、`/tmp/refactor-682-soak-progress.json`；不是有效长时验收。后续本地全量用 `--maxWorkers=2`，性能采样单独运行。
