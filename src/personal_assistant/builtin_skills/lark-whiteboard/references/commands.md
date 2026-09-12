# 操作与参数参考

按本次操作查对应章节；不要求顺序通读。命令中的相对工作文件路径以执行命令的 cwd 为准，Skill 自带文件从 Skill 目录定位。

> [!IMPORTANT]
> - 运行 `lark-cli --version`，确认可用，无需询问用户。
> - 运行 `npx -y @larksuite/whiteboard-cli@^0.2.13 -v`，确认可用，无需询问用户。


---

## 快速决策

**身份**：画板操作默认使用 `--as user`。仅当需要以应用身份上传时使用 `--as bot`。

| 用户需求                                    | 行动                                                                                                |
|-----------------------------------------|---------------------------------------------------------------------------------------------------|
| 查看画板内容 / 导出图片 | [`+export --output-type preview`](lark-whiteboard-export.md)                       |
| 导出 SVG 矢量图 | [`+export --output-type svg`](lark-whiteboard-export.md)                       |
| 获取画板的 Mermaid/PlantUML 代码               | [`+export --output-type source`](lark-whiteboard-export.md)                             |
| 检查画板是否由代码绘制                             | [`+export --output-type source`](lark-whiteboard-export.md)                             |
| 仅微调节点文字/颜色                         | `+export --output-type raw` → 手动改 JSON → `+update --input_format raw`                             |
| 用户**已提供** Mermaid/PlantUML/SVG 代码，或明确指定用该格式 | 自己生成/使用代码 → [`+update --input_format mermaid/plantuml/svg`](lark-whiteboard-update.md) |
| 新建/创作复杂图表（架构/流程/组织等）                    | → **[§ 创作 Workflow](lark-whiteboard-workflow.md#创作-workflow)**                         |
| 修改/重绘已有画板                               | → **[§ 修改 Workflow](lark-whiteboard-workflow.md#修改-workflow)**                         |

## Shortcuts

| Shortcut                                          | 说明 |
|---------------------------------------------------|---|
| [`+export`](lark-whiteboard-export.md) | 导出画板为预览图片、SVG 矢量图、代码或原始节点结构。 |
| [`+update`](lark-whiteboard-update.md) | 更新画板，支持 PlantUML、Mermaid、SVG 或 OpenAPI 原生格式 |

---

## 不在本 skill 范围
- 文档内容编辑 → lark-doc [lark-doc](../../lark-doc/SKILL.md)
- 在文档中创建画板 → [lark-doc-whiteboard.md](../../lark-doc/references/lark-doc-whiteboard.md)
- 表格 / Base 操作 → [lark-sheets](../../lark-sheets/SKILL.md) / [lark-base](../../lark-base/SKILL.md)
