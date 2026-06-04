# 条件轮询替代写死等待(Condition-Based Waiting)

## 这是什么

flaky 测试常常靠**写死的延时**去猜时机(`time.sleep(0.05)`)。这制造竞态:快机器上过、负载高或 CI 里挂。

> **核心:等你真正关心的那个"条件成立",而不是猜"它大概要多久"。**

## 什么时候用

- 测试里有写死的延时(`time.sleep` / `await asyncio.sleep(...)` 纯为等异步完成);
- 测试 flaky(有时过、负载下挂);
- 并行跑时超时;
- 在等一个异步操作完成。

**不要用在**:真的在测时序行为本身(debounce / throttle 间隔)。那种情况**必须注释说明为什么需要这个写死的时长**。

## 核心模式

```python
# ❌ 之前:猜时机
await asyncio.sleep(0.05)
result = get_result()
assert result is not None

# ✅ 之后:等条件
await wait_for(lambda: get_result() is not None, "result 就绪")
result = get_result()
assert result is not None
```

## 常用模式

| 场景 | 写法 |
|---|---|
| 等事件 | `wait_for(lambda: any(e.type == "DONE" for e in events), ...)` |
| 等状态 | `wait_for(lambda: machine.state == "ready", ...)` |
| 等数量 | `wait_for(lambda: len(items) >= 5, ...)` |
| 等文件 | `wait_for(lambda: os.path.exists(path), ...)` |
| 复合条件 | `wait_for(lambda: obj.ready and obj.value > 10, ...)` |

## 实现

```python
async def wait_for(condition, description: str, timeout: float = 5.0, interval: float = 0.01):
    start = time.monotonic()
    while True:
        result = condition()
        if result:
            return result
        if time.monotonic() - start > timeout:
            raise TimeoutError(f"等 {description} 超时({timeout}s)")
        await asyncio.sleep(interval)   # 每 10ms 轮一次
```

## 常见错误

- ❌ **轮太快**(`sleep(0.001)`)→ 浪费 CPU。✅ 每 10ms。
- ❌ **没超时** → 条件永不成立时死循环。✅ 永远带超时 + 清晰报错。
- ❌ **缓存了陈旧数据**(循环外取一次值)。✅ 在循环内调取最新值。

## 写死时长"确实正确"的情况

```python
# 工具每 100ms tick 一次,需要 2 个 tick 才能验证部分输出
await wait_for_event(manager, "TOOL_STARTED")   # 先:等触发条件
await asyncio.sleep(0.2)                          # 再:等已知的定时行为
# 0.2s = 100ms 间隔的 2 个 tick —— 有注释、有依据
```

要求:① 先等触发条件;② 基于**已知**时序(不是猜);③ 注释说明为什么。

> 与本项目 memory 一致:flaky 不许"没看 traceback 就判 flaky"。用条件轮询根治竞态,而不是加 `sleep` 或重试蒙混。
