# bugfix-629 — 候选版回归记录 R1

> 2026-10-21；独立 change-reviewer；候选实现 Nano `2ee87df7becb22f5d2576c192dbbee3018a3a07f`，插件源码 `51eb236`、`dsh-agent-context@0.3.0-rc.2`。
> 候选 tgz SHA256：`5aa290fb5634cccccb6ed8f11b96acccac587fc708a420b80ecf29d2b2bf3461`。运行时使用 caller 已安装构建的这份本地包；后续共享 HEAD 与设计变化不冒充本轮受验版本。

## Verdict

**未形成最终验收：候选基线已被用户后续决策替代。** 用户要求新窗口只重建当前可用 Skill 目录、不自动重放旧正文，并撤掉 interrupted_turn。本轮真实压力恢复成功依赖的候选行为含该导航，不能据此批准后续方案或宣称纯 Notes/History 路径已通过。按 caller 指令只收尾已发请求，停止新增实验，交还隔离服务。

本轮只读产品实现，未定位实现根因、修改源码或测试。使用隔离 Web IM 实际消息与插件管理 API、真实模型 `codexOAuth:gpt-6-astra` medium；没有内部 submit 或脚本预定最终答案。无 UI 变更，按 runbook 采用 API 交付验收，未声称浏览器视觉验收。

## 主故障候选基线：AMBER629B

条件为默认 C=258400、O=32768、B=16384、R=6144；没有预算 override，PA Auto off。先前 Notes 已记载旧日记交付完成，navigation-check 在 seq334 写入“验证完成，无待处理任务”。新输入不依赖旧批次的待办。

1. Web IM 新消息 `0975d73d924e428f87b59dc440153827` 要求复核 AMBER629B 的25份分册，读取前不写新 Notes，只整理、不执行待办。原生 Inbox read seq360/result361 实际取得原文。
2. 同一 turn6、step4 的25次 skill 调用 seq370–418，结果 seq371–419 全部成功，共 **1,059,818 字符**，各42391–42410字符；没有用单册截断结果充当全量读取。读取后至压力换窗前没有 Notes 写入。
3. compaction/start421、summary422、end424；原生 checkpoint 明确 `Context reset reason: pressure`，shadowedTokenCount=277391，范围280–419。checkpoint含候选 `<interrupted_turn>`，turn_id=347。
4. 换窗后先 notes read preparation（430/431），返回旧批次已交付记录；随后 history list_items turn_id347（436/437）恢复新 Inbox 输入及原始工具记录，再 search 同turn skill结果 `- [ ]`（441/442）。原始 Inbox 仍为 tool 来源，observer通知仍为 system/nano-system，没有重标成人类授权。
5. send_message446/result447 真实发送消息 `14fd98802483482fbe5ec2ac6e895544`，聊天落库 completed；只有一份 AMBER629B 最终清单：琥珀实验原始波形归档B17（周四前）、给秦老师六张显微照片（明早）、读书会两袋咖啡豆（周日）。与分册01/13/25独立核对一致；未误用旧批次、未执行待办。turn/end452=completed。

**结论：该候选的默认压力组合实测成功；撤除 interrupted_turn 后必须重新实测，不能继承为最终 pass。** 后续 observer轮仅读取本测试owner另一聊天的背景，turn/end480=completed，无新增交付。

## 已完成的其他候选观察

| 场景 | 实际证据 | 候选结论与保留边界 |
|---|---|---|
| 七份Skill与普通步骤 | recovery-1..7各成功读取8697字符。PA主动换窗278；snapshot291的nano-used-skills仅1552字符，七个正文sentinel均0。seq298/303/308/313/318/324连续六个Notes/普通步骤；329实际skill重读recovery-1；334写完成，339仅发完成。上述步骤期间没有新runtime snapshot。 | 当时“曾用Skill导航”分支无逐步全文增长，实际按需重读成功。最终目录生命周期改变后需重验。 |
| 直接输入、两个有内容窗口 | 普通Agent session `ee8ae939-2cfa-479f-8b87-ca3450b0d8aa`，chat `c_isi20umr`。显式 `/skill:ledger-check`，业务工具仅workflow。compaction25/67；history按turn_id6读原输入item10及第二窗item60；最终消息`af1590df9a3d4769a0bdfbce0925a55d`一次正确交付108、67、175贝壳和规则标记。 | 两个有内容窗口与真实原文恢复成功。无skill/read时正文自动恢复属于旧候选行为，用户已要求取消，不能当最终通过。 |
| 正常重启恢复 | 同隔离Node正常stop/start，PID81429→84397。原session不变；普通Agent seq111/116/121实际History读原输入、第二窗结果及Notes，正确再次核对175。 | 候选重启恢复成功，未删除原记录。 |
| 插件off/on | 同workspace产品API set_bundle false/true；off后的实际provider tools仅workflow，显式Skill核算47成功；on后seq151/156/161实际读取原History/Notes，正确返回175。 | 候选开关与记录保留成功；未测试停用后长任务摘要压缩，不作该声明。允许skill工具分支的off组合尚未补跑，按后续暂停要求保留缺口。 |
| 空业务白名单 | 普通Agent profile改为[]；实际provider仅get_context_remaining/history/new_context/notes；seq177实际Notes读取，最终175+规则标记。 | 没有扩大业务schema。 |
| 会话与来源边界（暂停前已发） | 普通Agent seq190过滤不存在turn，195读取PA会话item遭not_found，200读取本会话agent-instructions项，turn/end206正常结束。 | 原生操作证明会话隔离；最终模型拒绝披露内部元数据，未给用户三项逐项结果，因此不把最终回答当完整用户旅程pass。 |

## 环境前置尝试，不计压力通过

- 首次七Skill路径不正确产生unknown；修正后七次正文成功才计入。此前插件安装、custom journal_fixture调用均被Auto off manual_required阻断；没有绕过审批。fixture预装由caller执行，仅作环境准备。
- 单个1,386,415字符journal-archive被原生spill裁为49,930字符（遗漏1,337,055字节），随后正确交付旧批次三todo但没有压力换窗。本轮明确不把它算主故障通过；有效压力证据来自后续25份完整分册。
- 一次History max_chars_per_item=6000被校验拒绝，模型自行改4000继续；未修改工具schema或实现。

## 证据与交接

- PA session：`30f48cc2-b740-43d8-aaf7-1ca035a4d48d`；chat：`c_7bdf1ad3596a`；隔离IM `http://127.0.0.1:63693`，node `wt-nano-multiagent-79125`。
- 原生证据位于本worktree `.dsh-runtime/**/sessions/**/<session>/session.v4.jsonl.zstd`；真实provider请求目录为 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_16-07-04_374_30f48cc2-b740-43d8-aaf7-1ca035a4d48d/` 及 `2026-10-21_16-13-18_886_ee8ae939-2cfa-479f-8b87-ca3450b0d8aa/`。
- 本机归纳 `/tmp/bugfix629-e2e/30f48cc2-evidence.json`、`ee8ae939-evidence.json`；最终产品响应 `pa-final-timeline.json`、`direct-final-timeline.json`。原始日志、凭据和测试素材不入Git。
- 最后观察PA turn7和普通Agent turn6均completed。Node PID84397，`.gateway.pid`已同步；服务保持运行，无新实验待发。PA/普通Agent上下文插件均已恢复enabled，普通Agent业务白名单当前为空。测试workspace、Notes、History、临时fixture保留，由caller接管清理或后续复验。
- 未新增自动化测试。Reference Artifacts Reviewed：派发时incident/design/runbook、当前agent-capabilities/auto-permissions、旧feat627验收（只参考范围，不拿其结论替代本轮新路径）。本轮只提交此候选报告。

## 上层文档

当前用户已改变Skill与恢复策略，incident/design/delta-spec由caller修订；本报告不修改它们。SPEC/AGENTS/文档体系未由本轮改变。最终受影响场景及验收标准需以修订后版本重新冻结并复验。
