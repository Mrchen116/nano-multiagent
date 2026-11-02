# feat-700 As-built design

本文在快速开发中据实际实现形成，用户验收尚未完成。

- 工作分支：codex/openui-native-visuals；本轮开始 HEAD 1c493d000，随后合并 origin/main 9cb67e17，merge 5614b1fb，以复用已合入的 Memory 评测。原 UI 三个预览服务不停止。
- 取号脚本原子保留 feat-700。新代码作用域以 merge 后 dirty diff 为准；496 项主干变更不冒充本任务实施。
- evals/intelligent-ui/dataset.json + assets 固定三个 case。公共页面只显示 case，fresh-context 是执行前必须满足的协议要求；本轮没有声称已实现自动隔离运行器。
- evals/ui 的 catalog 提供能力/case/阶段数据；server 提供带随机本地读取 capability 的目录、原图、报告及 native trajectory 载体；index/app/native 从原本机 Memory 页面提取公共导航、样式和 MessagePort 桥，去除机器路径、题号、阶段数和模型请求数硬编码。
- Memory 原生读取经 apps/node 的显式 evaluation-archive 公开子入口接入。它复用 NodeConfiguration/providerProfiles 与 @nano/dsh-integration/client，不绕过公开 DSH exports。初始化前复制 agent-work/runtime，将 gateway workspace/owner 路径重定向到 viewer 自有目录后才读取配置；所有 agents 置 disabled，公开 initialize 的 observationOnly 跳过知识恢复和自动清理，防止历史绝对路径触及原件。product.call 拒绝，读取仅限归档已声明 sessions 和已获 observer。
- 旧归档当前一目录一 case；多题归档明确拒绝，不能将同组 sessions 冒充多题。各能力保留自己的协议，不将 Memory 的 prepare/answer/score 强套到 UI 视觉判定。
- --ui-evidence 可挂接已有产品对话，明确标“已有复测现场，不是本页面新执行”。不持有这些产品服务的生命周期。
- 此前尝试的自动运行/评分大原型已移入 ignored output/eval-runner-draft，不交付、不编造为用户要求；package/e2e-up 相关试作已恢复。
- 本轮无产品 API/current spec 行为变化；评测入口的长期说明由 evals/README、ui/README、intelligent-ui/README 维护，docs/README 只加路由。
- 风险/边界：旧 Memory 归档配置与锁定 DSH 版本必须兼容；原生查看只是读证据，不证明候选曾走完整产品链路。没有把未运行的新 case 判成通过。
- 回滚：回滚 feat-700 代码/资产/文档提交；无需数据迁移。原 Memory 页面和数据仍保留。公共查看器的 Ctrl-C 只清理自己观察流与 DSH，按用户要求保留产品预览。

- 实际核验和测试见 [validation.md](validation.md)，独立审查发现及闭环见 [code-review.md](code-review.md)。Memory 阶段在目录中默认折叠，避免批次很多时遮住其他能力；case 内仍可访问各阶段。
