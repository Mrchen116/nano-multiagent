# Verification Report: feat-542

> Validation snapshot: `dd6a4d58fc4545e498e26ae9ef1d833d005df396 → 427b5dcbf546aff40c1d208e4e96c97cea0b5317`

## Summary

- Mode: `full`
- Delta range: N/A
- Focus issues: N/A
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone; 5/5 requirements |
| Correctness | 13/13 scenarios covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: unit 没有 `tasks.md` / `progress.md`；按 design 的单一 milestone 退出标准、实际 diff 和 evidence 重建核对，`feat-542-M1` 为 1/1 完成。
- Spec 覆盖：5 条 requirement 均有实现；13 个场景均能追到产品代码与持久回归测试。
- Delta-spec：3 个 ADDED Requirement 与 1 个 MODIFIED lifecycle Requirement 均与实现一致；MODIFIED 段保留了原有单实例、状态、关停顺序和首因保留契约。
- 实现范围完整：typed config（`src/personal_assistant/config/local_store.py:293-309,1011-1024,1535-1579`）、唯一 lifecycle policy（`src/personal_assistant/gateway/process_lifecycle.py:182-260`）、具体 macOS owner（`src/personal_assistant/gateway/macos_launch_agent.py:22-153`）、CLI 反馈（`src/personal_assistant/main.py:26-41,99-150`）、操作文档和部署 skill 均在 diff 中。
- 真实常驻路径已登记为 v1 必保活（`docs/development/e2e-critical-paths.md:30-54`）；提交内 evidence 记录真 launchd 验证和清理边界（`docs/changes/feat-542-gateway-autostart/M1-macos-gateway-autostart/evidence/implementation.md:24-64`）。
- 本轮独立复验：
  - 聚焦 Gateway 回归：`65 passed in 1.59s`。
  - 依赖方向与测试命名/大小 contract：`7 passed in 1.11s`。
  - 真 macOS LaunchAgent 旅程：`1 passed in 19.75s`。
  - `docs-check`：219 份 maintained Markdown / 70 条 required routes 通过。
  - 受影响 Python 文件 Ruff check 与 format check 通过；`git diff --check` 无输出。
- Prototype / Reference 覆盖：N/A；design 无前端原型或 reference artifact。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| R1 / 缺省配置默认开启自启 | `src/personal_assistant/config/local_store.py:305-309,1551-1566`; `src/personal_assistant/gateway/process_lifecycle.py:229-260` | `tests/unit/personal_assistant/config/test_gateway_lifecycle_config.py:45-55`; `tests/unit/personal_assistant/test_gateway_autostart.py:30-57`; 真 E2E `tests/e2e/critical_paths/test_gateway_autostart_critical_path.py:18-51` | covered |
| R1 / 显式开启自启 | `src/personal_assistant/config/local_store.py:1551-1566`; `src/personal_assistant/gateway/process_lifecycle.py:244-260` | `tests/unit/personal_assistant/test_gateway_autostart.py:30-57` 以显式 `autostart=True` 驱动 managed 路径 | covered |
| R1 / 显式关闭自启 | `src/personal_assistant/gateway/process_lifecycle.py:244-253`; `src/personal_assistant/gateway/macos_launch_agent.py:135-153` | 真 E2E `scripts/e2e-gateway-autostart.sh:169-190`; config round-trip `tests/unit/personal_assistant/config/test_gateway_lifecycle_config.py:58-78` | covered |
| R1 / 关闭自启无法应用时不虚报 | `src/personal_assistant/gateway/process_lifecycle.py:244-253`; `src/personal_assistant/gateway/macos_launch_agent.py:135-153` | `tests/unit/personal_assistant/test_gateway_autostart.py:158-175`; `tests/unit/personal_assistant/test_macos_launch_agent.py:129-150` | covered |
| R1 / 仅编辑配置不改变当前模式 | 配置只在 CLI 启动路径加载（`src/personal_assistant/main.py:99-135`），无 watcher/reconcile 路径 | 运行实例仍由同一 state 拒绝替换：`tests/unit/personal_assistant/test_gateway_pid_lifecycle.py:214-245` | covered |
| R1 / 运行中裸启动不替换实例 | `src/personal_assistant/gateway/process_lifecycle.py:263-289` | `tests/unit/personal_assistant/test_gateway_pid_lifecycle.py:214-245`; CLI error handling `tests/unit/personal_assistant/test_gateway_main_command.py:236-256` | covered |
| R2 / 普通后台与登录自启使用同一环境，优先级为 CLI > YAML > inherited | `src/personal_assistant/gateway/process_lifecycle.py:124-158,362-414`; stable plist 仅含 `PYTHONPATH`：`src/personal_assistant/gateway/macos_launch_agent.py:180-212` | `tests/unit/personal_assistant/test_gateway_autostart.py:178-216`; `tests/unit/personal_assistant/test_macos_launch_agent.py:65-99`; `tests/unit/personal_assistant/test_auto_bind.py:76-107` | covered |
| R3 / 用户登录后自动上线 | 稳定 plist + `KeepAlive`：`src/personal_assistant/gateway/macos_launch_agent.py:180-212` | 真 E2E 重新 bootstrap 留存定义并等待 node online：`scripts/e2e-gateway-autostart.sh:154-165` | covered |
| R3 / 意外退出后自动恢复 | launchd 直接监督 foreground + `KeepAlive`：`src/personal_assistant/gateway/macos_launch_agent.py:190-212` | 真 E2E `SIGKILL` 后核对新 PID、loaded job 和 online：`scripts/e2e-gateway-autostart.sh:148-152` | covered |
| R4 / 人工停止当前登录不立即拉起 | `src/personal_assistant/gateway/process_lifecycle.py:475-541`; `src/personal_assistant/gateway/macos_launch_agent.py:104-132` | `tests/unit/personal_assistant/test_gateway_autostart.py:219-255`; 真 E2E `scripts/e2e-gateway-autostart.sh:154-160` | covered |
| R4 / 停止登录服务失败时非零且不再 signal | bootout 在读 state/发 signal 前完成：`src/personal_assistant/gateway/process_lifecycle.py:482-490,525-541` | `tests/unit/personal_assistant/test_gateway_autostart.py:257-278`; CLI 统一异常返回 1：`tests/unit/personal_assistant/test_gateway_main_command.py:222-233` | covered |
| R4 / 临时停止后下次登录恢复 | `stop_current_login` 不删 plist：`src/personal_assistant/gateway/macos_launch_agent.py:104-132`; 只有 permanent remove 才删：`:135-153` | 真 E2E 核对 plist 保留后重新 bootstrap：`scripts/e2e-gateway-autostart.sh:154-165` | covered |
| R5 / 开启自启失败后安全回滚、单一 detached 降级且 CLI 非零 | `src/personal_assistant/gateway/process_lifecycle.py:292-340,343-359`; `src/personal_assistant/main.py:116-143` | `tests/unit/personal_assistant/test_gateway_autostart.py:88-156`; `tests/unit/personal_assistant/test_gateway_autostart_cli.py:69-88` | covered |

### MODIFIED lifecycle requirement 保留核对

- 默认后台启动、PID/process-birth 确认、readiness 边界：`src/personal_assistant/gateway/process_lifecycle.py:182-215,292-340,362-414,893-938`，由 `tests/unit/personal_assistant/test_gateway_launch.py:58-172` 和真 E2E 覆盖。
- 重复启动拒绝与 config-scoped 串行：`src/personal_assistant/gateway/process_lifecycle.py:207-215,263-289,438-472,596-608`；重复实例回归见 `tests/unit/personal_assistant/test_gateway_pid_lifecycle.py:214-245`，CLI restart 接线见 `tests/unit/personal_assistant/test_gateway_main_command.py:331-366`。
- stop 优雅退出、超时 SIGKILL 与进程身份安全：`src/personal_assistant/gateway/process_lifecycle.py:475-563,730-807`，由 `tests/unit/personal_assistant/test_gateway_pid_lifecycle.py:288-450` 及本 unit 的 managed stop 测试继续覆盖。
- 关停时生产者先 seal、内核与投递 drain、IM/resource 后关，以及关停次要错误不覆盖首因：本 unit 未修改 runtime owner，既有 `tests/unit/personal_assistant/test_gateway_shutdown_resource_graph.py:139-222`、`tests/unit/personal_assistant/test_gateway_shutdown_timeout_isolation.py:170-229` 和 `tests/unit/personal_assistant/test_gateway_runtime_lifecycle.py:211-273` 在提交记录的全量 non-E2E 套件中继续通过。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1: YAML 拥有 `autostart` 与稳定 environment，CLI > YAML > inherited | 是 | `src/personal_assistant/config/local_store.py:293-309,1011-1024,1535-1579`; `src/personal_assistant/gateway/process_lifecycle.py:124-151` |
| D2: launchd 直接监督前台 Gateway | 是 | `src/personal_assistant/gateway/macos_launch_agent.py:180-212` 的绝对 Python + `--foreground` + `KeepAlive` |
| D3: lifecycle policy 留在 `process_lifecycle`，macOS 机制单独收口 | 是 | policy 在 `src/personal_assistant/gateway/process_lifecycle.py:218-260`；concrete OS 操作在 `src/personal_assistant/gateway/macos_launch_agent.py:34-177`；CLI 只消费 result（`src/personal_assistant/main.py:26-41`） |
| D4: 裸 start 拒绝替换，只有 restart 执行 stop + apply + start | 是 | `src/personal_assistant/gateway/process_lifecycle.py:263-289,438-472` |
| D5: stop 只暂停当前登录，false 才永久移除 | 是 | `src/personal_assistant/gateway/macos_launch_agent.py:104-153`; `src/personal_assistant/gateway/process_lifecycle.py:244-253,475-541` |
| D6: resolved config 派生稳定 label/plist，临时 CLI control 只进当次 bootstrap | 是 | `src/personal_assistant/gateway/macos_launch_agent.py:22-31,59-101,180-212` |
| D7: apply 失败先回滚并证明安全，再单实例 detached 降级且非零反馈 | 是 | `src/personal_assistant/gateway/process_lifecycle.py:292-359`; `src/personal_assistant/main.py:116-143` |

架构自洽性通过：改动局限于 `personal_assistant` 产品与运维/验收资产，没有让 IM 或 LLM/SearXNG 接管 Gateway 生命周期，没有新建跨平台 ServiceManager/noop adapter，也没有违反 `personal_assistant → agent.sdk` 依赖边界。相关 contract 本轮 7/7 通过。

### Prototype / Reference Contract

N/A — design 不含前端原型或 reference artifact。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

- 实现 commit `427b5dcbf` 使用 `feat(gateway): ...` scope，而仓库约定 scope 应使用 unit id，milestone 级可写成 `feat(feat-542/M1): ...`（`docs/development/local-development.md:98-106`）。这不影响产品正确性或可追溯性；后续 unit commit 应按该格式生成。

# Round 2

## Verification Report: feat-542

> Validation snapshot: `dd6a4d58fc4545e498e26ae9ef1d833d005df396 → a85870eedd32d42a22208ab35fdf28d6a57b3188`

### Summary

- Mode: `full`
- Delta range: `2f518ffabc6f728d1adbded2d9f186d09c45266e..a85870eedd32d42a22208ab35fdf28d6a57b3188`
- Focus issues: code review 的 8 条 confirmed finding
- requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone; 5/5 requirements; 8/8 review findings closed |
| Correctness | 13/13 scenarios covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- `feat-542-M1` 的实现、测试、运维说明、部署 skill、delta-spec 与持久 evidence 均存在；没有 `tasks.md` / `progress.md`，继续按 design 的单一 milestone 退出标准重建核对，完成度为 1/1。
- 首文档 5 条 requirement、13 个 scenario 均有最终产品代码和持久测试映射；delta-spec 的 3 个 ADDED Requirement 与 1 个 MODIFIED Requirement 仍与最终实现一致。
- `ac6e8e6f0` 触及的 8 条 code-review finding 均关闭；新增的 macOS baseline `PATH` 已同时进入 design、unit delta-spec、运维文档、plist 实现和测试。
- 本轮独立复验：聚焦回归 `70 passed in 0.96s`；`personal_assistant` 全包 `1138 passed, 1 warning in 26.05s`；全部 contract `156 passed in 6.72s`；真 macOS LaunchAgent critical path `1 passed in 18.23s`；文档完整性检查通过（222 份 maintained Markdown / 70 条 required routes）；受影响 Python 文件 Ruff check、format check 及 `git diff --check` 通过。
- Prototype / Reference 覆盖：N/A；design 不含前端原型或 reference artifact。

### Code-review closure

| Finding | 最终实现与持久测试证据 | 状态 |
|---|---|---|
| bootout 成功但无 state 时不能证明 managed child 已退出 | `macos_launch_agent.py:126-139` 使用 `/bin/launchctl bootout --wait` 后再确认 unloaded；`test_macos_launch_agent.py:119-130` 与真 LaunchAgent stop/disable 旅程通过 | closed |
| 单次 `--im-service-url` 可能被后续配置同步写回 YAML | `local_store.py:439-458,1060-1078` 分离 runtime URL 与持久 IM snapshot；`test_gateway_lifecycle_config.py:106-137` 证明后续持久化仍保留稳定 URL | closed |
| 配置 PATH 可能遮蔽生命周期 owner 使用的 `ps` | `process_lifecycle.py:647-669` 固定使用 `/bin/ps`；`test_gateway_autostart.py:251-275` 覆盖自定义 PATH 下的前台 state 发布 | closed |
| LaunchAgent loaded 但尚未写 state 时裸 start 可能替换服务 | `process_lifecycle.py:287-297` 在 macOS 额外核对 loaded job 并 fail closed；`test_gateway_autostart.py:97-119` 覆盖 state publication 前窗口 | closed |
| default-on LaunchAgent 丢失 Homebrew 常用 PATH | `macos_launch_agent.py:18,212-219` 固定系统目录与两种 Homebrew 常用目录；unit plist 与真 E2E stable plist 均核对精确值 | closed |
| E2E timeout 可能中断 shell trap 并遗留 launchd job/plist | `test_gateway_autostart_critical_path.py:18-54,60-85` 将 launchd 与 runtime cleanup 放进 pytest `finally`，各自有独立 30 秒边界；真 E2E 通过且清理完成 | closed |
| 部署 skill 的独立片段复用未定义 `prod_worktree` | `.claude/skills/prod-fleet-deploy/SKILL.md:172-176,207-211` 在两个独立片段中分别解析并校验目标 worktree | closed |
| `gateway.environment` 接受 `os.environ` 拒绝的名称/值 | `local_store.py:1576-1586` 拒绝 key 中 `=` / NUL 及 value 中 NUL；`test_gateway_lifecycle_config.py:140-163` 有永久回归 | closed |

## Correctness

| Requirement / Scenario | 最终实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| R1 / 缺省配置默认开启自启 | `local_store.py:293-306,1554-1589`; `process_lifecycle.py:218-260` | config default、managed launch unit test、真 E2E | covered |
| R1 / 显式开启自启 | `local_store.py:1569-1589`; `process_lifecycle.py:244-260` | managed launch unit test、真 E2E | covered |
| R1 / 显式关闭自启 | `process_lifecycle.py:244-258`; `macos_launch_agent.py:143-161` | config round-trip、disable unit/真 E2E | covered |
| R1 / 关闭自启无法应用时不虚报 | `process_lifecycle.py:244-253`; `macos_launch_agent.py:143-161` | permanent-remove failure 与 disable fail-closed tests | covered |
| R1 / 仅编辑配置不改变当前模式 | 配置仅在有效 start/restart 加载；无 watcher/reconcile 路径 | existing-live 与 loaded-before-state 两类重复启动回归 | covered |
| R1 / 运行中裸启动不替换实例 | `process_lifecycle.py:263-297` | PID live-state 与 loaded-job publication-window tests | covered |
| R2 / 两种后台模式共享环境，CLI > YAML > inherited，未配 PATH 有 macOS baseline | `process_lifecycle.py:124-158`; `macos_launch_agent.py:18,212-219` | environment precedence、custom PATH identity、stable plist unit/真 E2E | covered |
| R3 / 用户登录后自动上线 | stable plist、直接 foreground supervision、`KeepAlive`：`macos_launch_agent.py:188-222` | 真 E2E retained-plist bootstrap 后 node online | covered |
| R3 / 意外退出后自动恢复 | `macos_launch_agent.py:188-222` | 真 E2E `SIGKILL` 后新 PID 与 node online | covered |
| R4 / 人工停止当前登录不立即拉起 | `process_lifecycle.py:482-548`; `macos_launch_agent.py:126-139` | managed stop unit test、真 E2E | covered |
| R4 / 停止登录服务失败时非零且不再 signal | `process_lifecycle.py:489-497,532-548` | bootout failure fail-closed test、CLI exception contract | covered |
| R4 / 临时停止后下次登录恢复 | `stop_current_login` 不删 stable plist，只有 permanent remove 删除：`macos_launch_agent.py:126-161` | 真 E2E stop 后 retained-plist bootstrap | covered |
| R5 / 开启自启失败后安全回滚、单一 detached 降级且 CLI 非零 | `process_lifecycle.py:299-366`; `main.py:99-143` | apply/rollback/fallback unit tests、CLI result test、真故障旅程 evidence | covered |

### MODIFIED lifecycle requirement 保留核对

- 默认后台启动、PID/process-birth 确认、readiness 边界和 config-scoped lock 保持原契约；新增 loaded-job 检查只补齐 state publication 前的单实例窗口。
- stop/restart 仍先 bootout managed job，再按 PID + process-birth 安全收尾；`bootout --wait` 加强“受管 child 已退出”的证明，没有改变永久配置意图。
- runtime shutdown 的 producer seal、kernel/delivery drain、资源关闭顺序与首因保留代码不在本轮 delta 中；`personal_assistant` 全包 1138 项继续通过。

## Coherence

| design 决策 | 遵守? | 最终代码证据 |
|---|---|---|
| D1: YAML 拥有 autostart 与稳定 environment；CLI > YAML > inherited；LaunchAgent 提供固定 macOS baseline PATH | 是 | `local_store.py:293-306,1018-1031,1554-1589`; `process_lifecycle.py:124-158`; `macos_launch_agent.py:18,212-219` |
| D2: launchd 直接监督现有前台 Gateway | 是 | `macos_launch_agent.py:188-222` 的绝对 Python、`--foreground` 与 `KeepAlive` |
| D3: lifecycle policy 留在 `process_lifecycle`，macOS 机制单独收口 | 是 | policy 在 `process_lifecycle.py:218-366`；launchctl/plist 机制在 `macos_launch_agent.py` |
| D4: 裸 start 拒绝替换，只有 restart 替换实例 | 是 | `process_lifecycle.py:263-297,445-479`，并包含 loaded-before-state 窗口 |
| D5: stop 只暂停当前登录，配置 false 才永久移除 | 是 | `macos_launch_agent.py:126-161`; `process_lifecycle.py:244-253,482-548` |
| D6: resolved config 派生稳定 label/plist；临时 CLI control 不持久化 | 是 | `macos_launch_agent.py:22-31,64-109,188-222`; `local_store.py:439-458,1060-1078` |
| D7: apply 失败安全回滚后单实例 detached 降级且非零反馈 | 是 | `process_lifecycle.py:299-366`; `main.py:116-143` |

架构自洽性通过：最终 delta 仍局限于 `personal_assistant` 生命周期 owner、配置 owner 与运维/验收资产；未让 Gateway 管理远端 IM/LLM 生命周期，未增加跨平台 ServiceManager/noop adapter，也未违反 `personal_assistant → agent.sdk` 边界。全部 156 项 contract 通过。

### Prototype / Reference Contract

N/A — design 不含前端原型或 reference artifact。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

- Round 1 的非阻塞提交 scope 建议仍未变化：实现提交使用 `feat(gateway)` / `fix(gateway)`，而仓库 milestone 约定建议使用 unit id scope（`docs/development/local-development.md:98-106`）。历史提交不应为此改写；后续 unit 按约定命名即可。

## Corrected Delta Reconciliation

> Reconciled snapshot: `dd6a4d58fc4545e498e26ae9ef1d833d005df396 → 99f8a4281da1ce559c1da640830e72c0a1180d28`
>
> Verification mode: `corrected-delta`

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/spec.md` / Service Lifecycle Requirement count `10` | canonical 当前为 7；本 delta `ADDED 3 + MODIFIED 1 + REMOVED 0`，所以无损归并后为 10；MODIFIED 标题与 canonical 的 `运维者用启停命令把 Gateway 当后台服务管理` 精确匹配，3 个 ADDED 标题均不与现有 Requirement 冲突 | `scripts/docs_check.py` 对当前入口/delta 路由通过；本轮结构计数复核为 canonical 7、ADDED 3、MODIFIED 1、REMOVED 0 | aligned |
| `service-lifecycle.md` / ADDED `macOS Gateway 的登录自启意图和稳定运行环境由本地配置拥有` | typed config/default/save/validation：`src/personal_assistant/config/local_store.py:294-306,1018-1031,1553-1589`；模式选择与环境优先级：`src/personal_assistant/gateway/process_lifecycle.py:124-158,218-260` | `tests/unit/personal_assistant/config/test_gateway_lifecycle_config.py:46-163`; `tests/unit/personal_assistant/test_gateway_autostart.py:39-275` | aligned |
| 该 Requirement / Scenario `缺省配置默认开启登录自启` | `GatewayLifecycleConfig.autostart=True`，macOS 默认进入 managed path：`local_store.py:305`; `process_lifecycle.py:244-260` | config default test、`test_macos_default_start_uses_launch_agent`、真 LaunchAgent critical path | aligned |
| 该 Requirement / Scenario `显式开启登录自启` | YAML parser 保留显式 bool，managed path 应用 stable LaunchAgent：`local_store.py:1569-1589`; `process_lifecycle.py:244-260` | config round-trip、managed launch unit test、最终 head 真 E2E | aligned |
| 该 Requirement / Scenario `显式关闭登录自启` | `autostart=false` 先永久移除定义，再启动 detached：`process_lifecycle.py:244-258`; `macos_launch_agent.py:143-161` | disable-path unit tests；critical path 核对 job/plist 消失且 detached Gateway live | aligned |
| 该 Requirement / Scenario `登录自启关闭未完整应用时不虚报成功` | remove 抛错时不会越过到 detached launch：`process_lifecycle.py:244-253`; `macos_launch_agent.py:143-161` | `test_disable_failure_does_not_start_detached_replacement`; `test_permanently_remove_keeps_definition_when_bootout_fails` | aligned |
| 该 Requirement / Scenario `只编辑配置不改变当前运行方式` | 无 watcher/reconcile；仅有效 start/restart 加载并应用配置，裸 start 先拒绝 live state/loaded job：`process_lifecycle.py:182-215,263-297` | live PID 重复启动与 loaded-before-state 两类回归；acceptance Round 1 Journey 1 / Round 2 Journey C | aligned |
| 该 Requirement / Scenario `配置环境在两种后台模式中保持一致`（含 corrected baseline PATH） | `run_gateway()` 统一执行 inherited → YAML → 显式 auto-bind：`process_lifecycle.py:124-158`；stable plist 不复制 YAML 值，但提供 `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin` 与 `PYTHONPATH`：`macos_launch_agent.py:18,188-222`；显式 YAML `PATH` 在 runtime 覆盖 baseline | environment precedence 与 custom-PATH lifecycle tests；`test_apply_persists_stable_definition_but_bootstraps_transient_controls`; `scripts/e2e-gateway-autostart.sh:141-145`; acceptance Round 2 Journey D | aligned |
| `service-lifecycle.md` / ADDED `启用登录自启的 macOS Gateway 由系统保持运行` | stable LaunchAgent 直接监督 foreground Gateway，`KeepAlive=true`：`macos_launch_agent.py:188-222` | plist unit test、真 LaunchAgent critical path、acceptance Round 1/2 | aligned |
| 该 Requirement / Scenario `用户登录后自动运行` | stable plist 留在 `~/Library/LaunchAgents`，Program/argv/working directory 均为绝对稳定定义：`macos_launch_agent.py:22-31,188-222` | critical path 与 acceptance 均在 stop 后 bootstrap retained plist，观察新 PID 与 node online | aligned |
| 该 Requirement / Scenario `Gateway 意外退出后自动恢复` | launchd 直接监督 foreground child 且 `KeepAlive=true`：`macos_launch_agent.py:188-222` | critical path 对 child `SIGKILL` 后核对新 PID 和 node online | aligned |
| 该 Requirement / Scenario `人工停止只暂停当前登录会话` | `stop_current_login()` 用 `bootout --wait` 并保留 stable plist；只有 `permanently_remove()` 删除：`macos_launch_agent.py:110-161`; `process_lifecycle.py:482-548` | managed stop tests、async bootout test、critical path stop + retained-plist bootstrap | aligned |
| `service-lifecycle.md` / ADDED `登录自启应用失败时 Gateway 降级运行并如实失败` | apply/start failure 先 permanent rollback，确认安全后只起一个 detached Gateway，并保留原错误：`process_lifecycle.py:299-366`; CLI 打印 running + failed 且返回 1：`main.py:116-143` | rollback/fallback/fail-closed unit tests、CLI degraded-result test、acceptance Round 1 Journey 4 | aligned |
| 该 Requirement / Scenario `登录服务应用失败后降级为普通后台进程` | 同上；rollback 无法证明安全时直接失败，不会起第二实例 | `test_launch_agent_failure_rolls_back_then_runs_one_detached_gateway`; `test_launch_agent_rollback_failure_does_not_start_detached_gateway`; CLI test | aligned |
| `service-lifecycle.md` / MODIFIED `运维者用启停命令把 Gateway 当后台服务管理` | canonical 原 Requirement 的 PID/process-birth、lock、shutdown 顺序与首因契约全部保留；增量只把 macOS autostart 模式、managed stop 和反馈并入同一 lifecycle owner：`process_lifecycle.py:182-669`; `main.py:26-143` | `personal_assistant` 全包最终实现复验 `1138 passed`；全部 contract `156 passed` | aligned |
| 该 Requirement / Scenario `默认启动后台运行并尽快返回` | 非 macOS 仍 detached；macOS 按配置选 managed/detached，均等待 state 的 PID + birth 后返回结果：`process_lifecycle.py:182-260,299-414`; `main.py:26-41` | background launch、managed launch、non-mac output、CLI feedback tests；真 E2E | aligned |
| 该 Requirement / Scenario `重复启动被单实例锁拦下` | live state、legacy PID 与 loaded LaunchAgent 均 fail closed，给出 stop/restart 指引：`process_lifecycle.py:263-297` | PID live-state test、loaded-before-state test、CLI next-step test | aligned |
| 该 Requirement / Scenario `stop 终止 Gateway 并清理当前运行状态` | managed path 先 bootout，随后复用 process-birth waiter；detached path 保持原 stop/STALE/NOT RUNNING 语义：`process_lifecycle.py:424-442,482-570` | PID lifecycle stop tests、managed stop test、CLI stop/not-running/stale tests、真 E2E | aligned |
| 该 Requirement / Scenario `stop 无法停止登录服务时不越过失败` | bootout 在 state 读取和 signal 前执行；异常直接向 CLI 传播：`process_lifecycle.py:489-497,532-548` | `test_managed_stop_failure_does_not_signal_process`; acceptance Round 1 Journey 4 | aligned |
| 该 Requirement / Scenario `start stop restart 对同一 config 串行` | start/stop/restart 共用 resolved-config lifecycle lock，restart 一次持锁完成 stop + reload + start：`process_lifecycle.py:207,441,445-479,604-615` | `test_main_restart_command_uses_serialized_lifecycle_operation` 与既有 lifecycle tests | aligned |
| 该 Requirement / Scenario `stop 只向已证明的进程实例发信号` | 每次 signal 前核对 process birth；legacy state 通过绝对 `/bin/ps` command + config 归属收敛，身份变化 fail closed：`process_lifecycle.py:647-814` | `test_stop_gateway_rejects_legacy_pid_owned_by_another_command`; `test_stop_gateway_does_not_signal_reused_pid`; custom PATH regression | aligned |
| 该 Requirement / Scenario `stop 收拢活动运行后终止 Gateway` | runtime shutdown owner 未被本 unit 改写；managed/detached 最终都运行同一 foreground Gateway 和既有 shutdown graph | `test_shutdown_seals_then_closes_kernel_and_drains_one_deadline`; shutdown timeout isolation 与 runtime lifecycle tests | aligned |
| 该 Requirement / Scenario `真实故障在关闭后仍是主要错误` | 本 unit 未建立平行 runtime/shutdown owner；既有首因与 best-effort cleanup 路径继续由同一 runtime 实现 | shutdown resource graph、timeout isolation、IM cleanup exception regressions；全包 1138 项通过 | aligned |
| `service-lifecycle.md` / REMOVED Requirements | `无`；最终实现未删除 canonical 的其他 6 条 Service Lifecycle Requirement，也未删除 MODIFIED Requirement 的既有行为 | canonical 标题/场景结构对账；最终 unit diff 与全包测试 | aligned |

### Merge safety

- canonical `service-lifecycle.md` 当前有 7 条 Requirement；应用 3 条 ADDED、原位替换 1 条 MODIFIED、删除 0 条后为 10，与 unit `specs/gateway/spec.md` 的入口数字一致。
- MODIFIED Requirement 保留 canonical 的 7 个既有场景语义：两个场景仅改名以容纳 managed/detached 两种后台模式，另外 5 个标题保持；新增 `stop 无法停止登录服务时不越过失败`，没有吞掉原约束。
- 3 条 ADDED Requirement 名称均为新名称，适合直接插入 Service Lifecycle area；其他 canonical area 与 Requirement 数无需改动。

### Uncovered Observable Behavior

None. Review 后的产品代码变更均为既有 delta 行为的闭环：`bootout --wait`、loaded/no-state 检查与绝对 `/bin/ps` 分别加强 stop、单实例和身份安全；瞬时 IM URL 防回写落实“本次显式控制”不成为稳定配置；环境非法值校验落实 OS environment 可用性；E2E cleanup 与部署 skill 变量修复不新增 Gateway 产品行为。固定 macOS baseline `PATH` 已明确写入 ADDED environment Scenario，不再是 delta 外行为。

Outcome: aligned
