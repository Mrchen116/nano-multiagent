# refactor-470-M4: composition root 与测试表面收口 — Tasks

> 对齐: ../design.md v2

## 目标

`personal_assistant.main` 只保留 CLI 参数解析、命令分派和 `main()`；Gateway 对象图由
`gateway.composition.compose_gateway()` 唯一构造。38 个 `main` baseline import/reference
文件按真实 owner、入口保留或无代码 import/reference 分类并完成迁移，且不保留 alias 或测试专用 re-export。

## 退出标准

- [x] `main.__all__ == ["main"]`，入口不再承载 runtime/composition policy。
- [x] `gateway.composition.compose_gateway(config)` 返回完整 `GatewayRuntime`，不新增跨调用可变状态、managed-channel/credential/retry/进程 policy。
- [x] 38 个 baseline 文件完成逐一 owner/删除/保留对账；非入口测试从真实 owner import。
- [x] main 边界、test-size、ruff、非 e2e 回归及 design 指定关键 e2e 全绿；真实 Feishu smoke 按 runbook 完成 online reconnect 与 cached autonomy 消息往返。

## 测试策略

- 被测行为（来自退出标准）：CLI 仍按命令分派；composition 仍装配完整 runtime；入口模块仅暴露 `main`；测试不再依赖 main 私有 re-export；原有 channel/lifecycle/heartbeat/cron 回归保持。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_main_command.py`、`test_gateway_build_runtime.py`、`test_gateway_relay_lifecycle.py`、`tests/contract/test_personal_assistant_main_contract.py` 及 38-file baseline（扩展/迁移）；无新测试文件。
- 落层/目录/marker：`tests/unit/`、`tests/contract/`、`tests/integration/`、`tests/e2e/`；已有 e2e marker 保持。
- 可选依赖 importorskip：沿用 `tests/unit/test_feishu_integration.py` 的 `lark_oapi` importorskip；不新增。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实 Feishu runbook 的临时 review config、进程日志与哨兵消息记录；仅在 `progress.md` 记录结论。

## Roadpoints

### R1 — 固化 composition root 边界与对账基线

- 步骤: 增加入口/owner contract 断言，建立 38-file owner/删除/保留清单，并将测试导入切换计划固化。
- 验证: 新 contract 在旧入口表面失败，且清单覆盖 `rg` 的恰好 38 个 baseline 文件。
- 状态: DONE

### R2 — 迁移 composition 与真实 owner imports

- 步骤: 新建 `gateway.composition`，将装配及无状态投影移出 `main`；把 lifecycle/config、channel registry、runtime delivery、session/permission、heartbeat 和测试导入转向真实 owner；删除 `main` compatibility symbols。
- 验证: 聚焦 Gateway tests、architecture contract、ruff 和非 e2e 套件通过。
- 状态: DONE

### R3 — 真实入口与 Feishu 收口验证

- 步骤: 运行 design 指定 e2e critical paths；依 runbook 独占 real Feishu bot 后完成 online reconnect 与 IM-unreachable cached autonomy 两次哨兵消息往返。
- 验证: 两次真实用户消息均收到 Bot 指定回复；未以启动日志替代消息往返；review Gateway 已停止并恢复主 Gateway。
- 状态: DONE
