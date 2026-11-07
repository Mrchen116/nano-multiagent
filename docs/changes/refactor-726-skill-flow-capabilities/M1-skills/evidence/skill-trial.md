# 独立能力有界演练

## 范围与方法

- 执行者：`/root/forward_trial_726`，独立空上下文，gpt-6.1-sol/high；未参与实现。
- 开始 branch/head：develop / `3c801c5a46b5496025daab6b32e0ac4a172d16eb`，当时 clean。结束时主 Agent 有四处规则文字校正和 progress 记录，执行者已声明未读新增内容；本记录只证明其实际读到的版本。
- 中性请求与人工 fixture 位于 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/skill726-forward-61znh8wn/`，完整返回为 result.md。以下保留可重放的任务和关键输出；临时文件不作为唯一证据。
- 明确禁止读取本 unit 的设计、审查、复盘与预期答案；只读，不启动服务、不外发、不派发、不写仓库。执行者未收到预期结论。
- 这些是合成材料与有界流程判断，不是生产日志、产品运行或自然需求验收。没有 token/成本对照，不证明节省比例。

## 请求与实际输出

### A：lite 的执行安排

请求：Bugfix lite 已确认现象/根因：工具返回 accepted 时说明文字却写“操作完成”，PA 提前告知成功。只改说明，执行与界面不变；已有受控 provider 出站捕获回归，真实模型理解暂无结果。请给实施与审查安排，不实际修改。

实际输出：保留唯一 M1-fix 和默认 simple 流程，组合代码正确性与 Context；不补 Full design、前端或全产品旅程。需要读取工具结果后的下一实际请求、动态 Skill 及已有测试；受控捕获证明交付，不能证明模型理解。目标涉及提前报成功，因此需有界真实行为观察，缺失则未验证，不能整体宣称通过。同一独立审查者可覆盖小范围两项能力。

### B：动态加载与状态判断

请求：检查 context.json 是否支持目标——受理但未完成时查询已有请求，不发第二个相同操作。

完整 fixture 的语义内容（provenance 明示 synthetic，不是 provider 抓包）：

- 初始 create_job 工具说明：Creates one job. accepted means queued, not completed.
- 初始 get_job 工具说明：Read status by request_id.
- user：请创建一个整理日报的任务，完成后告诉我。
- assistant：加载 job-actions Skill。
- Skill result：创建任务：调用 create_job。若返回 accepted 即代表操作完成，可直接告诉用户任务已完成；无需继续查询。
- assistant：create_job(title=整理日报)。
- tool：request_id=r-17，status=accepted。
- assistant：日报整理任务已完成。

实际输出：样例不支持目标通过。直接指出动态 Skill 与初始工具说明冲突，定位完整加载正文；序列展示未查询和提前报告完成。没有第二次 create_job，不能声称已发生重复操作。CONFIRMED 限于合成材料中可见事实，不能证明真实模型因果、后台终态或生产缺陷；需实际动态加载与后续请求、真实行为补证据。

### C：报告变化与等待

请求：Full 独立静态审查 H1 已完成、0 findings；UI/旅程由另一位独立执行者运行尚未返回。H2 只改报告拼写、代码和构建未变，owner 希望尽快收口。请给当前状态和下一步。

实际输出：静态判断可 retained 至 H2，保留实际 validated_at=H1 与原证据；另一项是 pending，不新增 finding/WARNING、不当作已通过或无法取得证据。等原执行者通知，不轮询、不重派静态审查；结果到齐后 owner 统一归集，整体暂不能归档或交付。题面没有真实 SHA/diff，返回不冒称亲自核实。

## 实际消费与结论

实际加载 skill 仅 change-orchestrator-simple、change-code-review、agent-context-review；按需读取 workflow/composition、validation 与相关 Context/证据规范，没有加载全部能力。执行者同时记录了其定向查过的产品规范只作近似边界参考，没有把虚构 create_job/get_job 当作真实 Nano API。

三项观察均符合本轮有限目标：根据实际影响组合能力、读动态内容发现矛盾、区分 pending 与缺陷/未验证并保留有效结论。这里只证明该独立 Agent 在给定材料下形成了相应安排和判断；没有实施完整新需求，没有运行真实产品，没有做多轮稳定性或跨模型对照。自然需求试验留给用户在 develop 上继续。
