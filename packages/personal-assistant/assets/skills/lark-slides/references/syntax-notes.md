# 常见 XML 语法约束

- PPT 的尺寸是 960x540，必须严格确保主体内容在页面边界内。
- 字号必须显式设置 `<content>` 的 `fontSize` 属性，不要依赖 `textType` 的默认字号兜底，这些兜底值明显偏大。
- 大数字、字号大或字数多的 `<content>` 必须设置 `wrap="true" autoFit="normal-auto-fit"` 属性自动换行和缩排，避免文字溢出。
- 文字颜色必须用 `<content>` 的 `color` 属性而不是 `fontColor` 属性。
- 文字行间距必须设置 `<content>` 的 `lineSpacing="multiple:xx"` 或 `lineSpacing="fixed:xx"` 而不是 `lineSpacing="xx"`。
- IconPark 图标必须填充颜色（设置 `<fill><fillColor color="rgba(R,G,B,A)"/></fill>`）并和背景有足够对比。
- 绘制图表时原生图表（柱状、条形、折线、面积、饼（环）、雷达、组合图）用 `<chart>`，其他（漏斗图、金字塔图、象限图、矩阵图等）用 `<shape>` + `<line>` 模拟。
- 隐藏 `<chart>` 的图例只能通过不写或删除 `<chartLegend>` 实现，`<chartLegend>` 不支持 `position="none"`。
- 表格优先用 `rect` 和 `text` 模拟，其他用 `<table>`，没有 `<shape type="table">`。
- 必须设置 `<table>` 的 `width` 和 `height` 固定表格大小，同时设置需要保留列宽或行高的 `<col>` 的 `width` 和 `<tr>` 的 `height`，其余自动分配。
- `<td>` 直接子元素只有 `<fill>`（背景）、`<content>`（文字）和边框配置（一般不用），不能嵌套 `<shape>`、`<img>`、`<icon>`。
- `<shape type="rect">` 只是形状不是容器，`<icon>`、`<img>`、`<shape type="text">` 和其他 `<shape>` 必须与它平级靠坐标叠放。
- 填充渐变颜色必须用 `<fill><fillColor color="linear-gradient(135deg, rgba(R,G,B,A) 0%, rgba(R,G,B,A) 100%)"/></fill>`。
- 卡片结构：视觉锚点（关键词、编号或 IconPark 图标）+ 标题 + 内容（包括文字、图片、图表、子卡片）。
- 图标：内嵌 IconPark 图标（可用关键词或编号替代）作为视觉锚点，让高密度文字也有图形节奏，而不是成片纯文字块。
