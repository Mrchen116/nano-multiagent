# bugfix-669: As-built Design

> 实现后根据实际代码、diff、验证与用户决定整理；没有事前 design review 或 milestone。

## 实现范围

- Base: `a89b778de4dda56da933a12e5b59bcf81c207cb1`
- Implementation head: `ded0d64181c95757057ea4f41d9232dfde536ea5`
- 实现提交修改三个文件：`packages/product-contracts/src/index.ts`、`packages/personal-assistant/src/presentation.ts`、`packages/personal-assistant/tests/store.test.ts`。
- 收尾只增加本 unit 文档与对应 current spec 场景；不改执行代码。

## 最终结构与数据流

DSH 原生日志经 integration 原样保留顶层事件字段，PA 持久化 RuntimeEvent，再经 toolPresentation / projectWorkEvent 投影为 Work 工具记录。RuntimeEvent 新增可选 surfaceOp 类型；toolPresentation 只对 tool/result 的 replace 返回 undefined，使上下文替换不生成第二条 tool_end。原始日志、模型 surface 和 IM 合并算法均不修改。

普通 append 与旧日志缺省 surfaceOp 保留原有成功/失败、payload、耗时行为。主/子执行与恢复共用同一投影边界，不新增去重状态或时间启发式。

## 关键决策

| 决策 | 原因与约束 | 定位 |
|---|---|---|
| 在 PA 展示边界过滤 replacement | 执行事实和模型历史替换语义不同；不能删原始事件或影响模型消费 | presentation.ts tool/result 分支 |
| 可选产品结构类型，不 import DSH | 保持包边界与旧日志兼容 | product-contracts RuntimeEvent |
| 扩展已有 store/projection 测试 | 最低可观察 seam，覆盖持久化再重放，不增加重复高层测试 | store.test.ts |
| 不迁移旧 Work 污染记录 | 本任务是阻止新覆盖；历史回填涉及额外数据修改范围 | 无迁移脚本 |

## 验证与证据

### 自动化

新增四组成功/失败 × append/旧缺字段用例，原始时间采用 issue 的 98ms 样例。修复前四组均因多出第二 tool_end 失败，修复后通过。断言原 payload、98ms、仅一条完成、逐事件与 DB 重放一致，replacement 原始日志未改写。

| 命令 / 门禁 | 结果 |
|---|---|
| pnpm install --frozen-lockfile; pnpm build; pnpm typecheck | 通过 |
| pnpm check:ios-runtime | 通过 |
| vitest store.test.ts global-work-recovery.test.ts workflows.test.ts | 3 文件 / 30 测试通过 |
| env -u NANO_OWNER_CONFIG_ROOT pnpm exec vitest run --maxWorkers=2 | 142 文件 / 770 测试通过 |
| pytest -m 'not e2e' -q | 70 通过 / 32 deselected |
| ruff check .; ruff format --check . | 通过，88 文件格式通过 |
| ./scripts/docs-check | 通过 |
| Frontend npm ci; shared contract tsc; npm audit --audit-level=critical | 通过；既有11项非critical告警未在本修复升级 |
| Frontend npm run test -- --maxWorkers=2 | 108 文件 / 1031 测试通过 |
| Frontend npm run build | 通过 |

首次默认并发全量运行出现 worker/native timeout 与继承 owner-root 配置断言失败；清除继承 NANO_OWNER_CONFIG_ROOT 并限制 worker 后完整重跑通过，未改测试 timeout 或产品逻辑。iOS 原生 build/test 按路径门禁不适用。

### 真实模型压力与回看

隔离 daily 模板，真实 `codexOAuth:gpt-6-astra`，默认上下文策略；只读六份合成随机文本，不复制生产上下文。原生六次 read 后触发**一批工具输出裁剪**，产生六条 per-result compaction/prune（seq 91/93/95/97/99/101，时间跨度23ms）及六条 replacement（92/94/96/98/100/102）。没有 compaction/start、summary、end，没有 new_context 调用，窗口仍为 initial；不能称六轮完整压缩。

| 原始 result seq | 原始及 Work 耗时 | 旧逻辑会算出的耗时 | replacement seq |
|---|---:|---:|---|
|33|58ms|50155ms|92|
|43|49ms|37188ms|94|
|53|47ms|29929ms|96|
|63|48ms|22324ms|98|
|78|55ms|8490ms|100|
|89|55ms|93ms|102|

逐条仅一个 Work tool_end，原结果56457字符逐字保留，模型替换结果5159字符；前五项裁剪前后实时 Work 快照完全相同，第六项紧邻裁剪，原始 native result 与唯一实时完成核对一致。实际事件输入编译后投影重放，六项输出与实时相同。真实模型下一次上下文读数 T=44064（此前208142），看到 prune marker 后正常完成。浏览器 Work 展开及 reload 后六条耗时不变。

read 本身有既有1024行输出上限，未声称文件尾标记返回。原生轨迹仅为摘要 start/summary/end 显示压缩节点，不单独显示 prune；本次不改变该显示范围。

可复核本地定位：测试 session `fc2e1ca4-0e04-4177-bf00-6b7c42aabf41`；隔离目录 `/tmp/nano-issue420-native.6hLdrz/acceptance-evidence/` 中 native-events、work-events、verified-native-work、replay-verification JSON 和前后快照；浏览器截图在同目录上级 output/playwright。原始运行配置、凭据、数据库、截图与上下文不提交；上述表为必要的合成测试摘要。

### 用户确认

用户亲自查看预览、询问次数并获得“一批六输出、零摘要压缩/零换窗”的解释后要求提 PR。真实六文件执行由 Agent 完成，不虚构用户重跑。无独立产品 reviewer；独立代码审查见 [code-review.md](code-review.md)。

## 失败路径、风险与回滚

无新持久状态；回滚实现提交会重新引入 replacement 覆盖风险。此修复不恢复旧污染记录，不进行生产迁移或部署，不生成 deployment-prompt。未改变模型消费链，原生 replacement 保留及真实后续模型完成已验证。

## Canonical 文档影响

向 IM Agent Work 的“工作轨迹保留可检查的执行明细”补充模型上下文裁剪场景；delta 位于 specs/im/agent-work.md，按最终行为归并 current。其余展示和摘要压缩行为不扩展。
