# refactor-653: 移除 workspace 聊天历史副本

## Relations

- Related: perf-651-history-export

## 原始诉求

> 那就把第二份 `.nanoassistant/chat_history/*.jsonl` 的自动生成去掉吧，我觉得这个东西没用了。现在Agent的Context里面有写要它可以去读这个东西吗？

## 澄清记录

用户已决定停止生成第二份可读副本。代码调查未发现 Agent context 指示读取该目录；历史恢复通过原生 DSH 记录及 notes/history 工具完成。停止所有副本写入，已有文件原样保留，不执行清理。保留显式原始快照导出、fork 与配置恢复。本 unit 在独立 worktree 交付 PR，不部署。

## 现状痛点

perf-651 已将完整原始快照改为按需生成，但每轮 turn/end、fork、启动恢复及显式导出仍会写 workspace 可读副本；用户不再需要这份派生文件，维护增量游标、重建和启动扫描也失去目的。

## 目标状态

移除可读副本写入及恢复路径。正常聊天、fork、启动和显式导出均不创建或修改 `.nanoassistant/chat_history/`。原生日志继续持久化；显式 `session.export` 仍提供完整、原子发布的 JSONL 快照。同步更新当前契约和内置说明，不修改历史归档。

## 用户侧验收标准（不变性）

### Requirement: 聊天与历史恢复不依赖 workspace 副本

#### Scenario: 普通聊天及重启
- **WHEN** 用户连续聊天并重启节点后继续原会话
- **THEN** 与变更前一致，原生历史可查询且继续对话正常；workspace 不生成可读副本，已有文件原样保留

### Requirement: 分支与显式导出保持可用

#### Scenario: fork 后继续并导出
- **WHEN** 用户从历史消息 fork、继续分支并请求原始快照
- **THEN** 与变更前一致，分支包含继承前缀与自己的后续消息，不混入源会话分支点后的内容；导出保留版本头、完整原生事件与原子发布语义，且不生成 workspace 副本

## 影响范围

`packages/dsh-integration` 的历史副本生成与启动接线、相关测试；gateway current 契约及内置说明。无前端、工具权限、上下文压缩策略或原生存储格式变化。

## 迁移与回滚策略

不迁移或删除既有副本，不需要一次性部署脚本。原生日志和显式导出保真由真实 DSH subprocess 回归验证。回滚代码可恢复旧版本的副本生成行为。
