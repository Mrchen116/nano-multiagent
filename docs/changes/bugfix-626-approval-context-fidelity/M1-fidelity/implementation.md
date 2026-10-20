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
- build/typecheck/full regression 与真实产品验收、独立门禁待完成后补充。以上不是生产验证，也未部署。
