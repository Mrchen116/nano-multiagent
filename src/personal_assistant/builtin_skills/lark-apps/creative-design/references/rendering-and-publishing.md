# HTML 技术与发布参考

仅在实现对应媒介或发布到妙搭时使用。已有应用继续原 app/目录，不为每次迭代创建新 app；发布遵循用户当前授权。

## 编辑器与宿主约束

- 保留语义等价元素的 `data-comment-anchor` 值，重构时随元素移动；不复制到其他元素、不发明新值，只有删除原元素时才删除。
- 页/屏容器使用 `data-screen-label` 定位评论；用户页码从 1 开始。
- HTML 非空元素显式闭合、属性用双引号；不要自闭合 `<div>` 等非空元素。避免 `scrollIntoView` 干扰宿主滚动。
- 需要在线字体时使用妙搭镜像 `https://miaoda.feishu.cn/fonts/css2`，避免 Google CDN 在目标地区不可达。
- 可重排 UI 元素使用 flex/grid + gap，避免 DOM 编辑依赖空白文本节点。视频播放位置可持久化；deck-stage 已由宿主保存页码，无需重复实现。

## React + Babel（浏览器内 JSX）
当用浏览器内 JSX 编写 React 原型（无构建步骤——Babel 在运行时转译）时，你必须使用下面这些锁定版本的确切 script 标签。不要使用未锁定版本（例如 react@18）。要用 React + Babel 时，可直接从本 skill 的 `assets/index.html` 拷贝 HTML 模板起步（`cp <本 skill 所在目录>/assets/index.html <任务目录>/index.html`）——它已带好这三个 script 标签和 `#root` 挂载点，不必手写。

```html
<script src="https://sf3-scmcdn-cn.feishucdn.com/obj/feishu-static/miaoda/coding-unpkg-sdk/react@18.3.1/umd/react.development.js" crossorigin="anonymous"></script>
<script src="https://sf3-scmcdn-cn.feishucdn.com/obj/feishu-static/miaoda/coding-unpkg-sdk/react-dom@18.3.1/umd/react-dom.development.js" crossorigin="anonymous"></script>
<script src="https://sf3-scmcdn-cn.feishucdn.com/obj/feishu-static/miaoda/coding-unpkg-sdk/@babel/standalone@7.29.0/babel.min.js" crossorigin="anonymous"></script>
```

发布前需要对以上 script 路径进行自检，确保它们路径与上述代码完全一致

### 脚本导入
用 script 标签导入你写的任何辅助脚本或组件脚本。`.jsx` 文件必须用 `<script type="text/babel" src="xxx.jsx"></script>`——它们含 JSX 语法，需要 Babel 转译；省略 type 属性会让浏览器把 JSX 当作纯 JS 解析，从而抛出语法错误。纯 `.js` 文件可以用普通的 `<script src="xxx.js"></script>`。避免在脚本导入上使用 `type="module"`——它可能会出问题。

**加载顺序**：`@babel/standalone` 用异步 XHR 拉取外部 `<script type="text/babel" src="...">` 文件，但保证按 DOM 顺序执行——靠前的脚本总在靠后的脚本之前运行。然而，内联脚本（无 `src`）会立即就绪，而外部脚本必须等待网络响应。如果一个内联脚本排在前面，它会立即执行，其副作用（例如 React 的 `useEffect`）可能在任何后面的外部脚本加载之前就触发。把外部脚本放在依赖它们的内联脚本之前。

### 跨文件作用域
每个 `<script type="text/babel">` 在转译后都有自己独立的作用域。要在文件间共享组件，在组件文件末尾把它们导出到 `window`：

```js
// 在 components.jsx 末尾：
Object.assign(window, {
  Terminal, Line, Spacer,
  Gray, Blue, Green, Bold,
  // ... 所有需要共享的组件
});
```

### 样式对象命名
定义全局作用域的样式对象时，给它们起具体的名字。如果你导入了 1 个以上带 `styles` 对象的组件，就会出问题。你必须基于组件名给每个 styles 对象起唯一的名字，比如 `const terminalStyles = { ... }`；或者用内联样式。绝不要写 `const styles = { ... }`。

### 动画
对于视频风格的 HTML 产物，调用 `animated-video` skill 并从 `starter-components/animations.jsx` starter component 起步——不要自己实现时间轴引擎。对于简单的交互原型过渡，CSS transitions 或纯 React state 就够了。

### 原型
- 克制住加"标题"屏的冲动；让你的原型在视口中居中，或做成响应式尺寸（填满视口并留合理边距）。

## Starter Components（起始组件）
现成的 HTML/JS/JSX 脚手架位于 [starter-components](../starter-components/)——需要设备外框（device frame）、幻灯片外壳（deck shell）、画布（canvas）或动画时间轴（animation timeline）时，直接用它们，不要手搓。使用方式：把文件拷进当前任务目录（在任务目录下执行 `cp <本 skill 所在目录>/starter-components/<file> .`——注意 cwd 不会是 skill 目录，要用 skill 目录的实际路径），或读过之后照着改；每个文件顶部都带有自己的用法说明。

- `design-canvas.jsx` — 可平移／缩放的画布，artboard 可重排、可全屏聚焦。
- `deck-stage.js` — 幻灯片 deck 外壳。用于任何幻灯片演示（见「Skills 元信息」中的 Make a deck）。
- `ios-frame.jsx` / `android-frame.jsx` — 带状态栏和键盘的设备边框。
- `tweaks-panel.jsx` — 浮动的 Tweaks 面板＋表单控件（`useTweaks`、滑块、开关、单选、颜色 chips 等）。
- `macos-window.jsx` / `browser-window.jsx` — 桌面窗口外壳（chrome）。
- `animations.jsx` — 基于时间轴的动画引擎（Stage + Sprite + scrubber + Easing）。

## Tweaks
用户可以从工具栏开关 **Tweaks**——一个存在于原型内部的页内控件面板（颜色、字体、间距、文案、布局变体）。不要自己实现它：复用 [tweaks-panel.jsx](../starter-components/tweaks-panel.jsx)；若当前 harness 暴露 `copy_starter_component` 也可用它复制——它接好了宿主协议，并给你 `useTweaks()` 以及现成的控件。这个面板的标题按界面语言来定——英文叫"Tweaks"，中文叫"风格"。把它保持小巧，Tweaks 关闭时完全隐藏，并且用户需要探索样式时再加入相应 tweak。你写在面板里的标签和选项是用户会读到的内容，而非配置——用与 app 其余部分相同的语言书写。

**闭环。** 每个 tweak 都需要一个生产者（面板控件）和一个消费者（对该值作出反应的内容）。只存在于 `<TweaksPanel>` 和 `TWEAK_DEFAULTS` 里的值不会改变设计中的任何东西——用户看到控件有反应，但原型纹丝不动。

## 发布
用户要求发布到妙搭时，使用以下链路获取可访问链接。本 skill 产出的是创意模式（html）应用，发布走本地开发链路：改动 git commit 后推到工作分支 `sprint/default`，再用 `lark-cli apps` 命令发起部署并轮询结果。

**前提**：每个任务目录是一个独立的妙搭 html 应用仓库，独立发布、互不影响；发布序列的所有命令都在**当前任务目录**内执行。任务目录还不是应用仓库（没有 `.spark/meta.json`）时，先完成两步初始化：

```bash
# 1. 创建应用，记下返回的 app_id（app_ 开头）
lark-cli apps +create --name "<应用名>" --app-type html --as user

# 2. 初始化到任务目录：会自动 clone 远端仓库并 checkout 工作分支 sprint/default，
#    无需 git init / git checkout（--dir 不传默认 ./<app-id>；
#    --source-path 可把已写好的产物一并并入，但源码目录不存在时会被静默跳过，用后核对文件确实进了仓库）
lark-cli apps +init --app-id <app_id> --dir <任务目录> --as user
```

初始化后在任务目录内创建 / 修改产物（创意模式是 buildless，源码即产物，`index.html` 放仓库根目录），然后走下方发布序列。

`app_id`（`app_` 开头）从任务目录的 `.spark/meta.json` 读取，或来自 `+create` 的返回 / 用户给出——`cli_` 开头的是飞书应用 ID，绝不能传给 `apps +*` 命令。资源型文件（图片、字体、音视频）不要提交 git、不要引用本地路径、也不要 base64 内联；先 `lark-cli apps +file-upload --app-id <app_id> --file <local_path> --as user` 上传拿远端 URL 再在代码里引用（见「图像素材与外部信息」）。

发布序列：

```bash
# 1. 提交并推到工作分支 sprint/default
#    遇非 fast-forward：先 git pull --rebase origin sprint/default 解决冲突再推，绝不 force-push
git add <本任务文件> && git commit -m "feat: ..." && git push origin sprint/default

# 2. 发起部署（记下返回的 release_id），然后轮询状态直到 finished / failed：
#    publishing → 继续轮询；finished → 输出含可分享的 online_url，直接返回给用户；failed → 按输出中的 error_logs 报告失败原因
lark-cli apps +release-create --app-id <app_id> --as user
lark-cli apps +release-get --app-id <app_id> --release-id <release_id> --as user
```

要点：

- 所有 git 命令必须在**任务仓库根目录**下执行（每条命令先 `cd <任务目录>`，或用 `git -C <任务目录>`）——`git add .` 作用于当前 cwd，在多任务共用的上级根目录里执行会把其他任务的文件也 stage 进来。
- 推送和部署的分支必须是 `sprint/default`：推到其他分支，`+release-create` 会失败。
- `+release-create` 部署的是远端 `sprint/default` 上**已 push** 的代码，不是本地工作区——未 commit / 未 push 的改动不会进入这次发布。
- 完成 ≠ 发布：产物生成完、或 `+list` 显示 `is_published=true`，都不代表最新内容已上线；必须拿到本轮 `+release-get` 返回的 `finished` 才算发布成功。
- 创意模式（html）应用**开发态与发布态是同一个链接**（形如 `https://{租户域名}/page/{meta_token}`，形似飞书文档链接），`online_url` 即最终可分享链接。
- 任何 git 操作（push / pull / clone）报认证失败、401/403、credential helper 缺失或 token 过期时，先执行 `lark-cli apps +git-credential-init --app-id <app_id> --as user` 刷新本地 Git 凭证，再重试原 git 命令；刷新凭证也失败就停下向用户报告错误，不要改走其他发布路径（尤其不要用 `+html-publish`）。

## Skills 元信息
你有以下内置技能 prompt，位于本文件同级目录中。如果用户的需求与其中某个技能匹配，而对应的 prompt 尚未加载进你的上下文，就去 READ（读取）相应文件，把它的指引加载进来。

- **[Animated video](animated-video.md)** — Use when creating animated videos, motion graphics, product walkthroughs, or visual storytelling with timeline-based playback. 触发词：animation, video, motion, 动画, 视频, 动效, 产品演示, 演示动画, walkthrough
- **[Charts](charts.md)** — 基于 ECharts 的数据可视化，用于浏览器直出 HTML。当需要创建图表、仪表盘或数据可视化时使用。触发词：chart, ECharts, 图表, 可视化, visualization, 饼图, 柱状图, 折线图, 数据图表, 甘特图, 热力图, 数据展示, dashboard, 仪表盘, 数据看板
- **[Data report](data-report.md)** — 数据驱动的报表与看板设计。从数据分析到报表规划、信息层级组织，适用于用户有数据文件或明确指标，需要产出结构化数据报表的场景。图表绘制部分由 charts skill 承担。触发词：数据报表, 数据看板, 数据分析报表, BI, 经营报表, 指标看板, 周报, 月报, 数据大盘, KPI, 报表设计, data report, dashboard report, analytics report
- **[Frontend design](frontend-design.md)** — Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults.
- **[Hi-fi design](hi-fi-design.md)** — 用于创建高保真 UI mockup、设计探索，或带多种变体的视觉原型。触发词：mockup, hi-fi, prototype, UI design, 高保真, 设计稿, 原型, 界面设计, 视觉设计, 设计方案
- **[Interactive prototype](interactive-prototype.md)** — 可交互原型：像真实应用一样直接运行的高保真交互 demo。触发词：可交互原型, 交互原型, 点击原型, interactive prototype, working app, 产品 demo, 工单系统, 管理后台, 看板工具, 多页面应用
- **[Make a deck](make-a-deck.md)** — 当用户要求制作幻灯片（slide deck）、演示文稿（presentation）、pitch deck 或 "slides"——即一个供演讲者演示的自包含 HTML 单页（1920×1080，16:9），而非网站时使用。
- **[Visual exposure](visual-exposure.md)** — 用于制作可视化报告、专题视觉页、信息图、视觉长图、概念可视化、产品能力曝光、方案亮点展示等内容型 HTML 视觉作品。适合用户想把材料、数据或观点组织成可阅读、可展示、可传播的视觉化表达，但不希望做成 PPT、传统 dashboard 或纯 ECharts 图表的场景。触发词：可视化报告, 视觉报告, 可视化曝光, 视觉化曝光, 信息图, 长图, infographic, 视觉表达, 概念可视化, 亮点展示, 能力曝光
- **[Wireframe](wireframe.md)** — Explore many ideas with wireframes and storyboards

