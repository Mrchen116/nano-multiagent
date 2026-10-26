# M1 worker evidence

范围：合成隔离 workspace / SQLite / 原生 DSH subprocess；下列 scripted provider 固定输出用于验证真实运行时边界，不冒充真实模型行为。真实模型及最终上游 HTTP 输入另见 `../acceptance.md` 与最终 evaluation report。

| 合约 | 可复查测试与实际结果 |
|---|---|
| 单一权威、容量与有界投影、来源、主体/情境、分页/日期、版本和并发 | `packages/dsh-integration/tests/personal-memory.test.ts`：实际文件锁与 records/projection；13项覆盖同源不同事实保留、A→B→A新来源纠正和旧源拒绝。`/tmp/pa665-forget-guard-green.log`含本文件与两个native文件，共15 passed。容量测试证明存储边界；M08真实模型仍需单独证明未压缩掉压力条件。 |
| 下一模型请求刷新、forget清理/重启、历史和notes fence | `personal-memory-context.test.ts`：实际 subprocess，截获实际 `llm/stream` 输入；纠正下一请求出现新值；forget后正文不在请求，notes读取为空，旧history被拒；重启保持fence。合法continuation保留剩余工作/私聊目标，当前及旧版正文进入handoff均拒绝且未擦除记录/未报完成。 |
| 同步主人纠正与异步维护 | `personal-memory-maintenance.test.ts`：原生combined review真实读取revision1后暂停；主人修订revision2，再释放旧写入，实际收到scope revision conflict；共享Skill私人事实写入实际被执行guard拒绝。`/tmp/pa665-coldtask1.log` 3 passed中包括此项。 |
| 非PA、可清空配置、Skill关闭 | `personal-security.test.ts` 原生测试保持普通Agent原catalog；custom guidance可清空，禁用nano-ongoing-work不重新加载；个人源身份/独立审核仍在。完整suite及其受影响文件重跑结果见最终validation。 |
| 迁移/重放/故障/回退保护 | `personal-memory.test.ts`真实目录故障使第二份backup失败，records未发布且旧文件原样；修复路径后导入一次。提交后投影故障返回pending，authority保留、同key重试补投影，不重导。离线CLI对`/tmp/pa665-migration`合成副本连续两次输出完全一致：`/tmp/pa665-migration-first.json`与`-replay.json`，revision1/record_count1/legacy_source_count1；backup保留。未用旧代码写新records，回退要求暂停PA见deployment-prompt。 |

正文与日志不进Git。CR-01/02与CR-04原失败及独立关闭记录保留在code-review/verification；不把后续通过追溯覆盖失败。真实混合遗忘PA-5、跨群下一次上午偏好、当日辣食例外/平时清淡分别见acceptance Round3/4。
