# feat-615 Code Review

## Round 1

- Reviewer: `/root/static_review_615`，独立静态审查者，未参与受审实现。
- Mode: `full`。
- Executed base: `08b06c57b`。
- Validated product head: `ccf74c47cafa2aef4b3a9e73fec05f178578c5a0`。
- Range: `08b06c57b..ccf74c47c`；44 个产品、测试、资产及固定动作证据文件。未提交 `.approval-e2e.yaml` 与主代理继续编写的证据脚本不属于本次冻结代码结论。
- Result: **1 CONFIRMED finding；需修复后局部 closure**。

```json
[
  {
    "file": "packages/dsh-integration/src/policy/codex.ts",
    "line": 61,
    "summary": "[P2] 将已验证的原生人工审批投影进 Guardian 证据",
    "failure_scenario": "在 single_thread 人工允许一次受审动作后，DSH 只记录 approval/asked 与 approval/decided；后续 Codex 审查仅读取 deriveMessages 和 PTC 事件，既不读取该配对记录，也不读取 nano_approval 的 human audit。Guardian 因而能看到历史动作但看不到宿主确认的人工批准，连续维护或失败后再审查时会把真实授权当作未知。这违反 design 决策 4 的人工审批保留要求。应按 approval id 配对 allowed-once 并关联有效历史中的 callId/精确动作，保持批准的原动作范围；不能把旧批准推广到新动作或复活已压缩掉的动作。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

### Finding 直接证据

- `policy/codex.ts:59-66` 只用 `ApprovalSources.history` 构造当下证据。
- `policy/sources.ts:80-139` 读取 snapshot 只为 subagent/step/PTC 关联，输出只来自有效消息及 PTC 调用/结果，没有 `approval/asked` / `approval/decided` 分支。
- 已锁定 DSH public `dsh-user-approval` 的 `ApprovalService.request` 持久化 asked `{id,toolName,callId?,reason?}` 与 decided `{id,outcome}`；public 类型说明二者是 log-only audit，不进入消息 surface。
- `src/index.ts:214-215` 仅在人工拒绝并给出理由时注入 `user-approval` 消息。`policy/approval.ts:35-43` 的人工允许 audit 写入独立 domain；Codex 请求没有消费它。
- 最小可重跑 seam：`pnpm exec tsx /tmp/feat615-manual-approval-projection.mts`。fixture 同时提供有效 bash tool-call 与合法 allowed-once audit pair，输出只剩 bash 调用，`hasManualAuthorization=false`。脚本与输出 `/tmp/feat615-manual-approval-projection.{mts,json}` 是本次临时证据，不提交永久测试。

### 已覆盖范围

1. **配置全链。** nullable mode、旧客户端省略保留、显式清空继承、canonical/IM fingerprint、SQL migration、registration seed、Node runtime override，以及既有 apply/recovery/rollback/下一轮冻结 seam。没有改变 Auto 开关或执行模型解析。
2. **CC。** downstream allow 后才走普通 write/edit fastpath；原始与真实路径都限定 cwd；不存在叶子从最近已有祖先解析；敏感目标、自定义策略与 Bash 不获得新增豁免；原分类逻辑从 facade 提取后保留两阶段和 DSH 路径。
3. **Codex。** 独立 Service；固定 policy 资产与严格 verdict；受限 Agent scope 的 host-owned 三工具及 guard；无继承运行工具、PTC、写入、消息或网络。scope 自有注册可覆盖同名祖先工具的事实由锁定 DSH 源码和 native 测试共同确认。
4. **生命周期。** 同步认领 trunk；并发从最后成功 checkpoint seed fork；成功才推进 rows/events；失败、取消、历史改写和配置变化清理未提交实例；一次紧预算重建；整次 90 秒 signal 与父取消关联；返回前检查取消；high/critical 不因拒绝计数放宽。
5. **来源与预算。** CC 默认 transcript 不变；Codex 保留普通工具内容并标为不可信、私稿与 Inbox/发送真实状态；action 完整保留、授权优先、有界历史及 omission 标记。人工批准投影缺口见 finding；native compaction/deadline 的回归证据缺口另记 verification，不以假想代码缺陷替代。
6. **前端与报告脚本。** 新建/编辑共享选择控件，草稿/保存走既有 API；固定动作脚本只在临时 fixture 中做比较。首轮 Codex 对两个临时文件的未授权 rm 给 medium/low 并 allow，是固定上游 low/medium policy 的实测结果，不把它篡改成“已拒绝”或直接当作 adapter 代码缺陷。

### 验证

- 命令：`pnpm exec vitest run packages/dsh-integration/tests/codex-approval.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts packages/dsh-integration/tests/codex-approval-native.test.ts packages/dsh-integration/tests/approval-workspace.test.ts apps/im-server/tests/approval-configuration.test.ts apps/node/tests/configuration.test.ts packages/personal-assistant/tests/configuration.test.ts`。
- 在上述冻结 head 执行：**7 files / 26 tests passed**；日志 `/tmp/feat615-static-review-tests.log`。
- 没有修改实现、测试或运行配置；全量 CI、真实模型比较和产品验收由主代理及独立产品 reviewer 执行，不以本静态报告代替。
