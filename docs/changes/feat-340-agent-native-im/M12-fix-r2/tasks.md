# M12-fix-r2: Post-Acceptance Fix Round 2

## 目标

修复验收 round 2 发现的 2 个 issue：
- R2-1 (major): zh.json `shell.tabs.agents` 仍为 "Agents"，未翻译，改为 "智能体"
- R2-2 (minor): `app.py` 中 WS `?user_id=` legacy fallback 仍存在，承诺 unit lands 前删除未执行

## 退出标准

- zh.json `shell.tabs.agents` = "智能体"（整个 `shell.*` namespace 无未翻译英文 key）
- `npx tsc -b` 干净，无 error
- `npx vitest run` 全绿（≥ 52 文件 / 236 测试）
- WS `/im/ws/user?user_id=xxx` 返回 403/1008（不被接受）
- WS `/im/ws/user?token=<jwt>` 正常接受
- `pytest tests/im_service/` 不新增 regression

## 测试策略

- R1(i18n): 修改 i18n.test.ts 断言 zh 模式下 `shell.tabs.agents` = "智能体"；补全检查 `shell.*` 无漏翻 key
- R2(WS fallback): 修改 test_user_stream_auth.py 补一个用例断言 `?user_id=xxx` 被拒绝

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | zh.json shell.tabs.agents 改为 "智能体" | DONE |
| R2 | 删除 app.py WS ?user_id= legacy fallback | TODO |
