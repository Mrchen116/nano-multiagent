# Auto 权限配置与升级

CLI、单聊天 PA、全局 PA 及子任务共用 Auto 策略。当前默认策略版本为 `cc-2.1.267-nano-v1`；升级无需迁移数据库或配置，原有非空规则继续覆盖默认规则。全局 Agent 的普通消息任务在动作未获准时会自行沟通、换方案或停止该事项，等待回复期间可处理独立工作；单聊天和 CLI 继续保留各自人工审批入口。

## 配置位置与覆盖

在对应文件的 `auto_mode:` 下配置。工作区按字段覆盖全局；工作区未写的字段继承全局，两处都省略才用默认值。

| 产品 | 全局配置 | 工作区配置 |
|---|---|---|
| Coding CLI | `~/.nanocode/config.yaml` | `<workspace>/.nanocode/config.yaml` |
| Personal Assistant | `~/.nanoassistant/config.yaml` | `<workspace>/.nanoassistant/config.yaml` |

Gateway 的 `--config` 选择节点、Agent 和 provider 启动配置，不搬迁上述 Auto 全局根。每个 child 保留委派时的有效 Auto 配置及原始用户范围；后续委派不会把 Agent 自己声称的同意变成人工批准。

相关默认值如下；已有配置无需为升级补写这些键：

```yaml
auto_mode:
  enabled: true
  deny_limit: 3
  total_deny_limit: 20
  ask_timeout_sec: 600
  unattended_fallback: deny
  allow: []
  soft_deny: []
  hard_deny: []
  environment: []
```

本次新增 `hard_deny` 规则列表和 `total_deny_limit`。`deny_limit` 为连续有效自动拒绝阈值，`total_deny_limit` 为同会话累计阈值；成功清连续数，累计阈值被处理后清累计数，普通 child 各自计数。模型故障不计入有效拒绝。到达阈值后，CLI/单聊天使用原人工入口，全局普通消息任务仍向 Agent 返回原因。

四类规则列表的解释一致：空列表采用该类新默认规则；非空列表替换该类默认规则。在列表中加入精确字符串 `$defaults` 可在该位置展开一次默认规则，其余自定义规则保持顺序。例如：

```yaml
auto_mode:
  soft_deny:
    - '$defaults'
    - '未经用户明确确认，不删除 workspace/releases 下的文件。'
```

`allow` 表达允许情形，`soft_deny` 表达可结合用户授权判断的限制，`hard_deny` 表达硬限制，`environment` 提供环境事实。规则文字交由 Auto 策略理解；工具本身的明确拒绝仍优先于宽工具许可。现有 `web_fetch` 子段沿用整个子段替换，不做深层合并；Bash 仍按完整命令语法和参数检查。

## 判断未执行的原因

先看 Agent 收到的工具说明与该次工具结果，区分用户拒绝、策略拒绝、工具硬限制及审批无结论。自动分类超时、不可用、无法解析和上下文超限等故障本身，不会被描述为用户没有授权，也不会偷偷换模型或裁剪后重试。

- 普通全局主任务及其普通 child：动作不执行，原因返回 Agent，不等待权限卡片。
- Heartbeat（包括复用全局主会话的 Heartbeat）和 Cron：保持 `unattended_fallback`，默认 deny；显式 allow 时按配置处理故障或阈值分流，并在结果中标明配置 fallback，不冒充模型允许。工具要求的硬性人工确认不由该 fallback 放行。
- CLI 和单聊天：继续既有人工审批入口。

用户可通过具体请求或对明确提议的回答授权；Inbox 中的真实用户原话可作依据。文件引用、Agent 转述、自动通知及没有对应关系的另一聊天回复不构成新批准。压缩或重启后背景不足时，Agent 可以重新说明具体动作请求确认；查询旧消息只补背景。

PA 的专用审批模型仍在 Gateway 的 `llm.tool_approval_model` 中选择，修改后按同一配置重启，见 [Gateway 操作](gateway.md)。未设置时复用当前任务模型，失败时不换用其他模型。

## 回退

需要退回旧版本时，先结束或停止该实例正在执行的任务，保留原配置和运行数据备份，再部署升级前的代码并用原配置启动。没有专用数据库迁移；新增消息 metadata 可由旧 reader 忽略。代码中没有新旧分类器双轨开关或自动回退旧 prompt；回退是一次明确的版本部署操作。

CLI 重新启动对应入口；Gateway 以同一配置路径执行停止、更新、启动，参见 [Gateway 操作](gateway.md)。生产双节点的版本切换按 [舰队操作](prod-fleet.md) 完成，避免节点使用不同版本。配置中的现有自定义规则应随版本一起核对，不能仅删除新键就视为已恢复旧策略。
