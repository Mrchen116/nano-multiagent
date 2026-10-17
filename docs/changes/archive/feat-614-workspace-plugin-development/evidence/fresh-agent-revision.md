# 2026-10-17 新 Agent 常规场景

冻结实现 `f56e5e6d89cd496ef0bcdf75816db37313281a63`；原生锁定 DSH `0.2.1-alpha.1`。本文件记录主 Agent 的补充实测，独立验收见 [acceptance](../acceptance.md) 的新 Round；旧热更新与低阈值压力样本不作为本轮成功证据。

## 装配与方法

- 主栈 `/tmp/feat614-r2-main`、独立验收栈 `/tmp/feat614-r2-review` 各有新 owner、node identity、workspace、数据与高位端口。`e2e-up.sh` 从冻结构建启动；生产服务、主 checkout 与共享代理未改动。
- 新 global Agent：DeepSeek `deepseek:deepseek-v4-flash`、Astra `codexOAuth:gpt-6-astra`；默认 Skill discovery，正常 Auto，测试审核模型启动前配置为 `codexOAuth:gpt-6.1-sol`。所有数据为合成数据，没有外部频道发送。
- 随包与两个实际安装 Skill 的 SHA-256 均为 `b51ff7be7fd2e1adc1a4404292917290e852fe9eccf53a4da61033af8c84bc24`。轨迹确实包含 `skill(name=nano-plugin-development)`、describe_api、当前安装包 README/types 读取，不能只凭源码存在判断使用成功。
- 用户输入只给业务目标，没有 Skill 名、API 参数、代码或安装顺序。完整分页 Work 轨迹、聊天消息与输入保存于 `/tmp/feat614-r2/main-evidence`；auth/config/日志不提交。

## 主栈可复查结果

| 场景 | 聊天及关键 Work seq | 观察 |
|---|---|---|
| 读取 CSV 的可复用报销工具 | `c_eieyfhua`；Skill 20、接口 50、首装 173、实调 179 | 6 笔 6500 分；餐饮 3000、交通 2900、缺失类别 600；列出 -500 分与缺失类别，实际发送到原聊天。|
| 增加可选月份并覆盖安装 | 同聊天；安装 255、旧调用 258 | 原生 restart-required，当前仍为 6 笔 6500 分。Agent 明确已保存但没有生效，未反复启停或重装强迫刷新。|
| 正常重启后运行新版 | 同聊天；实调 288 | 主 Agent 确认两位业务 Agent idle 后，使用原 CLI 对本专用 Node 正常 restart；Node 恢复 online。原生已安装工具返回范围 2026-10、5 笔 5600 分，聊天准确交付。`live-month-verification.json` 保存该实际调用。|
| 可启停报销报告格式 | `c_hzfjfni2`；首装 120、停用 138、启用 145、独立子任务 154 | 均 applied；示例报告按“汇总/异常/待核对”组织，最终保持启用。|
| 后续普通聊天 | 同聊天；发送 217 | 一句话给休息建议，没有套用报销三段格式。|
| 现有插件交给 Cron 手动运行 | `c_eieyfhua`；后续实际工具调用 328、发送 337 | 创建周一 9 点提醒并手动触发；当前轮结束后，后续输入调用已安装工具返回 5600 分并发送消息，没有 sleep 自等或重复触发。按要求停止测试提醒，原生工具实际删除提醒，list 为空。没有将这次手动运行算作定时到点触发证据。|

## 偏差与归因边界

- DeepSeek 有额外 DSH 环境、安装目录与声明链探查，且有 BSD `cat -A` 兼容性错误；不是无错误、无额外负担的轨迹。未见它读取凭据、无关会话或修复宿主环境。
- 待重启期间，DeepSeek 复制源码、用 defineTool 桩做了离线业务逻辑检查（seq 264）。这不验证原生 schema/安装活性，本轮不将它算作新版本已可用证据；实际生效以重启后 seq 288 为准。它在交付中保留了待重启限制，但把实际位于 workspace 内的临时目录说成“工作区外”，属于残留的报告事实错误。
- 临时验证首次删除未证明归属的目录被 Auto 拒绝（seq 261）；随后先创建本次临时文件、完成测试并在已知路径清理，未重复同一被拒动作或改审批。原拒绝保留。
- 独立验收另观察到生成插件的 schema/cwd 错误，以及一个 Agent 创建共享 Skill、另一 Agent 随后读取的协作副作用。原样本保留；索引的单独对照使用全新 `/tmp/feat614-r2-index` owner，避免把自生成指导贡献算给随包 Skill。
- 这些样本支持“关键更新语义没有再被指导误判”，不能证明模型始终遵守 Skill、没有探索浪费或不会写错业务插件。未观察的自动压缩也不冒称验证完成。

## 手动压缩入口的必要补清

旧独立压缩样本在首装成功后继续约百次工具探索，准确报告没有发生压缩；后续试图复制全部 session、另存摘要，分别被正常 Auto 拒绝。不能把它记为高效或完全遵守指导的轨迹，也不能把拒绝后实际没有越界读写说成没有越界尝试。用户实际 `/compact` 随后成功压缩 186 项，原生事务保存 start/summary/end；摘要与继续对话保留预算 28600、离线首版、周五供应商报价 planned、云同步 undecided。停用后另一次 `/compact` 压缩 52 项，验证实际默认回落及继续。

`f09df0d25` 仅补充 compaction reference 的既有用户命令入口与当前轮结束交接时机，并在 design 说明原因（共 4 行新增）；原生运行时代码保持 `f56e5e6d8`。来源为 current global-agent 手动压缩契约及原生 idle 要求。独立 code-review Round 5 / verification Round 3 确认为必要 Nano 差异，pass/aligned。Skill 装配窄测 1/1、冻结构建通过。

该补充另外使用新 `/tmp/feat614-r2-compact` owner 的 DeepSeek，以同一自然输入做单次对照；实际安装 reference 与源码 SHA-256 均为 `0554e8733d11803fa5a0e0ab2cc803e7f73af0e8049673de3aa2861707ef09f7`。结果由 acceptance 新 Round 单列，不覆盖旧样本，不靠追加代码/API提示收窄任务，不把单次对照当作严格因果实验。

新样本 `c_nvho5bwk` 的首轮 16.2 分钟/129 次工具调用（旧样本 16.6 分钟/99 次），因此**没有效率改善证据**。seq19 确实读取新增说明；自行创建/首装/启停/台账工具成功，准确交付用户 `/compact` 交接，未重构 Host 控制、未读取其他 session 内容，仍有大量源码和目录探查；首次误调不存在的 run_in_background 后自行改用 bash，原错误保留。

随后从 idle 真实发送 `/compact`：用户收到“已压缩247项”，session `3a17dd48-6c58-4696-b0e3-25c40d8a9855` 的 seq618/start、619/summary、621/end（事务 `c2fc39a8-c9ee-456f-a114-0ccecfbda75d`）。摘要除原生文本外，有插件定义的第二文本块“项目决策（本地台账，逐条原样保留）”，包含四项事实及状态，业务贡献可直接观察；证据 `/tmp/feat614-r2/compact-evidence/manual-events.json`。本次没有自然触发自动压缩，保留为未观察及已披露的验收证据缺口。

续聊最终正确给出四项状态，但又花 4.6 分钟/28 次工具调用检查当前 session；尝试解压复制到临时文件被 Auto 拒绝，随后直接读取、使用现有 zstd，未人工放行，未读取其他 session 内容。这不是效率或零摩擦的成功。独立产品最终 **pass-with-issues**：自动新样本 E1 仍 inconclusive，模型调查成本/拒绝摩擦另记 minor；其他必验通过且无新增宿主实现阻塞，按首文档显式验收边界收口。

## 本次现场清理

四个专用栈均通过 e2e-down 停止，自己创建的 tmux 已移除。最终 Node/DSH：main 37770/37778、review 40258/40262、index 38228/38233、compact 40393/40397 均退出；IM 62633/62632/64783/50958 均关闭。证据与合成源码/数据保留在 `/tmp/feat614-r2*`，不提交 config、auth、日志、PID、数据库或完整会话。共享模型代理及生产服务未操作。
