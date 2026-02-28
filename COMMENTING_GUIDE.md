# COMMENTING_GUIDE

目标：让调用者不用读实现也会用；让维护者看懂“为什么/约束”，避免过期注释。

## 1) Docstring（Google 风格）— 写“契约”
### MUST 写 docstring
- 所有 public：module / class / function / method
- 入口：CLI、HTTP/RPC handler、任务入口、SDK API
- 抽象基类/接口

### Docstring 写什么（类型标注已强制，所以不重复类型）
- 一句话 summary（动词开头）
- Args：**语义/单位/范围/默认行为**（不写类型）
- Returns：**语义**（是否可能为 None、是否排序/去重等）
- Raises：**失败条件 + 语义**（可重试/幂等性如相关）
- Side Effects：网络/DB/文件/缓存/是否 mutate 入参（如相关）
- Notes：性能/并发/安全关键点（如相关）
- Examples：仅对“容易用错”的 public API 写 1 个例子

模板：
```python
def f(x: int) -> int:
    """Do X.

    Args:
        x: Meaning, range/units, default semantics.

    Returns:
        Meaning (None? ordering?).

    Raises:
        ValueError: When ...
    """
```

## 2) 注释（comments）— 写“意图”

原则：代码表达“做什么”，注释表达“为什么/约束/边界/代价”。

### MUST 注释的场景
- 业务规则：看代码不知“为什么这样算/判”
- 边界/历史兼容：特殊 case、脏数据修复
- 性能关键：复杂度、缓存、避免重复 I/O
- 并发/一致性：锁/事务/竞态规避、幂等键
- 安全：鉴权/脱敏/加密假设
- 协议/格式：字段语义、版本兼容策略
- workaround/技术债：必须 TODO/FIXME（含 issue id + 删除条件）

### MUST NOT
- 复述代码（如 i += 1  # increment i）
- 写实现流程细节（除非与正确性/性能强相关）

### 颗粒度
- 优先块注释解释一段逻辑
- 行尾注释只用于“这行很怪但必须这样写”

## 3) TODO/FIXME 格式（MUST）
- TODO(<issue-id>): <改进> — <删除条件>
- FIXME(<issue-id>): <缺陷> — <影响/风险>

## 4) 快速自查
- public API 都有 docstring（Args/Returns/Raises/Side Effects 需要则写）
- 写清副作用、失败模式、可重试/幂等（如相关）
- 性能/并发/安全/协议关键点有注释
- 没有“复述代码”的废注释