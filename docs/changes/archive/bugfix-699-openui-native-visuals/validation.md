# bugfix-699 验证记录

状态：Archived；用户已授权合并当前实现范围。以下各批记录保留当时状态，当前交付边界以末尾“合并收尾”为准；不将失败改写为通过。

## 已执行

- Base: 95c6b3deb07c03e9edd3b78375cd0ae29e87558e，独立 worktree，不含主仓已有 dirty 内容。
- Node 24.22.1，pnpm 11.7.0；pnpm build、pnpm typecheck 通过。
- frontend interactive 相关 3 个文件、22 个测试通过；生成资产 --check 通过。
- DSH capabilities 4 个测试通过。该检查不代表真实模型已消费新指导。
- 用户原图：酒店消息 b437225bf1fc482fa94a718969ec9302；看板消息 ef4f7762a9f94765957e485aa90a9025。只读浏览器放大截图留本机 output/playwright/openui-native/，未改生产消息。
- 隔离 daily 栈已启动，自己的端口/identity/data/workspace，真实模型与视觉结果待补。

## 用户验收

用户于2026-11-03明确要求合并当前PR。此前自验和已知视觉限制保留；该授权不改写为全部视觉通过。

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

## 用户指出通用按钮重复后的修正

- 用户问每张卡片右上角叉和右下角 Reset 的用途。两者是本轮模型生成的局部收起/恢复初始选择，不是宿主或上游要求每张卡片必须有。
- 短 policy 与长生成规则改为不默认追加通用 Close/Reset/toolbar；需要重置时按具体任务命名。不删除组件或动作能力。
- 真实模型新交付酒店 `62ca9afbab25417cbb1f339e49f0cf50` 与看板 `4444a44a1cd94a979655a86425852116`。源程序对比仅删除关闭/重置及其外壳，保留布局、照片、收藏/切换、地区筛选与漏斗阶段交互。
- 窄 patch 独立 review `[]`；资产一致性检查通过，DSH capabilities 4 tests 通过。
- 最后 Chrome 预览控制超时，改用内置浏览器继续同一隔离服务；重新登录并在 1440×1000 断点实际核对：新酒店/看板的 Close/Reset 按钮数量均为 0；酒店收藏仍显示“已收藏 1”，看板点击 Clicks 仍显示“Clicks · 310,000”。
- 新截图：`output/playwright/openiui/hotel-no-extra-controls.png`、`dashboard-no-extra-controls.png`；旧截图作为反馈前历史证据保留，不冒充最新版本。内置浏览器已恢复尺寸并关闭测试页。

## 清空上下文后的独立复测（2026-11-02，最新现场）

### 方法与结论

用户明确要求“清空聊天记录，重新测，不要累计着记录测。前后会有干扰”，并要求测试完保留服务供亲自试用。本节替代前述累积反馈结果作为**首次生成**表现的证据；旧证据作为历史保留。

使用 product-tryout：基线 `afd3ef0bc`，开测前 checkout clean，重新 build；三个 daily 隔离实例分别有新 IM 数据库、测试身份、PA、node identity、workspace 和 DSH home。每场景的消息 API 初始结果均为 `[]`。酒店/看板只发一次初始请求，不追加修正提示，不手写或替换模型 source；确认场景只增加同一旅程所需的一次真实确认。

模型均为模板 PA `codexOAuth:gpt-6-astra` / medium。酒店初始输入含用户原图及五个已验证照片素材 URL；这属于资源输入，未提供目标 DSL、布局参数或上一轮修改过程。看板仅附用户原图与普通复现要求。图片上传通过公开 API，确认任务发起、选择、提交与所有交互核对通过真实 Web。

结论：确认后回复能力在干净上下文中完整通过；桌面看板首次即画出四级居中漏斗并支持交互。酒店仍有卡片区域留白；手机看板有明显可读性问题。不能把上一轮经过多次反馈修正的结果当成首次生成稳定性证明。

### 确认回复旅程：直接成功证据

- node `wt-runtime-openiui-13132`，PA `pa_11c64498a06e`，聊天 `c_f904c9b5844a`；原生 session `bf56b25a-6e39-4570-874c-15423d4be460` 只有本轮 1/2 两个完成 turn。
- 初始请求 `8c800fcb869247d8bc38613ceab5808a`，交互卡片 `e0e12757ca264a208acee4d3c8e32757`；未选时间/时长时“确认选择”不可点。
- 实际选择“周四下午3点”“60分钟”，编辑备注为“带上预算草案”。确认前公开记录仍只有初始请求和卡片，没有因编辑自动发消息。
- 点击“确认选择”生成用户消息 `08cb6841473f422290ab32073cf7b932`，event context、完整 state 和带可读标签的 fields 均包含上述最新三项值。
- Agent 回复 `21b7447386544537993aa524b27ff4bc` 准确复述三项选择，并明确未创建真实日程。不是只看 HTTP 成功或本地回调；实际消息已送达、Agent 后续处理并在 UI 显示。
- 最终聊天仅本轮 4 条消息：请求、卡片、确认、Agent 回复。截图 `output/playwright/openiui-clean/confirm-{empty,before-submit,agent-reply}.png`；公开记录快照 `output/clean-iui/confirm-{empty,edited-not-submitted,submitted,complete,final}.json`。

### 酒店首次生成与发现 UI-CLEAN-1

- node `wt-runtime-openiui-clean-hotel-13379`，PA `pa_ab45d6c70cc3`；session `38a38e81-f4ea-4436-a68f-8c6f39787e7f` 只有 turn 1。聊天 `c_4718644999af`，请求 `48808fa8b075407697d7fcad2c5e5943`，交付 `a4f7481228b84df3a9e8185a87b28566`。
- 8 个显示照片实例均 complete 且 naturalWidth > 0；拼贴左大图 523px、右四图各 259.5px。收藏实际 aria-pressed false → true；点击第五张缩略图显示“照片 5 / 5”与大图，收起可恢复。不产生额外公开消息。
- UI-CLEAN-1（现象已证实，生成布局选择）：桌面卡片仍使用固定 232px Carousel，三张图各 214px，宽聊天中右侧留白明显，与参考及前轮经过反馈铺满三列的结果不同。source 明确固定 itemWidth，未观察宿主重新覆盖皮肤。不凭单样本声称普遍失败率；未修改本次结果。
- 最终仅一次请求 + 一张卡片；没有上一轮布局反馈。截图 `output/playwright/openiui-clean/hotel-{first-pass,photo-interaction}.png`，source / 消息在 `output/clean-iui/hotel-*`。本次没有专项复测酒店手机布局。

### 看板首次生成与发现 UI-CLEAN-2

- node `wt-runtime-openiui-clean-dashboard-13490`，PA `pa_e6f2091125f5`；session `b30137e1-ddd3-4fbe-aeb1-6d9ab354f347` 只有 turn 1。聊天 `c_b101f7e09046`，请求 `e5f3928627a346c8ad5384f5c6b90f27`，进度提示 `b37a589315074dc7aedd101f68a66899`，卡片 `3120be0cb9fc4ef4afc695a2d55ff55d`。
- 1440×1000：四项指标、三色散点、四级居中色条及连续率实际可见，没有零宽色条问题。Europe 开关令三组 opacity 1/1/1 → 1/0/1；点 Clicks 展示“Clicks · 310,000（演示）”及“占初始曝光的 7.38% · 下一阶段转化率 13.5%”。真实数值、事件与展示一致。
- UI-CLEAN-2（现象与布局机制已证实，P2/生成内容）：390×844 仍将两张图并排压缩，散点宽约 138.5px，漏斗 SVG 宽约 81.5px，图中文字几乎不可读；首个 KPI 也出现 Mn 断行。虽然 document scrollWidth=390 无整页溢出，**不能据此称手机适配通过**。
- source 的 panels 为 Box row/wrap，两个子 Box 使用 flex 1.7/1，没有窄屏最小列宽或切换为单列的条件；渲染器按该程序布局。Generic Grid minChildWidth 等能力可表达窄屏堆叠，但本次生成未使用。未观察组件硬性表达限制，不归咎为官方无法画漏斗。
- 保留初次结果，不追加“手机改为堆叠”提示。仅一次用户请求，最终 3 条公开消息（含进度提示）；本地筛选/阶段点击不新增消息。截图 `output/playwright/openiui-clean/dashboard-{first-pass,interaction,mobile-first-pass}.png`；消息/source 在 `output/clean-iui/dashboard-*`。

### Context 与未覆盖边界

- `output/clean-iui/native-summary.json` 保存不同 node/PA/session、各自仅有的本轮 turn 及实际 Skill 加载记录。物理隔离和初始空记录是去除历史干扰的证据；不是仅隐藏 Web 聊天。
- 未另核 provider 原始 wire payload；不把原生 run/Skill 记录冒充 wire 保真。未在本次重复群聊、离线、幂等冲突或 native iOS 旅程。
- 本次没有产品代码/提示词修改，也没有用已修结果覆盖原始生成结果。发现供用户亲自检查后决定后续修复。

### 用户要求保留的服务

用户明确说“测试完不要关服务，我去亲自看看”，因此三个受控服务与对应预览页保持运行，未按通常试用结束规则停止。当前 health / 消息数量见 `output/clean-iui/retained-services.json`。运行配置、凭据和原始材料仅留本机 output，不提交。

- 确认回复：`http://127.0.0.1:50985/chat/c_f904c9b5844a`，runtime `output/runtime-openiui`，启动 session `openiui-clean-confirm`。
- 酒店：`http://127.0.0.1:51193/chat/c_4718644999af`，runtime `output/runtime-openiui-clean-hotel`，启动 session `openiui-clean-hotel`。
- 看板：`http://127.0.0.1:51507/chat/c_b101f7e09046`，runtime `output/runtime-openiui-clean-dashboard`，启动 session `openiui-clean-dashboard`。

后续停止时对各自 runtime 执行配对 e2e-down；不要误停生产或其他工作区。unit 仍 Active，用户尚未验收；开发 worktree 保留，未部署或发布。

## 短常驻选择与设计指导候选（2026-11-02）

- 用户确认约100词英文指导后，仅替换公共 `intelligent-ui.ts` 的选择/设计段落：降低理解负担、复杂信息主动UI、先选信息结构/布局/可视化、美观舒适；保留后半段状态、真实性、权限和root/child交付规则。未改Skill语法、解析器、发布校验或固定case。
- `@nano/dsh-integration` build通过；communication-native 1 file / 2 tests通过；docs-check 282 maintained Markdown sources / 68 required routes通过；git diff --check通过。独立Context审查见code-review.md。
- 同一dataset v4广告case，固定CSV SHA `7c7f5806be03dfb44d8d3eaa26f54df34c3f2e74d952f3076a7e9b04b248608a`。新隔离runtime `output/runtime-eval-20261102-03`，新PA `pa_db62538c9822`，SID `f57cea98-164a-4e0a-84f2-bfbd8f9d87b0`；codexOAuth:gpt-6-astra / medium，初始0消息、workspace预置文件、无附件，唯一自然任务不含UI要求。旧trial02纯文字基线保留。
- **本次usedUI=true**：主动加载nano-interactive-ui，1次send_message带interactive.source，公开卡片 `32c97b56201c41bda58c8bfd86bfdc51`；共8次工具、0工具错误、1个完整完成turn。旧自然任务基线usedUI=false；单次对照不能外推稳定采用率。
- **视觉未通过**：实际桌面及390×844均看到空图，12根柱高为0；转化表每行四格重复20%或5%。周次切换能本地更新流失表，切回后公开消息仍3条，没有额外模型调用。正文很长且重复UI，没有达到简短摘要/降低理解负担的目标；不评分业务分析准确率。
- 只读诊断确认生成的未引号中文对象key/属性被解析为“?”，四个key互相覆盖；Chart按中文series读不到值。parser仍meta.errors=[]。与前一用户显式UI追问的空图同类，本次保留原始失败，没有修改消息、重试或混入解析修复。
- 原始证据留本机 `output/eval-ad-analysis-20261102-03/`：baseline、完整work/turn-items/messages、generated.oui、native-session.jsonl、actual-system-prompt.txt、chart-ast.json、result.png/mobile.png、result.json/report.md。native seq9实际包含新指导且旧表格偏好消失，不等同provider wire抓包。
- 服务按用户要求保留：`http://127.0.0.1:56319/chat/c_f693beacf0d1`；原trial02与酒店/看板/会议均未停止。此次为Agent自验，unit仍Active，未冒充用户验收、部署或发布。

## 发布前检查与可修正诊断（2026-11-03）

- Base / executed_base：`b26bcff02320a7d8d889f0c21addbf41eeaeae95`。保留官方可用诊断，使用公开SDK初始状态求值与参数校验，不修改上游parser/目录/生成指导，也不安装浏览器或调用纠错模型。
- 最窄发送链验证7files / 85tests通过，覆盖静态enum、状态计算后的enum、函数参数错误，HTTP业务错误/原子持久化、真实IM进程WebSocket拒绝→修正新调用成功、Channels detail、Global及私人PA明确拒绝与诊断、原生模型下一次请求包含工具错误及定位字段。原生测试是受控model stub，验证实际Context序列化，不声称真实模型自主修正或provider wire抓包。
- IM、PA、Channels build，IM typecheck通过；runtime dependency contract 13tests、docs-check 282 maintained Markdown sources / 68 required routes、git diff --check通过。本机日志留 `output/ui-preflight/`。
- IM/PA/Channels非E2E扩展回归83files / 631tests通过；另personal-images的3项因仍用旧nano-1/TextContent而在进入本轮校验前失败。仅迁移该测试输入为现有Image/nano-iui-1，图片实现不改；该文件4tests窄复测通过。未将修正后的窄复测冒充重新运行全量。
- 只读重校验已有酒店、看板、会议与本次广告source均接受。此前广告空图仍能通过官方parser，未修或伪称解决静默吞错；原消息和截图不改。Query无defaults时数据未知，快照参数检查延后；不保证未来所有交互状态或浏览器视觉。
- 本轮无产品前端改动，不重跑视觉评分；没有停止或重启用户保留的预览，未部署生产。unit继续Active，独立审查记录见code-review.md。
- 独立审查发现初始快照误拒未初始化Input/TextArea/Checkbox，修复为不将快照null-required当作确定错误；原程序字面null仍拒绝，并存的非null错误仍拒绝。最终source+PA两文件47tests通过，覆盖空输入与共享PA明确拒绝。旧图片fixture迁移窄测4/4通过。
- 同PR上一head的远端CI还暴露前端job仅npm ci、未安装新共享contracts的lang-core/zod依赖，编译失败。补pnpm frozen workspace安装步骤，保留原前端安装/编译/审计/测试；不改变产品代码或依赖版本。后端旧图片fixture失败与前述同因。此次提交不冒充此前远端CI已绿。

## 无消费者JSON目录清理（2026-11-03）

- 用户明确要求删除后，移除integration的3518行catalog.json及生成脚本对应输出/检查项。检索没有运行时或打包消费者；IM共享TS目录、Agent Skill和其他生成文件不改，无spec delta。
- 生成资产`--check`、docs-check、git diff --check通过；删除路径在实现/脚本/配置中无剩余引用。不为纯产物清理新增测试或重复模型/视觉评测。预览服务与worktree保留，unit仍Active。

## 合并收尾（2026-11-03）

用户明确要求“merge 吧”，按当前PR实现范围交付；保留原失败结果与未解决项，不将合并授权写成像素还原或全部视觉通过。最终源码head为4b58b4704；同步origin/main后无增量，effective_base=9cb67e17e，既有实现及相关测试/独立审查结论保留。本轮仅归并行为说明与整体归档，无新增实现或模型行为变化；CI以最终归档提交的实际结果为准。

Web交互delta已归并到docs/specs/im/web-chat-ux.md。用户要求保留预览，因此合并后仍保留服务和开发worktree；后续停止预览并核对证据保存后再清理。
