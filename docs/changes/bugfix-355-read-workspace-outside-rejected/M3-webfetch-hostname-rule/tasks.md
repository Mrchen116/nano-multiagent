# M3: webfetch-hostname-rule — Tasks

## 目标

实现 WebFetch 工具级权限检查:
- preapproved host 表(89 项,对齐 CC preapproved.ts)
- HostnameRuleEngine(user-configured deny/ask/allow host rules)
- WebFetchTool.check_permissions 5 分支决策链
- AutoModeConfig.web_fetch 配置字段扩展

## 退出标准(来自 design.md Milestone 表 M3 行)

- [worker] `PREAPPROVED_HOSTS` 与 CC preapproved.ts:14-131 逐项一致(89 项),单测全量比对;`is_preapproved_host(hostname, pathname)` 复刻 CC preapproved.ts:154-165 的 HOSTNAME_ONLY + PATH_PREFIXES 分裂逻辑,含 segment boundary 保护
- [worker] `HostnameRuleEngine.evaluate` 单测覆盖 deny → ask → allow 优先级、exact match 语义、空 rule 返回 passthrough
- [worker] `WebFetchTool.check_permissions` 决策链 5 分支单测全绿;`auto_mode_gate.SAFE_TOOL_ALLOWLIST` 已不含 `web_fetch` 的回归单测
- [worker] `AutoModeConfig.web_fetch` 字段 YAML 加载 / merge 单测全绿
- [reviewer] preapproved URL 直接 allow;非 preapproved 非 rule URL 弹卡片

## 测试策略

纯后端工具级权限逻辑 — 单元测试 + 入口验证(auto_mode_gate 集成路径回归)。
无前端变更。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | webfetch_preapproved + HostnameRuleEngine 新建 + 测试 | DONE |
| R2 | AutoModeConfig.web_fetch 配置扩展 + 测试 | DONE |
| R3 | WebFetchTool.check_permissions 5 分支 + 集成回归 | TODO |

## 范围边界

只动:
- `src/agent/platform/permissions/hostname_rules.py`(新建)
- `src/agent/platform/tools/builtins/webfetch_preapproved.py`(新建)
- `src/agent/platform/tools/builtins/web_fetch.py`(加 check_permissions)
- `src/agent/platform/config/auto_mode.py`(加 WebFetchConfig)
- 对应单测文件

严格不动 M2 范围:write.py / edit.py / dangerous_paths.py
