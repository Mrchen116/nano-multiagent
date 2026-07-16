# bugfix-467-M1 — Progress

## R1 — 注册播种 Red 测试

- Context: 需要把缺失的能力先用测试锁定：Gateway `node.register` 不带 skills/tool_allowlist；IM 创建 profile 时不播种。
- Decision: 在 `test_gateway_upstream_reporter.py` 增加 `send_register` 的 skills/tool_allowlist 断言；在 `test_gateway_node_persistence.py` 增加「创建时播种」与「已存在不覆盖」两个测试；在 `test_gateway_handler.py` 增加 WS 层解析播种测试。
- Rationale: 三处分别覆盖协议负载、持久化语义、WS 处理边界，与 bugfix-404-M2 的 workspace 播种测试模式保持一致。
- Evidence:
  - Tests: 4 个新测试全部失败，失败点 = payload 缺少 `agent_skills` / `agent_tool_allowlist` 字段或 persistence 未使用种子。
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git reset --hard 17dc27d43`（unit 分支基线）
- Commits: C1=`7a5b8bd82`
- Next: R2 实现

## R2 — 实现注册播种

- Context: 在保持 reconcile 与「空=零工具」语义不变的前提下，把种子值从 Gateway 注册帧带到 IM profile 创建路径。
- Decision:
  - `upstream_reporter.py`: `send_register` 增加 `agent_skills` / `agent_tool_allowlist` 两个字典。
  - `gateway_handler.py`: `_handle_register` 解析并透传，加 `_normalize_agent_string_list_seed` 过滤异常条目。
  - `gateway_persistence.py`: `register()` 新增可选参数，仅在 `existing is None` 时使用种子值。
- Rationale: first-seen-wins 与 bugfix-404-M2 的 workspace 播种完全一致，不引入新语义，不破坏用户在 UI 清空后的收敛。
- Evidence:
  - Tests: 4 个新测试 + 相关既有测试共 76 passed。
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git reset --hard 7a5b8bd82`
- Commits: C2=`573dd6185`
- Next: R3 回填 fix.md + live e2e

## R3 — 回填 fix.md 与 live e2e 验证

- Context: lite 模式要求回填 fix.md「修复」「验证」两段，并用真实 ephemeral IM + Gateway 证明 mirror 出生即真值。
- Decision:
  - 在 fix.md 写明改动点、不变量、相关 commit。
  - 用 `scripts/e2e-up.sh` 起 worktree 隔离栈，curl `source=mirror` 与 `source=live` 两个端点，保存证据到 `M1-fix/evidence/plato_config_curl.json`，再用 `scripts/e2e-down.sh` 收尾。
- Rationale: 单测只能证明代码路径正确；真栈才能证明用户报的症状（mirror v1 空壳导致 tools=0）消失。
- Evidence:
  - Tests: N/A
  - Entry:
    - `GET /im/v1/agents/plato/config?source=mirror` → skills 3 项、tool_allowlist 11 项、profile_version=1，非空。
    - `GET /im/v1/agents/plato/config?source=live` → 同样非空。
    - 证据文件：`docs/changes/bugfix-467-register-seed-agent-config/M1-fix/evidence/plato_config_curl.json`
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git reset --hard 573dd6185`
- Commits: C3=`TBD`
- Next: 本 milestone 已完成，合入 unit 分支
