# M101 — Gateway Heartbeat 调度器

## 前置阅读
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/SPEC.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/ROADMAP.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`

## 范围
- 仅实现 M101 所需的 heartbeat scheduler。
- 仅修改 `src/personal_assistant/scheduler/`、相关 `personal_assistant` 测试、以及本任务/进度记录。

## TDD 计划
1. 先补 scheduler 红测：`cron` / `interval` / `at` 三种模式。
2. 补“读取 `HEARTBEAT.md` 后无有效任务时静默跳过”的行为测试。
3. 补“进程重启后补跑错过的到期任务”的恢复测试。
4. 最小实现 scheduler，引入必要的状态持久化。
5. 跑相关 `personal_assistant` 测试，复查 import/负向断言，避免留下并行旧结构。

## 产品级关注点
- HEARTBEAT 空文件、只有标题、只有注释、只有空白时不能打扰用户。
- `at` 任务执行一次后必须幂等，不可在每次 tick 或重启后重复触发。
- catch-up 不能无界洪泛；至少要保证一次重启恢复时只补跑到期实例，不制造重复 run。
