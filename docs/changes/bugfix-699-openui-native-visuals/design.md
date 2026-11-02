# bugfix-699: As-built Design

> 实现后按最终范围整理；用户已要求从恢复样式扩大为接入 Open Intelligent UI，并明确不考虑后向兼容。用户视觉验收尚未完成。

## 实现范围

- Base / executed_base: `95c6b3deb07c03e9edd3b78375cd0ae29e87558e`
- Branch: `codex/openui-native-visuals`
- 上游：[thesysdev/open-intelligent-ui](https://github.com/thesysdev/open-intelligent-ui)，固定 commit `16ef26475999e3a021a50b1607a03717c0721255`，MIT；源码目录带 LICENSE，前端 UPSTREAM.md 记录适配。

## 最终结构与调用链

- Web 的 `interactive/open-intelligent-ui/` 复用上游全部组件、样式、动作、通用布局/绘图和 prompt options。包含 Box/Grid/Row/Col、SVG shapes、HtmlView、地图、图片、图表与本地控件；没有酒店或广告看板专用模板。
- 删除 Nano theme、组件皮肤覆盖及旧 Web composition examples。ThemeProvider 保留默认 light token；宿主只提供聊天阅读空间、状态与权限反馈。
- 上游通用函数放在 product-contracts 的显式 `interactive-functions` 子入口，使用 lang-core 定义，Web registry 与 IM source validator 共享同一实现。IM/前端不跨包相对导入、不依赖 DSH。
- catalog.tsx 在上游 library 上只增加 ComposeMessage，保留 Nano conversation_messages / continue_conversation 两个已接工具；不把上游 demo 数据工具伪装成真实业务工具。生成指导保留上游三个通用 worked examples，并补 Nano 消息/状态/授权协议、参考布局与百分比容器尺寸规则。
- 生成链：catalog → generate-interactive-ui.ts → frontend types、product-contracts intelligent-ui-catalog、integration catalog/prompt、PA nano-interactive-ui Skill。生成器仅加载 schema，忽略 CSS 模块；auth 资源适配按需加载，生成时不执行浏览器登录逻辑。
- 新协议版本 `nano-iui-1`，发布端自动填常量。Web/IM 使用新目录；未提供旧 Web DSL 转换/兼容。旧 native runtime 目录及其测试样例独立保留，iOS 本轮不重写视觉，新卡片按其既有版本检查显示摘要/不支持提示。
- IM 用共享目录验证 source、绑定类型、已接 Query/Mutation 与 ComposeMessage 约束；提交/私聊背景从响应式输入产生可读字段，解析普通命名 label/options 与 Query defaults，原始完整 state 仍保留。
- `/im/v1/intelligent-ui/api/{wiki,image-search,street-route}` 将上游固定公共资源处理函数接到现有身份认证与频率限制。前端通过现有 authFetch 请求；查询失败保持上游错误，不伪造照片或路线。
- HtmlView 复用上游 opaque-origin sandbox/CSP，不获得宿主凭据/工具；内部编辑不进入 Nano 共享状态。需要保存或提交的选择使用响应式控件。
- 非原生 Pressable 与 map marker selection 增加遵守宿主 disabled fieldset 的最小适配；既有服务器权限、私聊/群聊状态边界、幂等重试继续保留。

## 风险与回滚

- 用户明确不要求后向兼容；旧 Web 程序不保证继续渲染，已发布文字摘要仍可阅读。没有数据迁移或安装包发布。
- 远端公共图片/地图资源可失败；本机实际图片查询返回 502，酒店最终视觉测试使用事先验证可加载的演示照片 URL。不能将这当成图片查询成功。
- 模型可以组合任意通用布局与绘图，不等于一次生成就忠实还原。真实模型首轮和反馈修正均保留证据，不用手写业务模板替代实际模型结果。
- 回滚本轮源码、依赖锁和生成资产可恢复旧 registry；本轮没有改生产数据。

## 验证与状态

见 [validation.md](validation.md) 和 [code-review.md](code-review.md)。用户确认前保留 Active，行为 delta 保留在本 unit，不提前归并 canonical。

## 后续 as-built：公共表达选择指导

- 采用用户确认的约100词英文选择/设计策略，替换intelligent-ui.ts中旧比较优先简单表格及长生成入口说明；按理解负担选择形式，复杂信息即使未点名界面也主动用UI，先设计信息组织与视觉舒适。
- 保留同段后的ComposeMessage/ToAssistant、本地状态、群聊隐私、数据真实性、授权及root/child交付边界；Feature开关与按需Skill机制不变。没有给广告case添加UI提示或题目专用规则。
- 此处为候选生成指导更新，dataset v4与CSV不变；沿用evals的独立上下文协议复测。没有搭配修复此前中文裸键导致空图的解析缺口，以保持本轮变更范围可审。
