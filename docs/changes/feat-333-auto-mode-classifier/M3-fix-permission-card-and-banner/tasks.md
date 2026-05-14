# M3: Fix Permission Card and Banner

## 目标

修复 reviewer round 1 验收 fail 的三项 issue：
1. (blocking) IM 前端 permission WS 事件路由断裂 — chat-stream.ts KNOWN_TYPES 缺 permission.request/resolved
2. (major) REPL 启动无 auto 模式横幅 — dangerously_skip_permissions 静默生效，无可见警告
3. (minor) MessageResponse 缺 permission_request 字段 — 刷新后 pending 权限请求无法恢复

## 退出标准

- `cd src/IM/frontend && npm run test`：不新增失败（baseline: 2 failed pre-existing，不碰它们）
- `pytest -m "not e2e" --continue-on-collection-errors`：不比 baseline 新增失败（baseline 203 failed / 1413 passed）
- Issue 1: KNOWN_TYPES 补全，reducer 处理 permission.request/.resolved，PermissionCard 能从 WS 事件渲染
- Issue 2: REPL 启动后有 auto 模式提示；dangerously_skip_permissions=true 时有醒目警告横幅
- Issue 3: MessageResponse 和 to_message_response() 补 permission_request 字段

## 测试策略

| 场景 | 策略 | 是否落库 |
|---|---|---|
| Issue 1: WS 事件路由（前端核心业务路径） | 补 reducer 单测（permission.request / permission.resolved 事件处理），浏览器验收 | 是（reducer 单测） |
| Issue 2: REPL banner（CLI 输出） | 补 Python 单测验证 REPL 启动输出含 auto 模式提示 | 是 |
| Issue 3: MessageResponse 字段（后端 API） | 补 Python 单测验证 to_message_response() 映射 permission_request | 是 |

## UI 状态矩阵

| 状态 | 覆盖情况 |
|---|---|
| permission.request WS 到达 → message 有 permission_request | 核心路径，reducer 单测 + 浏览器验收 |
| permission.resolved WS 到达 → message.permission_request.status = resolved | reducer 单测 |
| dangerously_skip_permissions=false（默认）→ 常规横幅 | REPL 单测 |
| dangerously_skip_permissions=true → 醒目危险横幅 | REPL 单测 |
| 刷新后 pending 权限请求恢复（via REST API） | MessageResponse 单测 |

## Roadpoints

### R1 — 前端 WS 事件路由（Issue 1）
- **状态**: DONE
- **范围**: chat-stream.ts, chat-types.ts, chat-stream-reducer.ts + 对应单测
- **子任务**:
  - [x] C1: 补 reducer 单测（Red）
  - [x] C2: 补 KNOWN_TYPES / WsEvent / reducer 处理逻辑
  - [x] C3: 文档

### R2 — REPL 启动横幅（Issue 2）
- **状态**: DONE
- **范围**: src/coding_cli/commands.py + 对应单测
- **子任务**:
  - [x] C1: 补单测（Red）
  - [x] C2: REPL 启动时打印 auto 模式状态 / 危险横幅
  - [x] C3: 文档

### R3 — MessageResponse permission_request 字段（Issue 3）
- **状态**: DONE
- **范围**: src/IM/api/routes/messages.py + 对应单测
- **子任务**:
  - [x] C1: 补单测（Red）
  - [x] C2: 补 MessageResponse + to_message_response()
  - [x] C3: 文档

### R4 — 回归修复：更新 REPL 精确输出断言（orchestrator 验收发现）
- **状态**: DONE
- **范围**: tests/unit/test_cli_main.py（仅测试，不改实现）
- **根因**: R2 横幅引入后，3 个精确断言（== "" / strip() == "bye"）未更新
- **修复**: 3 处断言改为 contains 检查，同时验证横幅确实出现
- **子任务**:
  - [x] C2: 更新 3 个测试断言（fix）
  - [x] C3: 文档（progress.md R4 段 + tasks.md）
