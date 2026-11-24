# Web 目录请求与徽标复测

候选 469128101，M2 实施者 directory。agents-list-page.tsx 挂载目录与个人助手查询；每个 AgentLifecycleRow 原先还挂载独立 useAgentLifecycle。agent-profile、rail、deletion 和列表有不同的路由、query key 与启用条件。按六处代码位置计算固定流量会漏计逐行请求，也会重复计算互斥路由。

| 场景 | 基线 | 候选 |
|---|---|---|
| 50 行目录首屏，实际 React 路由、模拟 fetch | 1 contacts GET 加 50 lifecycle GET | 1 contacts GET 加 0 lifecycle GET |
| Chromium 连接隔离 IM，50 行 | 未做基线浏览器计时 | 初始和恢复合计 2 次联系人读取，随后 6.3 秒 2 次；全程零逐行读取 |
| 第二个登录会话启用 Agent | 既有 lifecycle.changed 刷新 | 本次 38 ms 后原目录的 Disabled 徽标消失 |
| 创建页桌面侧栏 | 每行挂载 lifecycle 查询 | 真实页面 50 行，零逐行读取 |

列表、侧栏在新版联系人返回摘要时使用摘要；详情、聊天与旧中心缺字段时沿用原查询。表中联系人与逐行请求不含认证、PA 绑定等其他请求。单次 38 ms 只说明这次事件触发及时刷新。假设 100 个设置页每页各有六个请求、每三秒一次，算术是 200 req/s。实际流量取决于页面、可见行数和连接状态。

4 个服务端联系人端点用例、21 个设置页组件用例、Web TypeScript 与 Vite 构建通过，最后再跑 8 个目录测试。测试浏览器、服务、SQLite 及临时目录已回收。
