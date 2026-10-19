# 2026-10-17 原生语义修订回归

本轮替代旧热更新验收结论。基线 HEAD `36ebeed51ea20e4e4157fce7a285b63320b5e6bd`，实现为其后本轮提交；DSH 锁定包 `0.2.1-alpha.1`，参考源码 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`。

## Red 与诊断

- 将原测试的覆盖后立即生效断言改为原生 `restart-required`，旧实现返回 `applied`，有效失败记录 `/tmp/feat614-revision-native-red.log`。
- 去除 generation 后，原生管理器对相同路径重装不能唯一推断依赖变化；使用它支持的 `包名@link:绝对路径`，不另造安装协议。
- 原生 linked resolver 按 peerDependencies 复用宿主包；fixture 与导入 DSH 的模板声明 peerDependencies。没有安装第二份 runtime。
- Include 提前恢复派生 runtime.json 的注册，使 refresh 将工具误标为 baseline；诊断日志记录 workspace_echo 同时存在于 schemas 和 baseline 而 workspace tools 为空。改用上游 preset 的公开 EntryTree 内存树模式，原生 profile 仍持有安装和启停状态。未保留清空共享配置文件的失败尝试。
- 原生 defineTool 的输出对象同样使用 value DSL；模板将 required 标在各属性并声明 additionalProperties，不混用 raw schema。

## Green

`pnpm exec vitest run packages/dsh-integration/tests/workspace-tools.test.ts packages/personal-assistant/tests/builtin-skills.test.ts`：2 文件 / 2 测试通过，39.66 秒，2026-10-17 00:06；日志 `/tmp/feat614-revision-native-green.log`。

真实锁定 runtime 经公开 RPC 验证：坏源码修复待重启；覆盖更新待重启；重启前和停启后仍执行旧代码；正常重启后本 Agent/同 workspace peer 执行新版；安装/启停选择跨重启保存；新 preview 不丢既有工具也不把 Cron 当 workspace 工具；跨 workspace 与空工具集隔离；异步卸载期间新输入排队；三个随包模板实际安装调用；压缩私有服务和停用回落。

`pnpm build` 与 `pnpm typecheck` 通过，日志分别为 `/tmp/feat614-revision-full-build.log` 与 `/tmp/feat614-revision-typecheck.log`。完整 CI 与新模型轨迹另记，不以本回归替代产品验收。
