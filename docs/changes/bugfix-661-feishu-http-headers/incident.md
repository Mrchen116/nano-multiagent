# bugfix-661: 飞书入站请求头丢失

> 快速开发；实现与隔离验证进行中，尚无用户验收，保持 active。

## Relations

- Related: feat-657, bugfix-660

## 原始报告

> 为啥我给我的PA发了很多飞书消息，都没收到回复
>
> 这bug为啥出现，哪个feat引入的
>
> 为毛这么基础的问题，测试都没看护住
>
> 审视是不是大量类似的测试废物。帮我快修模式赶紧修了

## 已确认范围

修复已定位的飞书入站故障，检查同类请求头处理及相关测试的真实保护边界，增加能挡住本次回归的隔离测试。合并和生产部署另行授权；不发送生产测试消息，不改生产数据库或手工重放用户请求。

## 现象与复现

2026-10-26 部署 main a16859ac489ba0cfb6762d0eec4fd2513b0f368b 后，Mini 收到的三条 PA 飞书私聊已持久化在渠道入站表，但没有进入 IM 的 PA 来源事件。已有 shadow 会话的入站请求被 IM 以 422 拒绝。Web 消息仍可正常执行，不能证明飞书入口正常。

隔离回归使用 ExternalChannels、Node 实际 HTTP adapter、真实 IM HTTP 服务与临时 SQLite；首次创建 shadow 也会因 JSON 头丢失而失败。旧实现下新增 5 个参数化用例全部失败，原有 external/lifecycle/knowledge 的 15 个用例仍通过。

## 根因与影响

feat-657 提交 701b6caa63fa8be9eb472266b6d288285f3512e2 为渠道 HTTP 请求添加生命周期身份时创建 `Headers` 对象。Node 原 helper 把 `RequestInit.headers` 当普通对象展开，丢失 Content-Type、Idempotency-Key 与生命周期头。它还错误处理 tuple headers，以及大小写不同的 Authorization 覆盖。bugfix-660 保留了该包装。

PA 入站依赖 IM 来源事件，故无法开始执行；普通 Agent 可本地执行，但 IM shadow 投影同样受影响。图片上传也经过同一 adapter。消息入站记录仍保留；恢复应复用既有 recover 和幂等键，不直接修改记录。

单元测试在 IM 接口处返回成功，服务端测试由自己的 HTTP helper 正确发包，两者都绕过实际 Node adapter。测试总数和局部通过被错误外推为链路可用。详细审视见 [test-audit.md](test-audit.md)。

## 修复方向与验收

以 `Headers` 标准接口复制调用方请求头并设置当前 gateway 凭据；只提取现有 HTTP adapter 供生产与测试共用。验证普通 record、tuple 和 Headers 输入；真实入站验证 PA/普通 Agent 的图文持久化、PA 来源可见性、回执丢失后的重启恢复与去重。

生产飞书回复与用户实际验收尚未发生；不以自动化通过代替用户确认。
