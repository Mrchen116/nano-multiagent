# refactor-550 实施与验证

用户要求“不用 change-orchestrator，直接干”。root 在 `codex/feat-546` / `unit-feat-546` 直接实现并验证，沿用 PR287。未启动 implementation orchestrator 或新增实现后独立审查；已有 design-review 仅证明设计复核，不冒充实现验收。

## 实现

- users/conversations 使用 `u_` / `c_` 加八位小写字母数字；数据库唯一约束冲突只对主键碰撞重试。业务 agent_id 保持全 IM 唯一，用于内部配置/路由。
- conversations.info 返回完整授权成员和可直接使用的 user mention。list 保留聊天/成员检索并缩减模型输出；Inbox 与历史共用消息投影，成员均使用 user_id，保留分片/图片/消费凭据。
- send_message 模型参数统一 target；成功回执不重复正文。单 Thread 和 global 的身份说明统一，单 Thread 显式包含自己的 user_id/名字；保留原任务推进和群回复策略。
- 前端候选包含真人与 Agent，显示完整短 ID，标签只使用 type=user；正文、预览、通知继续显示名字。命令提及保持按原目标触达。
- 外部 shadow 的代记 owner 不作为发送者的可私信身份；可靠来源 ID 写入 sender_source_id，旧历史无法恢复则省略。业务代码无旧 ID alias/自动身份迁移/双 mention parser。

## 自动化验证

- 最窄 IM API：7 passed。
- IM + PA 扩大回归：1675 passed，1 条旧 prompt 断言失败；更新断言后相关 prompt/成员/模型表达测试 30 passed。
- CI 等价 agent/PA 分片：1849 passed。
- CI 等价 remaining 分片：1854 passed，1 条旧 mention fixture 失败；修正后 broadcast/stop 控制测试 25 passed。
- frontend：75 files / 722 tests passed，生产 build 通过；最后成员文案用浏览器刷新检查。npm audit 的 critical 门槛通过，依赖未改。
- Ruff 检查、任务文件格式化及 docs integrity 通过。最终远端结果以 PR287 对提交 HEAD 的四项 CI 为准。

## 真实模型与浏览器

模型沿用隔离演示的 `deepseek:deepseek-v4-flash`。验收仅发往迁移副本，外部 channel 关闭。

1. 原总量 Session `sess_0af603994eac0e8f` 在群 `c_c4ogzmso` 收到自然语言请求，实际调用顺序为 inbox.check → inbox.read → conversations.info → send_message(target=u_mmln2osx) → send_message(target=c_c4ogzmso) → inbox.check/read。没有 Bash 或数据库查询。
2. 私聊收到 `REF550-DM：短身份私信成功`；群里出现 `<mention type="user" target_id="u_b7w701i4"/> REF550-MENTION：请只回复收到`，小策实际回复“收到”，Inbox 显示其相同 user_id。
3. 追加私信 Agent：模型使用 `target=u_b7w701i4`，原总量/小策私聊 `c_yrtcxbu4` 收到 `REF550-AGENT-DM：无需回复`；复用原会话，没有另建对象。
4. 浏览器桌面 1280×720、手机 390×844：四名成员均有短 ID，选择真人发送 `REF550-UI-HUMAN` 后显示名字；手机选择总量发送后收到 `REF550-MOBILE-ACK`。刷新后消息及候选保持，成员标题显示 Mention member，布局无溢出；恢复了临时 viewport 并关闭测试 tab。
5. 单 Thread 两 Agent 群 `c_bvte0xcm`：e2e 的正文 user mention 实际触达 e2e-peer。补齐自身身份说明后重启复验，e2e-peer 正确回复 `e2e-peer / u_vopnlyaj`。
6. 重启 IM + Gateway 后，向原总量私聊询问前两项验收标识，原 Session 回复 `REF550-DM、REF550-MENTION`。

## 一次性迁移副本

副本源为 `/tmp/feat546-feishu-authorized` 的 SQLite backup 与文件复制，演练目录 `/tmp/ref550-migrated-copy`。复制时原服务仍运行，因此它用于迁移方法演练；生产部署必须按 [migration-prompt.md](../migration-prompt.md) 停所有写入再做整套备份。

57 项旧主键映射完成后，逐条确认 16 个用户、41 个会话及 157 条原消息仍存在，消息 ID 不变；所有原 global main Session ID 保持。全部数据库 foreign_key_check / integrity_check 通过。重建 Session prompt slots、转换历史工具参数与结果、同步 45 条原 Inbox receipt 的页面/摘要，没有清空上下文或未读。

副本无 agent_channels 记录；凭据 AAD 仅用合成凭据验证“旧 owner 解密、新 owner 重封装”，未声称完成真实 channel 凭据迁移。部署 prompt 明确由持有 Gateway 私钥的部署 Agent 完成该项。

隔离使用 IM 59770、唯一 node `wt-ref550-copy-59770`、独立 config/workspace/DB、禁用外部 channel 和定时调度。macOS 路径统一为 `/private/tmp/ref550-migrated-copy` 后恢复原 global Session。启动用独立 tmux 中的 `python -m uvicorn IM.app:app --host 127.0.0.1 --port 59770` 和 `python -m personal_assistant.main --config <copy-config> --im-service-url http://127.0.0.1:59770 --foreground --auto-bind`，PYTHONPATH 指向本 worktree，IM_DB_PATH 指向副本。

验收结束向本次 Gateway/IM 发送 SIGTERM，确认 59770 和最后的内部端口 60714 均释放；删除副本 config、secret、凭据和 PID。新前端构建保存在副本 frontend-dist；共享演示的静态资源恢复为实施前 HEAD 构建，59669 仍在线且 index 与原版一致。原演示/生产数据库未迁移，原服务未重启，主仓 dirty/untracked 内容保留。

## 交付

current specs 已同步，迁移 prompt 随完整 unit 归档并进入 PR287。没有合并或生产部署。
