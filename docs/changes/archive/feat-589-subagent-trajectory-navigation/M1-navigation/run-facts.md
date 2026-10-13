# M1 运行事实实施记录

范围：product-contracts 的 `TrajectoryRun`；integration 运行事实观察服务、知识维护来源接线及固定 observer 的 `trajectory/runs`；IM carrier 允许该只读方法。没有修改 DSH 上游或官方 bundle，没有增加执行循环；viewer、宿主、current spec 与产品验收由主 Agent 负责。

## 实施

- `agent/created` 记录下一条 offset 为包含式下界，`session/event` 记录接受的尾界；真实 `subagent/start/end` 的父 carrier 和 runId 关联驻留期。不在工具返回时结算，也不依赖结束时仍有 child Agent。
- `tools/execute` 的异步上下文提供 parent、callId、真实 tool/call seq 和用途；knowledge 启动处显式传 memory/skills 与父坐标。省略委派参数时依据真实 descriptor mode 解释官方默认行为：one-shot 的 descriptor 可能晚于 start，届时补全该事实；不解析名称。
- storageDomain 只存运行元数据，串行写入。读取等待写入屏障稳定，失败向读者报错。重启后孤立 start 返回 unknown，已结束事实保留。自身各次 run 与直接发起 run 一并读取，其他 scope 不扩张，旧历史无事实则返回空列表。
- 原生 stopReason `aborted` 映射 cancelled；`error`、`max-tokens`、`refusal` 映射 failed，保留原始 stopReason。

## 测试归属与处置

- `tests/trajectory.test.ts` keep/扩展：冷观察不激活 Agent、固定 session 越权、mutation 拒绝与附件权限。先增 `trajectory/runs` 断言复现 `trajectory_read_only_method_required`，实现后通过。
- 新增 `tests/trajectory-runs.test.ts`：真实锁定 DSH + 受控 LLM 插件，专门保护 run 生命周期与因果元数据，区别于已有只读 carrier 覆盖。三组行为：普通/fork 的并发 rendezvous、继承前缀、完整起止、nested 父链和冷读；continuable 驻留收信不增 run、结束后唤醒产生新 run；失败/取消以及 SIGKILL 后孤立 start 的持久 unknown。嵌套 fixture 显式设置 DSH maxDepth=3，产品默认配置未变。文件少于 400 行。
- `tests/knowledge.test.ts` keep/扩展：已有维护场景以 global Work scope 运行，追加 memory/skills 两类背景 run 的真实来源与边界断言。原维护事实、Feature 撤回、使用记录和持久回看断言保留。
- `tests/knowledge-policy.test.ts`、`tests/tool-presentation.test.ts` keep：既有策略/呈现行为通过。
- `apps/im-server/tests/e2e/trajectory.test.ts` keep/扩展：已有非管理者 Work WebSocket 路径透传 runs，同时拒绝取消；原附件隔离断言保留。
- 无永久测试删除；fixture 使用隔离临时 home/workspace 并清理自己启动的进程，无实际外部 LLM 请求。

## 验证

通过：

```sh
pnpm --filter @nano/product-contracts build
pnpm --filter @nano/dsh-integration build
pnpm exec vitest run packages/dsh-integration/tests/trajectory-runs.test.ts packages/dsh-integration/tests/trajectory.test.ts packages/dsh-integration/tests/knowledge.test.ts packages/dsh-integration/tests/knowledge-policy.test.ts packages/dsh-integration/tests/tool-presentation.test.ts apps/im-server/tests/e2e/trajectory.test.ts
```

结果：6 files / 14 tests passed。`git diff --check` 通过。

额外运行 `tests/contract/test_runtime_dependency_contract.py` 得到 10 passed / 1 failed：并行实施中的 viewer 新增 `@nano/product-contracts` 依赖尚未进入该测试的 ALLOWED；已交给主 Agent 随其依赖边界改动收口。本子任务没有扩大 ALLOWED。完整 workspace gate、浏览器与实际 LLM 旅程验收不由这些受控模型测试替代。
