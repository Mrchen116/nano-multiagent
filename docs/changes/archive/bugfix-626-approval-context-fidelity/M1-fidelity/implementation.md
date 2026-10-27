# M1 实施与证据

基线 `b5c1e9790`，DSH 锁定 `0.2.1-alpha.1`，Codex 固定 `806d9732c974bc8a51b8317c1bd8985544fe627c`。实施位于独立 `unit/bugfix-626` worktree，主仓已有改动未参与。

普通审批入口已移除 `pa.authorization` 调用、请求参数和 CC/Codex 注入。PA 独立审查及其取证不改。Codex 移植依设计分开 profile/admission，完整计入授权历史、保留最新五条工具及 ProtectedAssistant；恢复才缩历史，保留来源与首尾，按完整序列化请求测量。Inbox 按 message 映射，避免与 generic tool result 重复；继承记录也规范化。输出契约与 parser 对齐固定上游默认值和包装 JSON。

## 必要适配与证据边界

- 本地上游 `guardian-context/src/profile.rs` / `enforcement.rs` / `transcript.rs`，`ext/guardian-reviewer/src/assessment.rs`，`core/src/guardian/{review,review_session,input_budget}.rs` 为机制对照。
- DSH public session 有有效历史、seed/fork；无 Codex ThreadOwned accepted-source/compaction checkpoint，因此本次采用 Legacy retained transcript，不声明支持 ThreadOwned 或预测审核。
- DSH `setSandboxMode('read-only')` 仅文件效果约束；public SandboxMode 不覆盖网络与进程。保留受限 stat/read/list，不能宣称具备上游任意 sandboxed shell/git/远端调查能力。
- DSH GenerateOptions 无 final output schema 参数：原样输出契约加上游 parser，不走私有 provider 接口。
- 现有独立模型、low 推理和 Nano 消息来源/实际投递适配保留。这里的保真结论针对列明机制，不是任意任务效果等价。

## 测试处置

| 覆盖 | 处置 | 原因与可观察 seam |
|---|---|---|
| personal-security 首项 | rewrite-merge | 旧测试要求注入额外 PA 授权，改为原生 DSH 两策略：有效用户历史允许动作；禁止动作仍阻断；消息交付边界不变；product.call 无额外全库读取 |
| approval-sources | extend | 保留 CC 原有 PTC 压缩和恢复来源保护，补 Codex 混合 Inbox 每消息来源、单次正文、继承去重 |
| codex-approval | rewrite-merge | verdict、profile、最终 admission 在原 seam 上对齐上游；覆盖完整 action、保护证据、preserve/recovery、超大 optional 优先淘汰 |
| codex-approval-lifecycle/native | keep | 原生复用、并发 fork、失效、上下文恢复、取消及 90 秒超时仍适用 |
| PA/IM personal 测试 | keep | 独立入站/提交检查未更改，仍由其最低层测试保护 |

没有新建永久测试文件。一次性产品脚本与运行数据仅留隔离目录，不提交进套件。

## 验证记录（实施中）

- Red：`/tmp/nano-626-red.log`，旧实现普通 nano 动作读取额外授权 1 次（期望 0），Codex 被超大包污染；`/tmp/nano-626-red-context.log`，上游 parser/profile/recovery 差异 4 项失败。
- Green：`/tmp/nano-626-green-focused.log`，23 tests / 4 files passed；新增 optional/继承保护见 `/tmp/nano-626-final-context.log`。
- `pnpm build`、`pnpm typecheck` 通过；`pnpm test` 106 files / 476 tests passed（`/tmp/nano-626-{build,typecheck,full-tests}.log`）。
- `pytest -m "not e2e" -q` 62 passed / 31 deselected；ruff check 和 format 均通过；docs-check 通过（`/tmp/nano-626-{python,ruff,docs}.log`）。
- Web npm ci/build/test/audit：100 files / 936 tests passed，critical audit 通过（`/tmp/nano-626-web-*.log`）。未改 iOS，按 CI 路径规则不适用本地 iOS gate。
- 用户要求的线上原始失败轨迹只审核回归通过，详见 [production-replay.md](production-replay.md)：CC/Codex 有效 allow，工具执行次数 0，主 Agent 未续跑。它不是生产部署。
- 独立产品回归 `M1-fidelity/regression.md`：pass，百万字符库内旧历史不放大两策略请求；PA participant/observer/ownerDM/外发边界真栈覆盖。
- 独立 code review：无发现；verification Round 2：本地 gate pass，0 CRITICAL / 0 WARNING，canonical 与已审 delta 一致。
- final sync：`origin/main ff5fbc8f5` 合入 `7dce653ef393e5fac8cb242b5cf92ddeff363a20`，相对 executed_base 只增加 feat-625 design-review.md 135 行，产品/测试树仍与 validated_at `40cd54ddf81c5c7262d1d2f69cb83b5dd3287bad` 一致。三道门禁 retained；后续仅报告、canonical 归并与完整归档。远端 CI 在 Ready PR 创建后运行，以 PR checks 为最终状态。
- 隔离服务清理完成：大历史栈 55423、小历史栈 56030 均无监听，所属 Node/DSH 进程和 tmux 已退出。生产只读取证，未重启或部署。
