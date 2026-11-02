# bugfix-689 个人助手并发配置保存回执错配

## 原始报告

> 修复同一个人助手从两个设置入口并发编辑时返回假成功。已复现：PA 改名 A 在节点落盘、回执延迟，通用配置 PATCH 要存 B，结果返回 200 和 A，最终数据库也是 A。apps/im-server/src/personal-agent.ts 和 control-routes.ts 各建了 ConfigOperations，通用入口会直接返回上一笔 recover 的结果。覆盖跨入口、正常保存、旧版本冲突，以及已有的中断恢复/同一次重试语义。使用现有 profile_version、成功/冲突/待确认约定，让每个请求得到属于自己提交内容的结果。

用户选择快修，授权在保留正常体验的前提下验证并交付单独 PR。

## 复现与影响

在基线 `7e79e9b79` 上，用 Fastify 打到两个 PATCH 路由，使用内存 SQLite 与可延迟回执的模拟 Gateway。PA 改名 A 已被模拟节点接受，通用设置带版本 1 提交 B，此时才放行 A 的回执。B 实得 HTTP 200、名称 A，数据库也保存 A。编辑人会把未保存的 B 当作成功。同样，等待回执时提交不同描述或更旧版本也错误地得到上一笔的 200。

## 根因与修复约束

两组路由各持有自己的按 Agent 排队的对象，允许第二组路由提前恢复第一笔操作。通用 PATCH 把任何成功的恢复直接作为本次响应，跳过本次内容和版本检查。正常保存、版本冲突、节点已应用后丢失回执的恢复约定见 [Agent 配置契约](../../specs/im/agents-nodes.md)。已有离线写入边界见 [bugfix-644](../archive/bugfix-644-agent-offline-settings/design.md)。

修复及实测结果见 [事后设计](design.md)。
