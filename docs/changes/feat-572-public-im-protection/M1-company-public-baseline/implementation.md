# M1 实施交接

状态：本地实施与集成完成，待独立 code review、verification 和产品验收；未归并 canonical spec、未归档、未上线。

## 实现

公司成员批准/停用与管理员边界；持久 refresh 轮换、会话 epoch、单次 WS ticket；入口限流和有界 WS；设备持有证明、本机确认、整机交接及中断恢复；公司范围任务与按群活动入口、保护原聊天来源、真实人类删除授权和幂等回执；受保护附件读取、SSRF 限制、上传配额及失败附件草稿；单进程 public launcher 与日志脱敏。源代码、集成 fixtures 和脚本均在本提交。

## 验证

运行位置：本 unit worktree。Python 使用主仓 .venv，PYTHONPATH=src。

- `pytest -q`：4090 passed，27 warnings，98.25 s（/tmp/feat572-python-final2.log）。随后仅 PA 绑定轮询改为 2 s、备份恢复测试隔离目录修正、群提及删除解析窄修复；相关绑定 11 passed、独立目录恢复 1 passed、公司任务/PA bridge 18 passed。
- frontend `npm test -- --run`：788 passed / 85 files（/tmp/feat572-ui-final.log）；后续新增容量错误翻译测试后 chat-workspace 54 passed、bind 2 passed，`npm run build` 通过。
- Ruff check/format、git diff --check 通过；contract + company + public launcher 167 passed；docs_check 246 maintained / 75 routes 通过。
- `npm audit --audit-level=critical` exit 0，已有 2 low / 3 moderate / 2 high，无 critical；未升级依赖。
- 群聊真实 `<mention .../> 确认删除 Child` 原先被 fullmatch 拒绝，先取得 red，再只移除前导结构化 mention；命名确认仍来自已持久化真实用户消息。裸 yes 不构成命名删除授权。
- 备份恢复测试先证明独立恢复目录缺 message-images 时附件 404，再连同数据库复制私有目录后通过，旧人类/机器凭据失效且重新登录可读取相同附件字节。

真实本地产品证据见 [evidence](../evidence/product-20260930/README.md)，发布/恢复草案见 [public-rollout](../public-rollout.md)。有效证据可复用，无需为角色交接重复全量。

## 未完成退出标准

R6 真实公网域名、免费配置、真实恢复发布现场：需要设计明确要求的当次上线授权；尚未操作 Cloudflare 或生产部署。
R7 真实飞书：专用 E2E Bot 正由 unit-feat-569 使用，未停止其他任务或抢占长连接。
独立 reviewer 应逐项记录 pass/fail/inconclusive，不把自动化覆盖当作真实旅程通过；必须保留这两个缺口。不能据此归档或创建 Ready PR。

## 复审修复批次

- 慢附件响应在发送 response headers 前释放公司准入锁，网络 send 限时；慢消费者不再阻塞停用提交。实际 ASGI 背压与并发停用回归通过。
- 设备确认链接统一使用配置的 public URL；跨主机存量节点登记只接收 Gateway 导出的公钥与指纹，不搬运私钥，操作已补入发布文档。
- 删除回执查询忽略七天前结果，写入时有界清理到期删除回执；create/apply 重试行为保留。
- 全局 Agent 删除从同 agent/session/run 的 `inbox_read_committed` 收集完整读取的人类消息；入口持久化 IM 消息身份，provider ID 仍用于模型来源展示。历史同步、其他运行、未提交或只读部分消息不授予删除资格。IM 仍逐条核对真实人类消息、聊天权限和明确命名范围，模型参数不增加确认字段。
- 实时连接共享现有 transport 状态，显示重连/冷却倒计时和重新登录入口；429 遵守 Retry-After，1013 使用冷却。认证错误改为关联表单的简短红字，与原型一致。

窄验证：公司网络/绑定9 passed；删除回执/公钥登记13 passed；global Inbox/bridge/company tasks31 passed；实时流/App/认证30 passed。全量与独立 targeted 复验结果待下节记录。
