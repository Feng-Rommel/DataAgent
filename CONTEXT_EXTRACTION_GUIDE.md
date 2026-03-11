# 上下文提取功能说明

## 概述

上下文提取功能已经完全集成到 `CodeProgrammer` 中，无需修改 main.py 或 ui_app.py，开箱即用。

## 工作原理

当调用 `CodeProgrammer.generate_code()` 时，内部会自动执行以下步骤：

1. **接收完整历史**：从 `get_notebook_history()` 获取完整的 Notebook 历史
2. **智能筛选**：使用 LLM 分析历史记录，筛选出与当前任务最相关的 cells
3. **生成代码**：使用精简后的上下文生成代码

## 自动触发条件

上下文提取只在以下情况自动触发：
- notebook_history 不为空
- notebook_history 不是 "暂无历史代码。"
- notebook_history 的 JSON 数组长度超过 max_cells（默认为 5）

## 使用示例

### main.py 和 ui_app.py（无需修改）

```python
# 和以前一样，直接调用即可
steps = code_programmer.generate_code(
    content,                           # 用户任务
    data_context=current_data_context,   # 数据上下文
    notebook_history=get_notebook_history(),  # 完整历史（自动筛选）
    completed_tasks=get_completed_tasks()
)
```

## 日志输出

当上下文提取被触发时，你会看到类似输出：

```
    [上下文提取] 正在分析 15 个历史 cell...
    [上下文提取] 从 15 个历史 cell 中筛选出 3 个最相关的
```

如果 LLM 解析失败，会自动降级：

```
    [上下文提取] JSON 解析失败，使用降级策略: ...
```

## 筛选标准

LLM 会根据以下标准判断相关性：

**优先保留**：
- 数据加载（readRDS, CreateSeuratObject）
- 变量定义（参数设置、阈值设定）
- 前置步骤（数据预处理、降维等）
- 类似功能的代码

**过滤掉**：
- 无关的探索性代码
- 失败的代码尝试
- 调试代码

## 性能优化

### Token 节省

假设历史记录包含 15 个 cells：

| 场景 | Token 数量 | 说明 |
|------|-----------|------|
| 之前 | ~3000 tokens | 所有 15 个 cells |
| 现在 | ~600 tokens | 只保留 3 个最相关的 |
| 节省 | ~2400 tokens | 80% 的节省 |

### 额外开销

- 每次生成代码前会增加 1 次 LLM 调用（约 500-1000 tokens）
- 总体权衡：增加少量开销，节省大量 prompt 长度

## 配置调整

如需调整筛选策略，修改 `src/code_programmer.py` 中的参数：

```python
# 在 generate_code 方法中修改
notebook_history = self._extract_relevant_context(
    current_task=user_requirements,
    full_history=notebook_history,
    max_cells=5  # ← 修改这个值（建议 3-10）
)
```

## 注意事项

1. **透明性**：上下文提取对调用者完全透明
2. **降级机制**：LLM 失败时自动使用简单截断策略
3. **兼容性**：与现有代码完全兼容，无需修改
4. **可控性**：通过 max_cells 参数控制筛选力度

## 调试技巧

如果想禁用自动筛选（用于对比测试），临时注释掉筛选代码：

```python
# 注释掉这行以禁用筛选
# notebook_history = self._extract_relevant_context(...)
```

## 未来优化

可能的改进方向：
1. 添加缓存机制（相似任务重用筛选结果）
2. 支持增量筛选（只对新 cells 进行分析）
3. 可配置的筛选策略（严格/宽松模式）
