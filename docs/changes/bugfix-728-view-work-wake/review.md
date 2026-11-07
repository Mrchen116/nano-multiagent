# bugfix-728: 验证与审查

## 状态

Active，待用户真实试用确认；独立审查固定模型配置存在能力缺口，尚未放行。不得把作者自测或待审 PR 当作用户验收/完整归档。

## 版本与范围

- 执行者：#473 主实施者（独立工作区，非用户验收者）。
- executed_base: `eeaea47921806936da20e78c9ed96167716f5037`。
- validated_at / effective_through：`606ad3da50b508f7c6fabb97091f61ccb298ad0c`；下述最终回归均在该冻结实现上执行，后续报告补充不改变实现。
- 本任务 dirty 范围：Work API/records/types；Web message-pane 链接与测试、Work panel/API/测试、双语提示；本 unit 文档与 backend focus 回归。主 checkout 的用户修改未操作。

## 自动化与静态检查

- 最窄 backend 真实进程/socket：`pnpm exec vitest run apps/im-server/tests/e2e/work-message-focus.test.ts` 通过1项，覆盖同Agent25轮、最新页之外的早期回复、两条不同回复/重复早期定位、续页、过程读取、缺失锚点及认证。
- 最终完整 IM 回归低并发通过：65文件 / 405项，`pnpm exec vitest run apps/im-server/tests --maxWorkers=1`，本地原始输出 `output/im-tests.log`。
- 最终完整 Web suite 低并发通过：113文件 / 1082项（含 message-pane102项、Work panel28项；后者覆盖延迟body后滚动/刷新不抢阅读），本地原始输出 `output/frontend-tests.log`。
- `pnpm build`、`pnpm typecheck` 通过；冻结实现后再次前端 `tsc -b && vite build` 通过（已有大chunk提示，不影响构建成功）。
- helper/contract pytest：135 passed / 28 deselected（`python -m pytest -m 'not e2e' -q`）；`ruff check .`、`scripts/docs-check`（279 maintained sources / 69 routes）、`git diff --check` 通过。
- 完整 pnpm test 曾在共享机器 load≈34 时出现无关 DSH 集成超时，已取消该全并发运行，不能声称完整 runtime suite 通过；本地原始输出 `output/backend-tests.log`。以上低并发 IM 回归是实际通过的范围，不替代全 runtime suite。

## 真实用户路径：作者自测

环境：隔离 daily 模板，UI/IM `http://127.0.0.1:58054`；node `wt-fix-473-view-work-95711`，开发分支源码；测试用户 nano。没有生产数据或公网隧道。

使用真实模型 P（daily-product、codexOAuth:gpt-6.1-sol/high）在“研发日常”生成两次独立 Inbox wake-up；两次分别读取输入、执行只读 bash，再实际 send_message。

| 回复 | 消息ID | 实际执行/轮次 | 真实路径观察 |
|---|---|---|---|
| 定位验收 A：已核查当前目录。 | `d7ea73916e094eaca9e3cf72755813dc` | `6b96f92c-1617-4710-aebc-5e325f202390` / `1` | 气泡链接点击进入同Agent Work，自动展开，8工具可见；bash展开核实 `$ pwd` |
| 定位验收 B：已核查日期。 | `01587998798544179009e8fc4329028f` | 同一执行 / `2` | 点击B进入轮次2，4工具可见，未误定位A；返回后再次点击A仍正确 |

最终滚动方案实测：A/B目标行均位于 viewport top≈47.8px（固定主栏下方），open=true，直接看到工具，而非仅验证URL。首次空摘要阶段滚动过早的自检发现已修正为首批过程就绪后滚动一次。

本地原始产物（不提交）：
- `output/playwright/reply-a-work-final.png`、`reply-b-work.png`：1200×732实际画面；冻结实现production build重新加载后 `reply-a-frozen-build.png` 仍准确展开A及实际bash输出。
- `.playwright-cli/page-2026-11-07T17-51-33-103Z.yml`：重复点击A的真实快照。
- `.playwright-cli/page-2026-11-07T17-52-21-258Z.yml`：A的实际bash内容。
- `output/playwright/delivery-provenance.json`：测试DB中两条真实投递事实，无凭据。

这些为作者自测，不是独立产品验收或用户确认；真实浏览器仅有两轮，默认20轮外历史另由25轮真实socket回归覆盖，不冒称真实模型生成25轮。

## 独立审查能力差异

当前 native subagent 工具只接受 description/prompt/background，不能指定 model/reasoning_effort；Codex适配默认代码审查要求 gpt-6.1-sol/high，并要求显式派发。父Agent确认其侧同样无此字段，要求冻结后交中性事实包，由其处理人类决定。未用继承模型冒充符合配置、未自审放行、未另造CLI协议。

审查问题：精确关联是否只来自授权Agent实际投递、默认页之外/续页是否可达、展开/迟到同步/重复导航/阅读恢复是否正确、最终delta是否覆盖目标。实际独立结论待补。

## 人类试用与恢复入口

须在运行节点同机浏览器打开（loopback不是远程可访问链接）：
1. 打开 `http://127.0.0.1:58054/chat/c_iy796v97`，隔离测试账号 `nano / nano1234`。
2. 找到 P 的“定位验收 A…”和“定位验收 B…”两条回复，分别点击 View Work。
3. 每次应进入 P Work 并直接展开对应Inbox唤醒；浏览器返回聊天，再点较早A复验。

作者自建的 `fix473` 浏览器已关闭，预览服务按待试用要求保留于 tmux `fix473-preview`，运行数据仅在本worktree。停止：`./scripts/e2e-down.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/fix-473-view-work`。不要重新执行up而清空供用户试用的两条记录。PR未合入及用户待试用，开发worktree保留。

## 未完成收口

用户实际确认、合规独立代码审查、最终CI结果、canonical delta归并和归档均须据真实事实继续。无合并/生产部署授权。
