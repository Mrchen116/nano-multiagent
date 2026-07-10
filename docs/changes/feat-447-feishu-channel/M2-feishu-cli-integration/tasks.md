# M2: feishu-cli-integration

## 目标

创建 `skills/feishu-doc.md`（飞书文档操作 skill 文件），教 agent 使用 feishu-cli 命令行工具操作飞书云文档。

## 退出标准

- [x] skill 文件格式正确（YAML frontmatter + markdown body）
- [x] 覆盖 feishu-cli 核心命令：auth、doc、wiki、sheet、chat
- [x] OAuth 授权流程验证（文件中有说明）
- [x] feishu-cli 安装验证（前置条件已记录）
- [x] 文档操作覆盖：创建、读取、导入
- [x] 知识库操作覆盖：list、resolve、create
- [x] 电子表格操作覆盖：read、write、create
- [x] 发消息操作覆盖

## 测试策略

纯文档 milestone，无代码变更，不需要测试命令。验收方式：reviewer 验证 skill 文件格式和内容完整性。

## Roadpoints

### R1: skill 文件创建
- 状态: DONE
- 范围: `skills/feishu-doc.md`
- 内容:
  1. 创建 `skills/feishu-doc.md`
  2. 覆盖所有 feishu-cli 命令（auth/doc/wiki/sheet/chat）
  3. 使用中文，YAML frontmatter 含 name + description
