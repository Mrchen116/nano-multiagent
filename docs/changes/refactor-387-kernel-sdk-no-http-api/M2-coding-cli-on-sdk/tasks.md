# M2: coding-cli-on-sdk — Tasks

## 目标

把 `coding_cli` 从「spawn uvicorn + loopback HTTP」改为「进程内持有 `Kernel`、async-native REPL」，
权限走注入的 `can_use_tool` 回调，删除 HTTP 桥接层。

## 退出标准

- `[worker]` coding_cli 单测全绿（新增/已有）
- `[reviewer]` Review-A 全部 Scenario pass（多步工具任务 / 权限 / 打断 / 后台通知 / 子 agent / skill / REPL 命令 / 无模式进 REPL）
- 无新增红测

## 测试策略

后端/CLI 任务，无前端 UI，测试策略：
- C1 写失败单测，覆盖 async REPL 核心路径（SDK 调用、权限回调、命令处理）
- C2 实现，让单测绿
- 真实入口验证：REPL 能启动、完成一轮会话

测试命名落层：
- `tests/unit/test_cli_*` —— coding_cli 单元层
- `tests/contract/test_cli_http_only_contract.py` —— 注意此文件有 2 个已知红测（M4 清理），不动

## UI 状态矩阵

N/A —— 纯 CLI/后端任务，无前端 UI。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 新建 async REPL 骨架 + 单测 | DONE |
| R2 | 用 agent.sdk 替换 ServerClient（会话、提交、流式） | DONE |
| R3 | 权限回调 can_use_tool（回调内 await 用户输入）| DONE |
| R4 | REPL 命令适配 SDK（/new /tools /compact /history /session /use）| DONE |
| R5 | 删除 HTTP 层（client.py / kernel_app.py / managed_server.py / session_stream.py HTTP 桥）+ 修复合约测试 | DONE |
| R6 | 收尾：main.py asyncio.run + 更新 README + 合约测试适配 | DONE |
