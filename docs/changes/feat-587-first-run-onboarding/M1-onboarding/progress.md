# M1 实施与验证证据

## 当前实现

同一 unit 串联个人账号/资源空间、同源电脑安装包、空 Node 启动、模型 setup、Web 四步向导及首次真实聊天。初轮独立实施负责 IM 空间边界与 Node/DSH 模型 seam；主 Agent 负责集成、安装器、Web 和后续修复。完整门禁尚待独立审查与产品验收。

## 已验证

- 全新隔离安装目录：从 `http://127.0.0.1:18489/install.sh` 获取实际发布包，校验 SHA，安装锁定依赖，浏览器确认后启动 Node。无需仓库路径、YAML 或预建助手。
- 初次慢速确认触发真实 429：`prepare` 每秒调用与浏览器共用 60/min 来源桶；现改为 3 秒并遵循 Retry-After。已有 device-binding 行为测试先失败、修复后通过，同时仍证明丢失 commit 响应可恢复、旧 owner runtime 保留。
- bootstrap 最低层测试证明同源重跑身份与配置不变、不同服务独立、私有文件权限，跨服务指定既有配置拒绝覆盖。
- IM onboarding API 测试在路由接入前 404、接入后通过，覆盖本人资源、他人节点拒绝、异步归属变更拒绝、凭据不回显、未发布安装包明确 503。
- 真实 Node ModelSetup → DSH → 本机代理 → `codexOAuth:gpt-6-luna` 验证成功；浏览器随后真实创建 global 助手 `assistant-31e4dd7c`，工作目录自动分配。首聊 `c_uacc7xc9` 收到真实模型回复，按建议起步任务询问目标、截止时间/固定安排与可投入时间；刷新后历史保持。
- Integration 测试通过真实锁定 DSH 的公开 settings/credentials seam，验证失败回滚、冷重启后 key 保留和实际 Agent 回复。原生 OAuth device-code notice/cancel 经受控 interaction 验证，未宣称真人 OAuth 登录完成。
- Web onboarding 3 个行为测试通过：连接失败禁止跳步且不保存 key、创建重试保留 Agent ID 和安全默认值、重新打开已有首聊不覆盖草稿。Web build 通过。
- 初轮 IM 套件、公司/认证 Web 窄测试、11 个 DSH 依赖架构契约通过；最终全套结果在交付前补齐。

## 证据与限制

所有运行数据位于 worktree `.dsh-runtime/onboarding-e2e/`，IM 仅监听 18489；Node identity、config、DSH home、workspace 均隔离，安装演示禁用登录自启。截图和最终录屏保存在本地 `output/playwright/`，不提交数据库、凭据或媒体。

现有本机代理 DeepSeek profile 的流式 SSE 返回未标注 encoding 的压缩字节，被真实 DSH 拒绝；非流式成功不代表可用。该外部代理未修改/重启，验收改用其已验证的 Codex ingress。

## 测试维护

保留/扩展现有 identity、control、device-binding、company-access、auth-form-experience 与 iOS SessionTests；旧注册等待批准断言改为个人 onboarding。新增 bootstrap、setup、onboarding 和 tenancy 测试分别持有首次安装、公开运行时配置、跨进程入口与跨资源空间隔离风险；无为单次录屏创建永久测试。
