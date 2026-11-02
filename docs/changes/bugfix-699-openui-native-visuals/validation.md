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

## 最终扩展范围：接入 Open Intelligent UI（2026-11-02）

前文是第一轮标准 react-ui 默认视觉修复及其调查的历史记录；下列证据对应用户随后明确要求的 open-intelligent-ui 接入，不能用前一轮测试替代。本轮未要求旧 Web DSL 兼容。

### 实现与验证

- 固定上游 `16ef26475999e3a021a50b1607a03717c0721255`：完整 56 项组件与 59 个通用函数；复用原组件/样式/动作/生成规则和三个通用示例。Nano 只接消息、状态、身份和资源路由，没有酒店/看板模板。
- pnpm build、pnpm typecheck、前端 build、生成资产 --check 通过。构建有既有/完整库较大 chunk 警告，不冒充资源体积优化完成。
- Web 全量 109 files / 1,036 tests 通过；随后修正 SVG 断言并新增只读 Pressable 回归，最窄 2 files / 15 tests 通过。未将后一次窄测冒充又跑过全量。
- IM 全量最终 45 files / 269 tests 通过；PA 相关 4 files / 47 tests；DSH personal-security/approval 2 files / 17 tests 通过。
- iOS runtime 生成一致性/类型检查通过，native 7 tests 通过；只移动其自有旧语言测试样例，不重写 native 视觉。
- runtime dependency contract 13 tests 通过。新增白名单仅为前端/IM 对 product-contracts/interactive-functions 的公开子入口，不放宽 DSH 依赖边界。
- docs-check 341 maintained Markdown sources / 68 required routes 通过。
- 独立 full review 的两项成立问题均修复，closure `[]`；详情见 code-review.md。

### 真实模型输入、反馈与交付

- 隔离 daily 栈：runtime `output/runtime-openiui`，IM 127.0.0.1:62983；独立 node/data/workspace/identity。PA `pa_ffc9e810cab6`，`codexOAuth:gpt-6-astra` / medium。
- 使用同一用户酒店/看板原图的放大截图。输入消息 `5908a16bea2c484a9044aa19e879e754`（酒店）与 `857e3cae5a1f49aeb874a97c29c5ab7e`（看板）。没有给目标 DSL 或业务模板。
- 初轮交付酒店 `01c79eabe2fe4e7d88d2df682567562e`、看板 `153a4e3830ba412ea1a5fea35d976d2c`。酒店把照片改为 SVG，漏斗因 centered Col 内的 flex/百分比容器宽度为零而不可见；已据实保留，未算成功。
- 实际视觉反馈后，模型自主将漏斗改为通用 SVG，并使用 SearchImage 重做酒店。资源查询本机实测返回 502（Wikipedia unavailable / Image search unavailable），仍显示占位，未算照片成功。
- 再提供五个实际请求已验证 200 / image/jpeg 的 Unsplash 演示 URL，模型通过通用 Image 重新交付；没有把 URL 固化到代码。照片只为视觉演示，不表示对应真实酒店。
- 后续目测发现上游 media Row 自动将拼贴大图压至 200px、看板过高；给模型实际布局反馈后，它用 Grid 调整拼贴并收紧看板。最终酒店 `856882c174c7424799368ff6360406da`；最终看板 `5fed85ffbf924a77bd61e3caaa1eeb89`。
- 最终结果来自真实模型生成与反馈迭代；不是一次生成即像素复刻，也不是手写替换模型交付。

### 最终浏览器操作与视觉观察

- 最终构建重新加载，使用浏览器 screenshot API 保存实际页面，避免系统级截图在 viewport override 下比例不一致。
- 桌面 1440×1000：酒店三张卡片等宽填满一行；三张照片约 316.7px 宽；下方大图 524px，右侧四小图各 260px，恢复左半/右半关系。所有 8 个显示图片实例 complete 且 naturalWidth > 0。
- Book 实测 32px 高、999px 圆角、背景 rgb(13,13,13)，圆形收藏保留；点击收藏显示“已收藏 1”，点击第五缩略图后大图 alt 从“演示照片 2”改为“演示照片 5”。Reset 可恢复。
- 看板具备四项 KPI、三色散点、四级居中色条与连续率；点击 Clicks 显示“Clicks · 310,000”；选择 Europe 后散点三组 opacity 为 0.12 / 1 / 0.12。未增加 Agent 调用或业务动作。
- 手机 390×844：酒店卡片、照片拼贴与看板按窄屏堆叠，documentElement scrollWidth/clientWidth 均为 390，没有整页横向溢出。未另测真实地图/WebGL，未实测 HtmlView 游戏。
- 最终截图本机 `output/playwright/openiui/`：`dashboard-desktop.png`、`dashboard-interaction.png`、`hotel-desktop-top.png`、`hotel-desktop-gallery.png`、`hotel-mobile.png`、`hotel-gallery-mobile.png`、`dashboard-mobile.png`。
- 本机真实消息/source 快照 `output/iui-real-messages.json`，请求/资源探测与日志同 output/。不提交私人原图、截图、运行数据或凭据。未核验对应 provider 原始 wire payload；不据实际交付宣称 wire 保真。

### 剩余边界

- 最终布局/按钮/漏斗已实际改善；照片是替代示例，字体、选中态、比例仍非逐像素等价。
- 公共图片查询在本机失败这一限制仍存在，通用 Image URL 路径已验证；不掩盖为“自动图片查询已验证通过”。
- 未部署、未发布。用户尚未亲自确认本轮最终截图，unit 保留 Active，canonical spec 未提前归并。
