# perf-746 实现审查

独立审查由未参与实现的 code_review 执行，范围为 `c49c63461..ea172f04d`。R1 确认当前可读范围、游标、回放窗口和事件顺序符合 delta；发现头查询需要按 `created_at` 访问正文表。R2 复验覆盖索引，使用提交中的真实 SQL 和 schema 确认只有一个索引读取游标，达到事件上限可提前结束，无开放 findings。

本地通过中心 tenancy 10 项、中心 WebSocket 与 Agent lifecycle 11 项、Web user-stream 17 项，以及中心 build。覆盖索引修正后复跑 tenancy 10 项及 user-stream 17 项。文件 SQLite 探针中，2,001 条各 128 KiB 正文的事件，头查询由约 37.3 ms 降到约 0.41 ms。这个数据衡量索引修正的读取成本。中心回归另验证不可读积压、可读超期与超量、零游标及无缺口。生产浏览器端到端延迟待测。
