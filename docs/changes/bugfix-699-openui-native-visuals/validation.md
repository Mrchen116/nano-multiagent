# bugfix-699 验证记录

状态：进行中；Agent 自验与用户验收分别记录。

## 已执行

- Base: 95c6b3deb07c03e9edd3b78375cd0ae29e87558e，独立 worktree，不含主仓已有 dirty 内容。
- Node 24.22.1，pnpm 11.7.0；pnpm build、pnpm typecheck 通过。
- frontend interactive 相关 3 个文件、22 个测试通过；生成资产 --check 通过。
- DSH capabilities 4 个测试通过。该检查不代表真实模型已消费新指导。
- 用户原图：酒店消息 b437225bf1fc482fa94a718969ec9302；看板消息 ef4f7762a9f94765957e485aa90a9025。只读浏览器放大截图留本机 output/playwright/openui-native/，未改生产消息。
- 隔离 daily 栈已启动，自己的端口/identity/data/workspace，真实模型与视觉结果待补。

## 用户验收

尚未发生。不能以 Agent 自验或组件测试代替。

## 完成的 Agent 自验（2026-11-02，北京时间）

- 前端全量：109 files / 1,037 tests 通过；short policy 改动后 DSH capabilities 再跑 4/4 通过；docs-check 通过（336 maintained Markdown sources / 68 required routes）。
- 隔离 daily PA：`pa_2332f924831b`，真实 `codexOAuth:gpt-6-astra` / medium；另普通 Global P 使用 `codexOAuth:gpt-6.1-sol` / high 生成酒店对照样本。没有向模型提供目标 DSL、控件参数或酒店/看板专用模板；输入为用户原图的浏览器放大截图与普通复现要求。
- PA 酒店：输入 `cb2b7d49c7d84af59b5078143975a848`，交付 `e08bb044e3694af29a8be0a8984bbd47`；P 对照交付 `9606c4e2ce8043e88b22f701f856014f`。
- PA 看板：输入 `2998e2a7fec5486db42369822c5c8a8a`，交付 `53350905c10a4ceb89624bccf5d9b616`。样本在短 policy 更新、integration 重建与隔离 Node 正常 restart 后生成；浏览器已使用本轮源码构建产物。
- 浏览器：默认桌面视口、1440×1000 桌面断点与 390×844 手机断点。酒店小号 Book 为 32px 高、7px 圆角、Inter 14px，颜色来自上游默认蓝色；圆形收藏为 32×32。修前为 Nano 绿色中号约 46.4px 高，卡片强制 24px 内边距。不能把官网定制黑色胶囊当成固定版本默认视觉。
- 实际操作：酒店收藏/取消、关闭/重新打开、图片 Gallery 弹层；看板 All regions → Europe → All regions，散点系列相应变化。没有因本地操作新增 Agent 回复。手机页面 documentElement scrollWidth/clientWidth 均为 390，没有页面水平溢出；酒店按 Carousel 横向浏览，看板指标两列、图表向下阅读。
- 截图留本机 `output/playwright/openui-native/{hotel-desktop,hotel-mobile,hotel-gallery-mobile,dashboard-desktop,dashboard-mobile}.jpg`；原图同目录；真实消息/source 快照 `output/hotel-pa-messages.json`、`output/hotel-p-messages.json`。不提交图片、原始会话或运行配置。

## 实际 Context 证据与边界

- PA 原生 session `267b08d6-af1c-4263-b4db-670e14216241` 的日志解压副本留本机 `output/pa-native-session.jsonl`。
- 第 30–31 行是 Skill tool call/result（seq 28/29），正文含更新后的 `COMPOSITION: Use the upstream OpenUI visual defaults.`；第 33–35 行随后真实模型继续并调用公开发送工具，IM 已持久交付上述酒店消息。
- 第 47 行 system/message（seq 45）含最终短 policy `Choose layout, density, component variants...`；第 50 行 request/header，随后真实模型继续，至第 62–63 行工具调用/结果并持久交付看板。
- 这些是原生实际交付/消费链与产品结果证据；本机代理未定位到对应 provider 原始 wire payload，不能用原生日志替代 wire 保真声明。
- 启动期间 gateway.log 有 `agent_disabled` 报错，但 PA/P 后续成功交付；错误不能据此被描述为本轮模型验收失败，根因不在本轮修复范围。

## 对照结果与剩余限制

- 恢复上游默认视觉已验证；酒店控件与密度改善，但图片仍是模型选用的替代照片，标签/字体/按钮并非官网营销页专用 CSS，非像素还原。
- 看板保留四项指标与左右图形结构、区域切换可用，但模型仍以原生 HorizontalBarChart 近似居中示意漏斗，后级因数量级差异很短；背景面板/轴和比例也不同。**不能宣称看板已忠实复现原图**，本轮未增加专用漏斗或截图模板。
- 官方 `thesysdev/skills` / OpenUI Skill 用于开发接入；当前运行时 Skill 的语言/目录来自注册库的上游 prompt()，Nano 仅包装消息及状态/权限约束和通用生成指导，未整套引入开发 Skill。官方来源：https://www.openui.com/docs/mcp 与 https://github.com/thesysdev/skills 。
- 用户验收仍未发生；不以 Agent 自验冒充，不归并 canonical，不归档。

## 用户追问后的漏斗能力核对

用户问：“漏斗不能还原的原因是模型还是什么限制，你写的话能还原吗”。

- 核对实际已安装 react-ui 0.18.1 的公开 JS exports：`FunnelChart` 为 function；`openuiLibrary.components` 共 82 项，其中无 FunnelChart。本仓继承完整模型目录，不代表开放了包里所有原生 React 组件。
- 当前已登记 HorizontalBarChart 的 schema 只有 labels/series/variant/xLabel/yLabel；没有居中漏斗、独立示意宽度、隐藏轴等参数。单纯换一份同样受该目录限制的 DSL，不能忠实复现参考的居中示意条。
- 使用同一份 4.2M/310K/42K/9.8K 数据，在本机隔离页实际渲染三列：当前 HorizontalBarChart、上游公开 FunnelChart（vertical/straight/layers=1）、手写参考式流程示意。截图留 `output/playwright/openui-native/funnel-capability-comparison.jpg`。
- 上游 FunnelChart 确实能画居中漏斗，但同样按实际数量缩放，后段很窄。手写通用 HTML/CSS 的阶段条能接近参考；条宽明确仅为流程示意，不伪装成真实数量比例。
- 原因包含模型选图/语义判断与已开放表达范围两部分；不能全归给模型，也不能声称只登记 FunnelChart 就获得参考外观。验证页没有加入产品，也没有新增截图专用组件或模板。
- 此证据补充不改变已审代码。扩展通用图形/布局表达能力不在已实现的“恢复默认视觉”代码范围内；用户仍未确认验收。
