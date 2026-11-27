# bugfix-802 审查与验证

独立 change-code-review 审查了基线 `3b4c0f022` 到实现 `1a452e889` 的全部八个文件，工作区干净。审查确认独立 job 沿用原有的 PR 范围、分支名传参和退出码；两条测试保留断言、超时预算和原有 pending RPC 诊断。Vitest 4.1.11 在外层用例超时后仍执行 onTestFinished。无待修复 finding，no spec delta。

- 本地 Node 24.22.1、pnpm 11.7.0。归档契约 24 项通过，两个受影响测试文件的 7 个用例通过，构建和文档完整性检查通过。
- 临时测试设置 75ms 外层超时并在第二阶段等待，Vitest 以失败退出，日志报告最后阶段 waiting for fixture 的耗时 76ms。
- [PR 首轮归档检查](https://github.com/Mrchen116/nano-multiagent/actions/runs/45969293890/job/140405486879)在 workflow 创建后 12 秒输出 active 单元路径，14 秒时结束。前后端测试并行调度。
- develop 当前没有配置 GitHub 强制必过检查，CI 以失败状态提示开发者。本次变更属于 CI 工作流与测试诊断。
- 使用默认 CI reporter 本地复核两条用例的成功日志。插件用例 58.9 秒，其中三个模板的安装与调用 14.5 秒；记忆用例 13.8 秒，其中配置与预览 4.9 秒。两项均为本机单次观测。
- 用户确认反馈效果符合预期，要求归档后交付 PR。

## 提速验证

独立 change-code-review 核对 `35bf36b5e..cb8e61a87` 和 Vitest 默认分片。两组矩阵保留失败状态，原有构建、测试和辅助检查均有执行入口。审查指出 testing.md 的旧触发路径列表不全，已改为引用工作流。

- [改前全绿运行](https://github.com/Mrchen116/nano-multiagent/actions/runs/45970278548)与[改后首次运行](https://github.com/Mrchen116/nano-multiagent/actions/runs/45975631134)分别用了 21 分 24 秒和 12 分 19 秒。两轮中最后完成的都是 iOS，均已计入 runner 排队。
- 从 workflow 创建到后端全部完成，11 分 35 秒降至 8 分 54 秒。逐文件对照运行日志，原有 300 个文件分别进入两组，各 150 个且交集为空；新基线共 1642 个测试用例通过，先前为 1634 个用例。
- 模拟器测试和 Release 归档各自在独立 macOS runner 上通过。耗时随机器和排队波动，本次对照中各分片重复构建，累计 runner 时间和 PR 墙钟时间是不同指标。
