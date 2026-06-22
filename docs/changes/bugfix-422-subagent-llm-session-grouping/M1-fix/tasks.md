# M1-fix tasks — bugfix-422

范围：让 `agent` tool 三条子 agent 启动路径（前台 / 后台 / 续传）在 LLM 请求层复用父 session id，
使子 agent 的 LLM 请求在 LLM proxy session-inspector 中归入父 session。保住"子 agent 本地 session id
独立"不变量。

测试策略：以单测断言为主口径（fix.md 澄清记录 Q2）——三条路径分别断言 `llm_session_id == 父 id`、
子 agent 本地 `agent_session_id != 父 id`；外加一条经真实 wiring + RuntimeRunner 的端到端集成断言。

- [DONE] R1（C1 红测）：unit 3 例 + integration 1 例，先行失败
- [DONE] R2（C2 实现）：plumbing 4 文件透传 `llm_session_id` + agent.py 三处调用点；修受影响桩
- [DONE] R3（C3 文档）：回填 fix.md 修复 / 验证两段
