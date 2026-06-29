# bugfix-446 — 回归验证

> 对齐: incident.md

**Review Round**: 1  
**Verdict**: pass  
**Highest Required Action**: pass  
**Issues**: { blocking: 0, major: 0, minor: 0 }  
**GH Issues Filed**: none  

---

## Verdict

**pass**

所有 Scenario 均通过真栈 e2e 与单测验证。节点在 IM 重启、启动顺序颠倒两类场景下均自动恢复 online，无需手动重启 Gateway。

---

## 验收标准覆盖

### Requirement: 瞬态故障后节点自动恢复 online

| Scenario | 验证方式 | 证据 | 结果 |
|---|---|---|---|
| Gateway 所在机器休眠后唤醒 | e2e-resilience.sh Scenario A（kill IM ≈ 宿主级断连，等效休眠唤醒，design.md 决策 5 注） | `✓ A2 node auto back online after IM restart (no gateway restart)`，RESILIENCE E2E PASS | **pass** |
| 网络中断后恢复 | e2e-resilience.sh Scenario A（同上，网络断开等价于 socket 死掉需重连） | 同上，A2 pass | **pass** |
| IM 服务重启 | e2e-resilience.sh Scenario A（直接 kill IM 进程后重启同库） | `✓ A1 initial node online` → kill IM → restart IM → `✓ A2 node auto back online after IM restart (no gateway restart)` | **pass** |

**Requirement 结论**：3 条 Scenario 全 pass，该 Requirement 通过。

---

### Requirement: 启动顺序不敏感

| Scenario | 验证方式 | 证据 | 结果 |
|---|---|---|---|
| Gateway 先于 IM 启动 / 启动时 IM 不可达 | e2e-resilience.sh Scenario B：先起 Gateway（IM 未起），sleep 6s 确认进程存活，再起 IM | `✓ B1 gateway survived startup with IM down` / `✓ B2 node online after IM comes up`，RESILIENCE E2E PASS | **pass** |

**Requirement 结论**：1 条 Scenario pass，该 Requirement 通过。

---

### Requirement: 连接层故障永不致 Gateway 僵尸

| Scenario | 验证方式 | 证据 | 结果 |
|---|---|---|---|
| 出现超出已知范围的连接故障 | 单测 `test_watchdog_rebuilds_im_loop_after_abnormal_exit`（im_task 异常退出即被 watchdog 重建）+ e2e Scenario A（IM down 期间 Gateway 进程保持存活） | 13 watchdog 相关单测 pass；e2e A 期间 `gateway_alive` 检测持续通过 | **pass** |

**Requirement 结论**：1 条 Scenario pass，该 Requirement 通过。

---

## 复现验证

修前路径（incident.md §现象与复现）：

```bash
# 1. 启动 Gateway
# 2. kill IM
# 3. 等 30s 后重启 IM
# 4. 查节点状态 → 实际: "offline"（Gateway 未自动重连）
```

修后（真栈 e2e 实跑结果）：

```
Scenario A: IM restart
  ✓ A1 initial node online
  killing IM ...
  restarting IM (same DB) ...
  ✓ A2 node auto back online after IM restart (no gateway restart)
RESILIENCE E2E PASS
```

节点在 IM 重启后自动回 online，无需重启 Gateway。复现路径已消除。

---

## 回归测试

**全测试树（不含 e2e）**：3125 passed, 1 skipped, 22 deselected（`pytest -m "not e2e"`），含 `tests/unit/`、`tests/contract/`、`tests/im_service/`。无新增失败。

**连接层回归（既有用例）**：`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` 18 例全 pass——断线重连、退避封顶、入站分发、心跳逻辑均无退化。

**feat-393 护栏回归**：`test_heartbeat_start_waits_for_first_connect_attempt` pass，心跳首 tick 等待首次连接尝试落定，移除 eager connect 未破坏 feat-393 不变量。

**Lint**：`ruff check` + `ruff format --check` 对 `src/personal_assistant/` 全通过。

---

## 自动化测试增量

| 测试文件 | 新增场景 | 防回归目标 |
|---|---|---|
| `tests/unit/personal_assistant/test_gateway_im_resilience.py` | cancel 清理 + re-raise、首连成功/失败 set 信号、wait 超时有界、on_connected 失败不断连、InvalidStateError 不外泄（6 例） | `run_forever` CancelledError 分流 + 首连落定信号 + TOCTOU 防御 |
| `tests/unit/personal_assistant/test_gateway_runtime_watchdog.py` | watchdog 重建 im_loop 异常退出（3 例）、启动不敏感（connect 恒失败 Gateway 不崩）、心跳首连门（先 resolve 再 heartbeat.start）（共 3 例） | 主循环 watchdog + 启动顺序不敏感 + feat-393 护栏 |
| `tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py` | subprocess 驱动 `scripts/e2e-resilience.sh`，`@pytest.mark.e2e`，门控 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` + 主 config 存在（1 例） | 登记入套件，缺环境干净 skip |
| `scripts/e2e-resilience.sh` | Scenario A（IM 重启节点自动恢复）+ Scenario B（Gateway 先于 IM 启动）真栈脚本 | 集成层真栈验证，防重蹈"从未真栈 e2e 覆盖"根因 |

`docs/e2e-critical-paths.md` 已登记 #13「Gateway-IM 连接韧性」。

---

## User Journeys Exercised

| Journey | Scenarios 覆盖 | 操作摘要 | 结论 |
|---|---|---|---|
| 旅程 1：IM 重启自愈 | 休眠后唤醒、网络中断后恢复、IM 服务重启 | 起 IM+Gateway → 确认 online → kill IM → sleep 4s → 重启 IM → 轮询节点状态 | PASS：节点自动回 online（75s 内） |
| 旅程 2：启动顺序颠倒 | Gateway 先于 IM 启动 | 先起 Gateway（IM 未起）→ sleep 6s 确认进程活着 → 起 IM → 轮询节点 online | PASS：Gateway 不崩，节点自动 online |
| 旅程 3：watchdog 兜底 | 连接维护故障永不致僵尸 | 单测注入 im_task 异常退出 → watchdog 计数重建，不外泄 | PASS（单测层）；e2e Scenario A 补活 |

---

## Side Findings

无。本次旅程中未观察到本 unit 范围外的明显异常。

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。本 unit 只改 Gateway 内部连接行为，不改包间依赖/部署图。
- [x] `docs/specs/gateway/spec.md`（长青行为契约层）：**需要更新**（由 orchestrator §7.0 收尾归并写入）。delta-spec 在 `docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md`，新增「宿主级瞬态故障同样自愈」扩充说明 + Scenario 三条（休眠唤醒/断网恢复/IM 重启）+ ADDED「启动顺序不敏感」+「连接维护故障永不致不可恢复」两 Requirement。worker 已知会 orchestrator，canonical 未写入属预期。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。启停范式与端口隔离约定未变。
- [x] `docs/SPEC_GUIDE.md`：**无需更新**。本 unit 未改文档体系本身。
