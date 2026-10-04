# feat-578: 独立 iOS App 与免费安装维护

状态：active，需求首文档草案；由独立 chat 继续需求收口、方案研究与实施。尚未通过 Gate 1，不是已确认的架构方案。

## Relations

- Related: bugfix-577

## 原始需求

2026-10-04，用户原话：

> 如果没有合适方案可能要考虑做一个ios app，但是我不会给付费，所以可能要做一个同一个内网内定期更新凭证的方案。
>
> 你要自己衡量是否要做一个ios app

用户随后明确将 iOS App 提升为独立目标：

> 我要求你新开一个独立的thread，新开一个unit，并行的做ios app，可以在里面思考下ios app可以带来什么，比如弹出消息，等等。有价值的东西我会接受。但是哪怕不做新增特性，ios app我也是希望有的。然后你继续修web 的问题

> AltServer 支持同一 Wi‑Fi 下刷新，可以部署到我的mac mini上

## 已确认范围

Agent 解读：

- 必须交付可安装、可使用的独立 iOS App；不再以“Web App 可以修好”作为取消此目标的理由。
- 与 bugfix-577 Web 修复并行推进；Web unit 仍只处理输入缩放和导航遮挡。
- 不要求用户为 Apple Developer Program 或本方案支付费用。
- 探索原生 App 的附加价值（例如消息提醒、系统集成），逐项区分可行能力、免费签名限制与后台系统限制，不预先承诺后台 APNs 推送可用。
- 即使暂不新增功能，App 本体仍在本次目标内。承载方式、MVP边界和新增原生功能由此 chat 基于证据形成具体方案。
- 免费签名与续签优先评估 AltServer + 同一 Wi‑Fi；用户提出 Mac mini 可作为部署位置。准备具体可审查的部署与维护方案，保留现有 Mini 生产服务。

## 当前背景

- 正式 Web IM：`https://im.nanoim.win/`。
- 真实设备：iPhone 15 Pro Max / iOS 26.4；主 chat 正使用 iPhone Mirroring 验证 Web 修复，独立 chat 勿并发争用该 UI。
- bugfix-577 已在同机隔离实验确认：小于16px输入触发focus zoom、100vh高于可用高度、无显式manifest时SPA导航触发系统栏；该修复是独立工作，不替代本unit。
- Apple 免费 Personal Team provisioning profile 7天到期；AltServer官方支持同网或USB刷新。权威来源：[Apple](https://developer.apple.com/help/account/basics/about-your-developer-account)、[AltServer](https://faq.altstore.io/altstore-classic/altserver)。独立chat继续核实具体能力与设备环境。

## 下一阶段需要收口

1. 用户拿到App后最短可用旅程与可验收MVP；保持现有账号、聊天与Agent工作入口。
2. 承载方式和真实原生价值的取舍；通知须明确前台、后台、锁屏、被系统终止等状态下的能力边界。
3. 免费签名、首次安装、同网续签、过期恢复、Mac mini常驻条件及失败反馈。
4. 真实设备与本地开发前置；凭据只在授权环境内使用，不写进仓库或聊天。

以上为调查工作项，不能当成已确认的技术选型或验收通过结论。
