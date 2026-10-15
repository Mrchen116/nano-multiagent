# Bundle、配置和生命周期

## 创建

源码放在当前 workspace 的独立目录，例如 `plugins/expense-summary/`。不要放在受管安装目录 `.nanoassistant/dsh-plugins/` 内。

最小包的 `package.json`：

```json
{"name":"expense-summary","version":"1.0.0","type":"module","description":"按月份汇总报销数据","dsh":{"bundle":{"patch":"./cordis.patch.yml"}}}
```

`cordis.patch.yml`：

```yaml
- insert:
    - id: expense-summary-tool
      name: ./tool.mjs
```

本地插件入口必须是 bundle 内的相对文件；不要把源码入口写成宿主包名或 workspace 外的绝对路径。需要宿主能力时，在本地 JS 入口 import 宿主公开 exports。DSH peer 依赖由宿主解析器复用，无需复制一份 DSH、在 workspace 安装 runtime 或使用 private imports。普通业务依赖写入自己的 package.json；确需构建脚本时等待明确授权。

有多个 provider/consumer 时使用 services-events 资料中的隔离 group。需要配置 schema 时先读取 describe_api 返回的公开说明，不把 JSON Schema 与 DSH 的简写 schema 混用。

## 安装与更新

调用 `plugin_manager`：

- `install_bundle`：`target` 是源码目录绝对路径或用户指定的兼容 package spec。
- `list_bundles`：读取安装状态、诊断及 `profileDir`。
- `set_bundle`：`target` 是精确包名，`enabled` 控制整个包。
- `remove_bundle`：移除安装，影响同 workspace Agent；不要连带删除用户源码或业务数据。

修改原源码后重新 `install_bundle`。本地安装生成独立版本，避免模块缓存复用错误；不要编辑已安装 generation。更新已停用包保持停用，需要重新开启时显式 `enabled: true`。`application: applied` 只是生效前提，仍需实际验证；`failed` 按诊断修复，`restart-required` 明确尚未在线生效。不要为了日常本地更新主动重启节点或重建会话。

## 配置

需要配置已安装插件时，从 `list_bundles.profileDir` 得到准确位置，读取其 `cordis.patch.yml` 后最小修改，这是当前 workspace 的原生 user overlay。只覆盖目标 bundle 已声明的条目，保留其他配置；例如修改该条目的 `config` 或 `isolate`。不要新插入一份独立副本，否则关闭原 bundle 时副本可能继续工作。

不要修改 `runtime.json`、受管 profile 的 package.json、已安装包文件或节点宿主 profile。安装由管理工具完成，overlay 负责已有条目的配置。

## 归属与授权

所有同 workspace Agent 共享安装和启用选择，但可能各自拥有独立 preset 实例；不得假设只加载一次。新增独立工具名无需手工加入白名单；既有工具禁用、子任务限制和审批仍按 Nano 规则执行。不要创建换名工具来绕过已有拒绝、审批或用户选择。插件安装授权不自动授权未来的外发、付费或其他业务操作。持久数据用明确的 workspace 数据目录，安装源码/产物可替换，数据不能依赖 generation 路径。
