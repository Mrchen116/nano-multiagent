# feat-333-M6: wire-permission-broker-e2e

## 目标

将 PermissionBroker 接入 app 装配链路，使 auto_mode_gate hook 的 ask 流程真正可用：
1. app.py lifespan 实例化 PermissionBroker 并赋值 app.state.permission_broker
2. runtime._build_hook_context() 注入 permission_requester 回调（连接 broker）和 metadata['permission_broker']
3. 验证 POST /v1/sessions/{sid}/permissions/{request_id} 路由全链路联通
4. 确认 PA DEFAULT_HOOK_MODULES 含 auto_mode_gate（M5 hot fix 已做）

## 退出标准

- 新增中型集成测试覆盖 e2e ask 链路（模拟触发 bash → emit permission_request → POST decision → 两条路径）
- pytest -m "not e2e" 不比 baseline (203 failed) 新增失败
- cd src/IM/frontend && npm run test 不新增失败
- 真实 IM 端到端走 rm -rf /tmp/test-fff：权限卡片出现 → Allow once → 真执行；Deny → 不执行
- 截图存 ACCEPTANCE/m6-permission-e2e/（≥ 3 张）

## 测试策略

后端核心：集成测试覆盖 broker 注入 + permission_request event emit + POST resolve 链路（ask_allow / ask_deny 两条路径）。
前端：已有单元测试，M6 不改前端代码，只验 npm run test 不退步。
真实入口：e2e 走 IM 全链路（截图证据）。

## Roadpoints

| 编号 | 标题 | 状态 |
|---|---|---|
| R1 | 写集成测试（Red）— 覆盖 broker 未注入 → 注入后 ask 链路 | DONE |
| R2 | I1 + I2：app.py 实例化 broker + runtime 注入 permission_requester | DONE |
| R3 | 全链路验证 + 文档（progress.md） | DONE |
