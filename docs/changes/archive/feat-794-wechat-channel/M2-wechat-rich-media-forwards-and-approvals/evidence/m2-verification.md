# M2 验证证据：富媒体加解密、卡片/合并转发、局部引用、双阶段出站图片与单会话文本审批互斥

验证分支：`unit/feat-794-wechat-channel`（基于 M1 提交 `332a700bb` 实施 M2）  
验证日期：2026-11-26  
环境约束：全部验证在隔离 worktree 与临时运行目录（`/tmp/feat-794-m2-rt`）执行并已完成回收，未触碰主仓未提交改动或个人生产服务。

## 1. 单元、集成、前缀缓存与前端回归门禁

| 验证层 | 执行命令 | 结果摘要 | 覆盖范围与限制 |
|---|---|---|---|
| `@nano/channels` 富媒体与 XML/引用解析 | `pnpm exec vitest run packages/channels/tests/wechat-inbound.test.ts packages/channels/tests/wechat.test.ts packages/channels/tests/feishu.test.ts packages/channels/tests/channel-credentials.test.ts` | **4 files / 13 tests passed** | 覆盖 `<appmsg>` 分享卡片（禁 XXE 实体展开、禁通道层盲抓外链）、`<recordinfo>` 递归展开（`<= 5` 层 / `<= 50` 条 + 防指令混淆包裹）、`partial_text` 0-based 子串出现序号（`global` / `relative` 双模式 + `quotemd5` 消歧）、`sharp` EXIF 方向修正与纯图片入站（无 `[图片]` 占位词）、双层语音（自带转写优先 + `SILK/PCM -> 24kHz WAV`）、PDF 与 25 MiB 超限拒绝、不支持消息显式双端回执 |
| `apps/node` 本机 `external:` 离线附件落盘 | `pnpm exec vitest run apps/node/tests/file-transfer.test.ts` | **2/2 passed** | 覆盖 `download_attachment` 在 IM 离线（`http://127.0.0.1:1`）时直接从当前节点 `ExternalStore` 读取归属 `agentId` 的 `external:` 附件落盘（`0600` 权限、路径消毒、25 MiB 上限、跨 Agent 越权拦截） |
| `@nano/personal-assistant` 双阶段出站图片与审批互斥 | `pnpm exec vitest run packages/personal-assistant/tests/{wechat-delivery-and-approvals,wechat-channels,external,single-thread,global-agent,personal-assistant}.test.ts` | **6 files passed** | 覆盖 `stageOutboundImage` 在 IM 离线时直发微信 CDN `image_item` 并在重连后幂等补传影子会话图片、回复内联 `data:image/...` 提取、`SingleThread` 微信纯文本审批口令（`允许/1` vs `拒绝 [原因]/2`）与 IM 卡片双向互斥、转发文本防误触，以及 `/stop` `/new` 与轮次终结自动关闭未决审批防吞后续普通消息 |
| `apps/im-server` PA 主人私聊图片放行与影子流完成附件 | `pnpm exec vitest run apps/im-server/tests/{wechat-channel,external-ingress}.test.ts` | **2 files passed** | 覆盖 `pa.action.prepare` 在 `owner_private` 微信私聊下放行图片附件（非主人外部会话仍返回 `409 external_attachment_adapter_unavailable`），以及 `message_completed` 影子流消息关联已上传图片附件 |
| 根会话静态提示词前缀缓存与跨包依赖契约 | `pnpm exec vitest run packages/dsh-integration/tests/fork-prefix-provider.test.ts && pytest tests/contract/test_runtime_dependency_contract.py -q` | `fork-prefix-provider` **3/3 passed**；依赖契约 **14/14 passed** | 确认 Global / PA / SingleThread 静态提示词前缀缓存零退化，跨包架构红线完整保持 |
| Web 全量构建与测试 | `cd src/IM/frontend && npx tsc -b && npm run test` | **133 files / 1,293 tests passed** | 确认前端类型检查与全量组件/集成测试零回归 |

## 2. 隔离全栈 E2E（含真实 LLM）端到端核验

- **启动与控制面**：在 `/tmp/feat-794-m2-rt` 运行 `node scripts/e2e-wechat-twin.mjs`（`127.0.0.1:61419`）与 `./scripts/e2e-up.sh --wt /tmp/feat-794-m2-rt --profile daily`（`IM=http://127.0.0.1:61423`，`PA=pa_af402c69eb34`）。
- **验证结果**：
  1. **扫码 + 手机验证码（`482916`）绑定**：绑定通道 `ch_9afe51440ea34943bb7e03c1a598f198`，节点单 poller 进入 `connected`（`max_concurrent_pollers = 1`）。
  2. **合并转发 `<recordinfo>` + 真实 LLM 阅读理解往返**：向微信注入含林工/陈工多条子记录的 `<appmsg><type>19</type><recorditem>` 合并转发与提问，自动建立内部 IM 影子会话 `c_sw23qn`（`pa_af402c69eb34 · wechat`），真实 LLM 准确提取子记录信息并回发微信：「林工说，发布时间定在周四晚上 21:00。」
  3. **EXIF 原图无占位符入站**：上传带 `orientation=6` 的加密 JPEG 原图并投递 `IMAGE` 条目，核实影子会话消息 `content === ""`（零 `[图片]` 占位词）且包含完整图片附件。
  4. **局部选中引用（`partial_text` + `quotemd5`）+ 无转写 `SILK` 语音转 `24kHz WAV` + PDF 附件**：单条复合入站消息准确还原 `[引用历史消息摘录] > 周四晚 21:00`，并将 `SILK` 语音解密转码为 `voice.wav`（`audio/wav`）及 `release-plan.pdf`（`application/pdf`）同步至影子会话。
  5. **不支持特殊条目双向显式反馈与 `-14` 自动停用**：注入 `<emoji>` 动画表情 XML 后，微信侧立即收到可读提示「暂不支持直接解析该类型的微信消息（如动画表情或特殊卡片），请发送文字、图片、语音、链接或文件。」；注入 `errcode: -14` 后通道自动停止轮询并上报 `observed.status_code = "wechat_token_revoked"`。
- **资源回收**：脚本退出时执行 `./scripts/e2e-down.sh --wt /tmp/feat-794-m2-rt` 并清理临时目录，核实无残留进程。
