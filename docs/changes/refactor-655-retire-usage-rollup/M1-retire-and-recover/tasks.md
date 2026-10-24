# M1 tasks

- [x] 核查并删除无产品消费者的累计链，保留 Work / bubble / Workflow budget。
- [x] 原生 catalog/cut 小型元数据持久化，跨重启元数据核对及受信父子归属。
- [x] PA 原生接收、产品处理 checkpoint、WorkSync ACK 分离；开放轮次恢复、原子 journal 提交。
- [x] 同步完整性声明及 Web/iOS 单行状态提示。
- [x] 真栈主子执行、失败工具、统计、重启、分页、原生详情与桌面/窄屏体验证据。
- [ ] 独立产品 review、合并 code review + verifier，final sync/canonical/archive/本地与远端 CI。

测试处置：删除仅累计协议的 usage reader/reporter 测试；usage endpoint 测试改为退役边界；WebRelay 通用恢复保留有效 receipt 协议。原生 Workflow 预算用例保留并增加冷 Work 切口验证；token critical path 从累计 metrics 改为独立 Global Work。PA 重启处理位置/崩溃窗口独立归入 global-work-recovery.test.ts，既有超长 global-agent.test.ts 不再堆新恢复场景。现有 WorkSync、Web panel、iOS AgentContracts 文件各扩展本层契约。
