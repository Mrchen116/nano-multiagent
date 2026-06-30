---
name: feishu-doc
description: 教 agent 使用 feishu-cli 命令行工具操作飞书云文档（创建、读取、导入文档、知识库、电子表格、发消息）
---

# 飞书文档操作 Skill

使用 `feishu-cli` 命令行工具操作飞书云文档。所有操作需要先完成授权。

## 前置条件

```bash
# OAuth 登录授权（首次使用或 token 过期时执行）
feishu-cli auth login

# 检查登录状态
feishu-cli auth status
```

## 文档操作

### 创建空白文档

```bash
feishu-cli doc create --title "文档标题"
# 返回新文档的 doc_id 和 URL
```

### 读取文档内容

```bash
feishu-cli doc read <doc_id>
# 以 Markdown 格式输出文档内容
```

### 导入 Markdown 为飞书文档

```bash
feishu-cli doc import <local_file.md> --title "文档标题"
# 将本地 Markdown 文件导入为飞书云文档，返回 doc_id
```

## 知识库操作

```bash
# 列出知识库空间
feishu-cli wiki list

# 获取知识库节点
feishu-cli wiki resolve <wiki_token>

# 在知识库中创建节点
feishu-cli wiki create --space <space_id> --title "标题" --parent <parent_token>
```

## 电子表格操作

```bash
# 读取表格数据
feishu-cli sheet read <spreadsheet_token> --range "Sheet1!A1:D10"

# 写入表格数据
feishu-cli sheet write <spreadsheet_token> --range "Sheet1!A1" --data '[["a","b"],["c","d"]]'

# 创建表格
feishu-cli sheet create --title "表格标题"
```

## 发消息

```bash
# 向指定用户/群发送消息
feishu-cli chat send --to <user_id_or_chat_id> "消息内容"

# 支持富文本（JSON 格式）
feishu-cli chat send --to <id> --type post '{"title":"标题","content":[[{"tag":"text","text":"内容"}]]}'
```

## 使用注意事项

- 所有命令需要先 `feishu-cli auth login` 完成授权
- doc_id 格式通常为 `doxcnXXXXXX`，wiki_token 格式通常为 `wikiXXXXXX`
- 电子表格 range 使用 A1 表示法（如 `Sheet1!A1:D10`）
- 发消息的 to 参数可以是 open_id、user_id 或 chat_id
- 导入的 Markdown 支持标准语法，标题、列表、代码块等会自动转换
