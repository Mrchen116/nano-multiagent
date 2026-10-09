# 操作与参数参考

按本次操作查对应章节；不要求顺序通读。命令中的相对工作文件路径以执行命令的 cwd 为准，Skill 自带文件从 Skill 目录定位。

# slides (v1)


视觉设计可查 [visual-style](visual-style.md)，元素约束查 [syntax-notes](syntax-notes.md)。

## Quick Reference

**本表只定位「场景 → 用哪条命令、读哪份文档」。参数以「执行前必做」里对应的文档和 `lark-cli slides +<verb> --help` 为准，不要凭记忆或按别的命令类比补参数。**

| 用户需求 | 优先动作 | 关键文档 / 命令 |
|----------|----------|-----------------|
| 新建 PPT | 先规划 `slide_plan.json`，再按复杂度选择一步或两步创建 | `planning-layer.md`、`visual-planning.md`、`asset-planning.md`、`lark-slides-create.md`、`slides +create`、`slides +add-slide`、`lark-slides-add-slide.md`（两步创建逐页添加） |
| 用户要求使用模板，或提供 PPTX 文件要求修改、美化 | 将模板导入为 Slides 再编辑 | `lark-slides-pptx-template-workflows.md` |
| 编辑单个标题、文本块、图片或局部元素 | 优先块级替换/插入，不改页序 | `slides +replace-slide`、`lark-slides-replace-slide.md` |
| 给已有 PPT 追加或插入页面 | 一次一页，`--slide` 支持 `@file` 绕开 shell 转义 | `slides +add-slide`、`lark-slides-add-slide.md` |
| 删除页面 | 按 `slide_id` 单页删除，删前先回读确认 | `slides +delete-slide`、`lark-slides-delete-slide.md` |
| 读取或分析已有 PPT | 解析 slides/wiki token，用 shortcut 回读全文 XML 或读取单页 XML，保存 `xml_presentation_id`、`slide_id`、`revision_id` | `slides +xml-get`、`xml_presentation.slide.get`、`lark-slides-xml-presentations-get.md` |
| 查看或回滚历史版本 | 先用 `+history-list` 找 `history_version_id`，再 `+history-revert`，必要时 `+history-revert-status` 轮询 | [`lark-slides-history.md`](lark-slides-history.md) |
| 获取幻灯片页面截图 | 用 `slide_id` 或页号指定页面，一次不超过 10 页 | `slides +screenshot`、`lark-slides-screenshot.md` |
| 上传或使用图片 | 先上传为 `file_token`，禁止直接写 http(s) 外链 | `slides +media-upload`、`lark-slides-media-upload.md`，或 `+create --slides` 的 XML 里写 `<img src="@./path">` 占位符 |
| 绘制图表 | 原生图表（柱状、条形、折线、面积、饼（环）、雷达、组合图）用 `<chart>`，其他（漏斗图、金字塔图、象限图、矩阵图等）用 `<shape>` + `<line>` 模拟 | `xml-schema-quick-ref.md`、`slides_chart_demo.xml` |
| 绘制表格 | 优先用 `rect` 和 `text` 模拟，其他用 `<table>` | `xml-schema-quick-ref.md` |
| 使用图标 | 禁止盲猜 iconType，必须先检索 IconPark，再写 `<icon iconType="...">`，图标必须填充颜色并和背景有足够对比，禁止使用 emoji 图标 | `iconpark_tool.py search → resolve`、`iconpark.md` |
| 创建失败、空白页、3350001、布局异常 | 先回读状态，再按排障清单修复，不假设原操作原子成功 | `troubleshooting.md`、`validation-checklist.md` |


**CRITICAL — 查看或回滚历史版本前，MUST 先读取 [`lark-slides-history.md`](lark-slides-history.md)。回滚接口只接受 `history_version_id`，不要把 `revision_id` 直接传给 `+history-revert`。**

XML 结构不明确时查 [xml-schema-quick-ref.md](xml-schema-quick-ref.md)，禁止凭记忆猜测 XML 结构。**

多页设计需要持久中间状态时参考 [planning-layer](planning-layer.md)；有具体布局/素材问题再查 [visual-planning](visual-planning.md) / [asset-planning](asset-planning.md)。



**CRITICAL — 将完整 `<slide>` XML 提交给 `slides +create --slides`、`slides +add-slide`、`xml_presentation.slide create` 或 `slides +replace-pages` 之前，MUST 先把待提交 XML 保存到本地文件并运行唯一版式准出入口 [`scripts/xml_text_overlap_lint.py`](../scripts/xml_text_overlap_lint.py)；`summary.error_count` 必须为 0 才能调用接口。**

**CRITICAL — 创建或大幅改写后，MUST 按 [validation-checklist.md](validation-checklist.md) 做显式验证：回读全文 XML、核对页数和关键元素，并使用 [`scripts/xml_text_overlap_lint.py`](../scripts/xml_text_overlap_lint.py) 统一检查 XML、越界、重叠、空白页和内容稀疏风险。**

出现对应错误或布局风险时，按 [troubleshooting.md](troubleshooting.md) 检查 XML 转义、结构、shell 截断、图片 token、3350001 和布局风险。**

**编辑已有幻灯片页面**：单个标题、文本块、图片或局部元素优先用 [`+replace-slide`](lark-slides-replace-slide.md)（块级替换/插入，不动页序）；已有 Slides 的多页大改优先用 [`+replace-pages`](lark-slides-replace-pages.md) 在原 presentation 内批量重建页面，避免 `slides +create` 生成新链接。选择 action 和完整读-改-写流程见 [`lark-slides-edit-workflows.md`](lark-slides-edit-workflows.md)。

**用户要求使用模板**：按 [lark-slides-pptx-template-workflows.md](lark-slides-pptx-template-workflows.md) 处理。

## 身份选择

飞书幻灯片通常是用户自己的内容资源。**默认应优先显式使用 `--as user`（用户身份）执行 slides 相关操作**，始终显式指定身份。

- **`--as user`（推荐）**：以当前登录用户身份创建、读取、管理演示文稿。执行前先完成用户授权：

```bash
lark-cli auth login --domain slides
```

- **`--as bot`**：仅在用户明确要求以应用身份操作，或需要让 bot 持有/创建资源时使用。使用 bot 身份时，要额外确认 bot 是否真的有目标演示文稿的访问权限。

**执行规则**：

1. 创建、读取、增删 slide、按用户给出的链接继续编辑已有 PPT，默认都先用 `--as user`。
2. 如果出现权限不足，先检查当前是否误用了 bot 身份；不要默认回退到 bot。
3. 只有在用户明确要求"用应用身份 / bot 身份操作"，或当前工作流就是 bot 创建资源后再做协作授权时，才切换到 `--as bot`。

## 操作参考

> **重要**：`references/slides_xml_schema_definition.xml` 是此 skill 唯一正确的 XML 协议来源；其他 md 仅是对它和 CLI schema 的摘要。

高频只读：

- [xml-schema-quick-ref.md](xml-schema-quick-ref.md)
- [planning-layer.md](planning-layer.md)（新建 / 大幅改写）
- [visual-planning.md](visual-planning.md)（新建 / 大幅改写）
- [asset-planning.md](asset-planning.md)（新建 / 大幅改写）
- [validation-checklist.md](validation-checklist.md)（创建 / 大幅改写后）

调用相关命令前必须读取相关的文档以了解命令的使用方式：

- 创建：[`lark-slides-create.md`](lark-slides-create.md)、[`lark-slides-add-slide.md`](lark-slides-add-slide.md)（逐页添加 / 给已有 PPT 追加页面）
- 删除页面：[`lark-slides-delete-slide.md`](lark-slides-delete-slide.md)
- 阅读：[`lark-slides-xml-presentations-get.md`](lark-slides-xml-presentations-get.md)
- 编辑：[`lark-slides-edit-workflows.md`](lark-slides-edit-workflows.md)、[`lark-slides-replace-slide.md`](lark-slides-replace-slide.md)、[`lark-slides-replace-pages.md`](lark-slides-replace-pages.md)
- 历史版本：[`lark-slides-history.md`](lark-slides-history.md)
- 截图：[`lark-slides-screenshot.md`](lark-slides-screenshot.md)
- 图片：[`lark-slides-media-upload.md`](lark-slides-media-upload.md)
- 图表：[`slides_chart_demo.xml`](slides_chart_demo.xml)
- 图标：[`iconpark.md`](iconpark.md)、[`scripts/iconpark_tool.py`](../scripts/iconpark_tool.py)
- 排障：[`troubleshooting.md`](troubleshooting.md)
- 完整协议：[`slides_xml_schema_definition.xml`](slides_xml_schema_definition.xml)


## Workflow

### 生成流程

```text
Step 1: 需求分析 & 读取知识
  - 分析主题、受众、页数、风格；
  - 若用户要求使用模板，按 lark-slides-pptx-template-workflows.md 处理
  - 读取 xml-schema-quick-ref.md；新建 / 大幅改写时还要读取 planning-layer.md、visual-planning.md、asset-planning.md
  - 涉及图表读取 slides_chart_demo.xml

Step 2: 生成大纲 → 写入 slide_plan.json
  - 生成结构化大纲
  - 多页任务需要中间状态时创建独立 plan 目录并保存 `slide_plan.json`
  - plan 字段、路径命名和 `asset_need` 结构按 planning-layer.md / asset-planning.md 执行

Step 3: 按 slide_plan.json 生成 XML → 创建
  - 逐页消费 plan：key_message 定主结论，layout_type 定几何，visual_focus 定主视觉，text_density 定文本量
  - 缺素材时采用符合内容语义的替代方案，不伪造实际图片或证据
  - 读 lark-slides-create.md 定一步创建还是两步创建，并据此构造 `slides +create`；两步创建再读 lark-slides-add-slide.md 用 `+add-slide` 逐页添加
  - 图片按 lark-slides-media-upload.md 处理；复杂 XML、转义和 3350001 排查按 troubleshooting.md 执行

Step 4: 审查 & 交付
  - 创建完成后，必须用 `slides +xml-get --presentation <xml_presentation_id>` 读取全文 XML，并按 validation-checklist.md 做显式验证记录，包括 XML 文本重叠检查
  - 失败或部分成功按 troubleshooting.md 处理；局部问题优先用 `+replace-slide` 修正
  - 没问题 → 交付：使用 NotifyHuman 工具交付 PPT 链接
```

> 渐变色必须使用 `rgba()` 格式并带百分比停靠点，如 `linear-gradient(135deg,rgba(15,23,42,1) 0%,rgba(56,97,140,1) 100%)`。使用 `rgb()` 或省略停靠点会导致服务端回退为白色。

### 大纲模板

生成大纲时使用以下格式：

```text
[PPT 标题] — [定位描述]，面向 [目标受众]

页面结构（N 页）：
1. 封面页：[标题文案]
2. [页面主题]：[要点1]、[要点2]、[要点3]
3. [页面主题]：[要点描述]
...
N. 结尾页：[结尾文案]

风格：[配色方案]，[排版风格]
```

## 核心概念

### URL 格式与 Token

| URL 格式 | 示例 | Token 类型 | 处理方式 |
|----------|------|-----------|----------|
| `/slides/` | `https://example.larkoffice.com/slides/xxxxxxxxxxxxx` | `xml_presentation_id` | URL 路径中的 token 直接作为 `xml_presentation_id` 使用 |
| `/wiki/` | `https://example.larkoffice.com/wiki/wikcnxxxxxxxxx` | `wiki_token` | ⚠️ **不能直接使用**，需要先查询获取真实的 `obj_token` |

> 带 `--presentation` 的 slides shortcut 都会自动解析以上两种 URL；直接调用原生 API 时仍需手动解析 wiki 链接。

### Wiki 链接特殊处理（关键！）

知识库链接（`/wiki/TOKEN`）不能直接当 `xml_presentation_id`。直接调用原生 API 前，先查询 wiki 节点，确认 `node.obj_type == "slides"`，再用 `node.obj_token` 作为真实 presentation ID。

```bash
lark-cli wiki spaces get_node --as user --params '{"token":"wiki_token"}'
```

带 `--presentation` 的 slides shortcut 都会自动解析 `/wiki/` URL 并校验 `obj_type`；手动调用 `xml_presentations.*` / `xml_presentation.slide.*` 时才需要自己做这一步。

### 资源关系

```text
Wiki Space (知识空间)
└── Wiki Node (知识库节点, obj_type: slides)
    └── obj_token → xml_presentation_id

Slides (演示文稿)
├── xml_presentation_id (演示文稿唯一标识)
├── revision_id (版本号)
└── Slide (幻灯片页面)
    └── slide_id (页面唯一标识)
```

## Shortcuts 与 API

Shortcut 是对常用操作的高级封装（`lark-cli slides +<verb> [flags]`）。有 Shortcut 的操作优先使用。

| Shortcut | 说明 |
|----------|------|
| [`+create`](lark-slides-create.md) | 创建 PPT，可选一步添加页面 |
| [`+add-slide`](lark-slides-add-slide.md) | 向已有演示文稿追加或插入**一页**（`--before-slide-id` 控制位置），XML 支持 `@file` / stdin，`<img src="@./path">` 占位符自动上传 |
| [`+delete-slide`](lark-slides-delete-slide.md) | 按 `slide_id` 删除**一页** |
| [`+xml-get`](lark-slides-xml-presentations-get.md) | 读取全文 XML，用 `--presentation` 指定演示文稿的 `xml_presentation_id`，用 `--output` 把 XML 存到本地文件（必须是 CWD 内的相对路径，如 `.lark-slides/plan/<deck>/readback.xml`） |
| [`+screenshot`](lark-slides-screenshot.md) | 把幻灯片页面截图保存为本地图片，用 `--slide-number` 指定页号（从 1 开始，多页重复传入，一次最多 10 页），用 `--output-dir` 指定保存目录（必须是 CWD 内的相对路径，默认 `.lark-slides/screenshots`），失败时降级到 XML 回读等非截图检查 |
| [`+media-upload`](lark-slides-media-upload.md) | 上传本地图片到指定演示文稿，返回 `file_token`（用作 `<img src="...">`），最大 20 MB |
| [`+replace-slide`](lark-slides-replace-slide.md) | 对已有幻灯片页面进行块级替换/插入（`block_replace` / `block_insert`），自动注入 id 和 `<content/>`，不改变页序 |
| [`+replace-pages`](lark-slides-replace-pages.md) | 在原演示文稿内批量重建多个页面：先创建新页到旧页前，再删除旧页；适合已有 Slides 的多页大改，不新建链接 |

没有 Shortcut 覆盖时使用原生 API。高频资源：`slides +xml-get` 读取全文；`xml_presentation.slide.create/delete/get/replace` 管理单页。

```bash
lark-cli schema slides.<resource>.<method>   # 参数不明确时查询 method schema
lark-cli slides <resource> <method> [flags] # 调用 API
```

> **重要**：原生 API 参数不明确时，运行 `schema` 查看 `--data` / `--params` 参数结构，不要猜测字段格式。

## 核心规则

1. **先规划再写 XML**：新建演示文稿或大幅改写页面时，必须先写入 `.lark-slides/plan/<deck-or-task-id>/slide_plan.json`；模板、风格和大纲只能作为规划输入，不能绕过规划层
2. **创建流程**：新建演示文稿用 `slides +create`，一步创建还是两步创建按 [`lark-slides-create.md`](lark-slides-create.md) 判断
3. **`<slide>` 直接子元素只有 `<style>`、`<data>`、`<note>`**：文本和图形必须放在 `<data>` 内
4. **文本通过 `<content>` 表达**：必须用 `<content><p>...</p></content>`，不能把文字直接写在 shape 内
5. **保存关键 ID**：后续操作需要 `xml_presentation_id`、`slide_id`、`revision_id`
6. **删除谨慎**：删除不可逆，删前先回读确认 `slide_id`
7. **编辑已有页面优先原链接更新**：修改单个 shape/img 用 `+replace-slide`（`block_replace` / `block_insert`），不要整页重建；已有 Slides 的多页整页重建用 `+replace-pages`，不要用 `slides +create` 新建整份 PPT；追加/插入单页用 `+add-slide`、删除单页用 `+delete-slide`，只有这些 shortcut 未覆盖的参数才手动调 `slide.create` / `slide.delete`
8. **`<img src>` 只能用上传到飞书 drive 的 `file_token`，禁止使用 http(s) 外链 URL**：飞书 slides 渲染端不会代理外链图片，外链 src 在 PPT 里通常不显示或显示破图。流程必须是「先把图存到本地 → 用 `slides +media-upload` 上传，或在 `+create --slides` 的 XML 里写 `<img src="@./path">` 占位符自动上传 → 拿 `file_token` 写进 `<img src>`」。如果用户给了网图链接，先 `curl`/下载到 CWD 内再走上传流程，不要直接把外链 URL 塞进 `src`。**图片最大 20 MB**（slides upload API 不支持分片上传）。

> **注意**：如果 md 内容与 `slides_xml_schema_definition.xml` 或 `lark-cli schema slides.<resource>.<method>` 输出不一致，以后两者为准。
