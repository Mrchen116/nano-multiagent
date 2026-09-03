# feat-542 — 验收报告

> 对齐: `spec.md` 的验收标准

> Validation snapshot: `dd6a4d58fc4545e498e26ae9ef1d833d005df396 → 427b5dcbf`

> Review round: 1（full revalidation）

## Verdict

**pass**

**Highest Required Action:** `pass`

Issue counts: blocking 0 / major 0 / minor 0。

在当前登录的 macOS GUI domain 中，隔离 Gateway 的默认开启、显式开启、显式关闭、
崩溃恢复、人工暂停、下一登录加载、配置应用时机、环境优先级和三条失败语义均从真实
CLI / `launchctl` / 隔离 IM 节点接口得到预期结果。验收未访问或修改生产 Gateway 配置，
IM 仅作为隔离测试依赖。

## 用户旅程体验

### Journey 1 — 默认开启、显式开启与配置应用边界

1. 从无 `gateway:` 段的隔离 config 启动已停止 Gateway。CLI 在约 1.6 秒内返回：
   `Gateway started (pid=63799)`、`Autostart: enabled (macOS login and crash recovery)`、
   `IM service: http://127.0.0.1:60761 [connected]`。
2. `launchctl print gui/501/<derived-label>` 显示 job `state = running`、`pid = 63799`；
   stable plist 有 `KeepAlive=true`、`ExitTimeOut=5` 和 unit worktree 的绝对路径，只含
   `PYTHONPATH`，不含配置环境值及本次 `--auto-bind` / `--im-service-url`。
3. 运行中加入显式 `autostart: true` 和环境配置但不 restart，再执行裸启动。CLI 返回
   `gateway is already running (pid=63799)`、退出 1，并指引 `stop` / `restart`；前后 state
   PID 都是 63799，没有替换实例，也没有显示新配置已应用。
4. 在已停止状态用显式 `autostart: true` 启动，CLI 返回
   `Gateway started (pid=64815)` 与 `Autostart: enabled ...`，IM 为 connected。

### Journey 2 — 系统监督、人工暂停与下一登录恢复

1. 对受管 PID 64815 发送 `SIGKILL`。约 1.2 秒内 state 变为新的 live PID 65073，隔离
   IM 中节点恢复 `online`，无需再次执行 Gateway 命令。
2. 执行产品 `stop`，CLI 返回 `STOPPED service=<derived-label>`、退出 0。等待 2 秒后旧
   PID 已退出、job 未 loaded、state 已清理，但 stable plist 仍在，未被 `KeepAlive`
   立即拉起。
3. 按 design Runbook 用 retained stable plist 执行一次 `launchctl bootstrap`，模拟下一
   登录会话加载。约 1.4 秒内出现 PID 65534，节点重新 `online`。新的 live command 只有
   `--config ... --foreground`，不再带上一会话的 `--auto-bind` 或
   `--im-service-url`。

### Journey 3 — 长期关闭及关闭失败的 fail-closed 语义

1. 把隔离 config 改为 `autostart: false`，并只对本轮 stable plist 设置可逆 immutable
   flag，模拟持久定义无法删除。`restart` 返回
   `ERROR [Errno 1] Operation not permitted: '<isolated-plist>'`、退出 1；没有
   `Autostart: disabled`，job 已卸载，plist 和失败证据仍在，没有 state 或替代 Gateway。
2. 清除该测试 flag 后再次启动。CLI 返回 `Gateway started (pid=66017)`、
   `Autostart: disabled (detached background process)`、IM connected；label 未 loaded，
   stable plist 不存在，只有一个 detached Gateway。因此后续登录没有可加载的该 config
   持久定义。

### Journey 4 — 应用失败降级与人工 stop 失败

1. 对本轮专属 label 暂时执行 `launchctl disable`，制造真实 bootstrap 失败。裸启动返回
   1，同时明确显示：

   ```text
   ERROR Gateway is running, but macOS login autostart failed: bootstrap Gateway LaunchAgent failed: ...
   Gateway started (pid=66115)
   Autostart:       failed (Gateway is running in detached mode)
   IM service:      http://127.0.0.1:60761  [connected]
   ```

   失败后只有一个 live detached PID，job 未 loaded，stable plist 已回滚删除；随后已把
   该 label 恢复为 enabled。
2. 恢复正常 managed Gateway 后，用 macOS sandbox 仅拒绝产品执行 `/bin/launchctl`，模拟
   当前登录服务无法 bootout。`stop` 返回
   `ERROR [Errno 1] Operation not permitted: '/bin/launchctl'`、退出 1；前后 PID 均为
   66527，进程仍 live、job 仍 loaded，没有 `STOPPED` 或替代实例。

### Journey 5 — 稳定环境与显式 CLI 的优先级

1. 使用两个全新 config / node，均令 inherited
   `NANO_MULTIAGENT_AUTO_BIND=0`、YAML `NANO_MULTIAGENT_AUTO_BIND="1"`，不传
   `--auto-bind`。managed config 返回 enabled、PID 66967，detached config 返回
   disabled、PID 67073；两个新节点都自动出现在隔离用户节点列表且为 `online`，证明两种
   后台模式都应用 YAML，且 YAML 覆盖同名 inherited environment。
2. 第三个全新 config 令 YAML `NANO_MULTIAGENT_AUTO_BIND="0"`，显式传
   `--auto-bind --im-service-url ...`。CLI 返回 enabled、PID 67309，新节点自动绑定并
   `online`，证明显式 CLI control 覆盖 YAML。stable plist 不含上述 CLI 参数、IM URL、
   auto-bind 值或本轮 marker；启动反馈也没有显示环境值。
3. 独立运行仓库登记的真 LaunchAgent critical path：
   `1 passed in 18.49s`。该结果只作重复性辅助证据，不替代以上真实产品输出。

纳入判定的 CLI 启停均在约 0.4–1.9 秒内完成；未观察到假死或重复实例。

## Reference Artifacts Reviewed

N/A。本 unit 没有原型、视觉稿、reference screenshot 或 must-match 视觉契约。

## 问题清单

无。

## 验收标准覆盖

### Requirement: 用户通过本地配置选择 Gateway 是否登录自启 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 缺省配置默认开启自启 | `spec.md` 对应 Scenario | Journey 1：无 `gateway:` 段时从停止态裸启动 | PID 63799；CLI `Autostart: enabled`；job running；节点 online | pass | 当前用户 GUI domain，非生产 config |
| 显式开启自启 | `spec.md` 对应 Scenario | Journey 1：显式 `autostart: true` 后从停止态启动 | PID 64815；CLI enabled；IM connected | pass | 启动时 config 显式为 true |
| 显式关闭自启 | `spec.md` 对应 Scenario | Journey 3：`autostart: false` 后启动 | PID 66017；CLI disabled；job/plist 均不存在 | pass | 当前以 detached 运行；后续登录无定义可加载 |
| 关闭自启无法应用时不虚报成功 | `spec.md` 对应 Scenario | Journey 3：只对隔离 plist 注入删除失败 | CLI exit 1；无 disabled；无 live replacement；plist 保留 | pass | 测试 flag 已恢复 |
| 编辑配置后尚未重新启停 | `spec.md` 对应 Scenario | Journey 1：运行中改配置，未 restart | live PID 始终为 63799；运行方式未变 | pass | 裸启动没有应用新配置 |
| 运行中裸启动不替换实例 | `spec.md` 对应 Scenario | Journey 1：对运行中同 config 再次裸启动 | `already running (pid=63799)`；exit 1；前后 PID 相同；有 restart 指引 | pass | 未显示配置已应用 |

### Requirement: Gateway 的稳定运行环境由本地配置拥有 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 普通后台与登录自启使用同一环境 | `spec.md` 对应 Scenario；`design.md` 决策 1/6 | Journey 5：managed 与 detached 均以 YAML auto-bind=1 对抗 inherited=0；第三 config 以显式 flag 对抗 YAML=0 | 两种模式的新节点均自动绑定并 online；显式 CLI config 也 online；stable plist/反馈无环境值或临时参数 | pass | 使用无秘密测试值；未检查或显示生产环境 |

### Requirement: 开启后 Gateway 由系统持续保持在线 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户登录后自动上线 | `spec.md` 对应 Scenario；`design.md` Runbook | Journey 2：人工 stop 后以 retained stable plist bootstrap，模拟下一登录加载 | bootstrap exit 0；PID 65534；节点 online；无需 Gateway start 命令 | pass | 按 Runbook 等价模拟，没有真的注销当前开发者会话 |
| 意外退出后自动恢复 | `spec.md` 对应 Scenario | Journey 2：对 managed PID 发 `SIGKILL` | PID 64815 → 65073；新 PID live；节点恢复 online | pass | 无人工 Gateway 命令 |

### Requirement: 人工停止与长期自启意图互不混淆 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 人工停止不被立即拉起 | `spec.md` 对应 Scenario | Journey 2：产品 `stop` 后观察 2 秒 | `STOPPED service=...`；旧 PID dead；job unloaded；state absent；plist present | pass | 当前登录保持停止 |
| 人工停止无法卸载登录服务时不虚报成功 | `spec.md` 对应 Scenario | Journey 4：仅拒绝 `/bin/launchctl` 执行 | CLI exit 1；无 STOPPED；PID 66527 未变且 live；job loaded | pass | 没有单独终止进程或起 replacement |
| 临时停止后下次登录恢复 | `spec.md` 对应 Scenario；`design.md` Runbook | Journey 2：stop 后 bootstrap retained plist | 新 PID 65534；节点 online | pass | 与“用户登录后自动上线”共用同一真 launchd 证据 |

### Requirement: 自启应用失败时保持当前可用并如实反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 开启自启失败后降级运行 | `spec.md` 对应 Scenario | Journey 4：仅 disable 本轮 label 后真实 bootstrap 失败 | CLI 同时显示 Gateway running + autostart failed + 原始 bootstrap 错误；exit 1；PID 66115 live detached；job/plist absent | pass | label 已恢复 enabled；只有一个 Gateway |

## Side Findings

无。

## Cleanup

本轮创建的 4 个 config-scoped job 均已确认未 loaded，对应 stable plist 和隔离 config 已
移出活动位置；故障注入的 disabled label 已恢复 enabled。隔离 IM 已停止，端口 60761
无 listener，worktree 中不再有本轮 config、PID、state、credential 或 tmux session。

## 澄清记录

无。验收口径与 design Runbook 足以执行完整旅程。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 只改变 Gateway 的本机生命周期，
  不改变跨包拓扑或 IM 生命周期所有权。
- [x] `docs/specs/gateway/`（长青行为契约层）：**需要更新**。本 unit 已提供
  `specs/gateway/spec.md` 与 `specs/gateway/service-lifecycle.md` delta；当前 canonical
  index 仍为 7 项，需由 orchestrator §7.1 归并为验收后的 10 项行为契约。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。架构与开发约束未变。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**。本 unit 未改变文档体系。

README、Gateway / local-stack / prod-fleet / troubleshooting 运维说明已经呈现本次可观察
行为；reviewer 未修改这些文档。
