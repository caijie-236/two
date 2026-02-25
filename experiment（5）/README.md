# 金融Agent架构对比实验框架

## 实验目标

对比两种处理复杂工具Schema的架构方案在 **正常执行** 和 **报错纠正** 场景下的表现差异。

## 架构说明

### 架构A：双模型 + Skills纠错
```
用户输入 → 主Agent(简化工具, function call) → 选工具
                                              ↓
                                    简单工具 → 主Agent自行填参 → 执行
                                    复杂工具 → Worker模型(完整Schema, function call) → 抽参 → 执行
                                                                                           ↓
                                                                                    报错 → 主Agent调用 get_tool_schema(Skills)
                                                                                           ↓
                                                                                    查看完整Schema → 修正参数 → 重新执行
```

### 架构B：懒加载（Lazy-Loading）
```
用户输入 → 主Agent(简化工具, function call) → 选工具
                                              ↓
                                    简单工具 → 直接执行
                                    复杂工具(首次) → 返回完整Schema（不执行）
                                    复杂工具(再次) → 按Schema填参 → 执行
                                                                    ↓
                                                              报错 → 模型已有Schema → 直接修正 → 重新执行
```

## 文件结构

```
experiment/
├── main.py              # 实验入口脚本
├── config.py            # 配置文件（模型、实验参数）
├── tool_schemas.py      # 工具定义（简化版 + 完整版）
├── error_injector.py    # 错误注入系统（核心）
├── mock_executor.py     # Mock工具执行器
├── architecture_a.py    # 架构A实现
├── architecture_b.py    # 架构B实现
├── test_cases.py        # 测试用例
├── runner.py            # 实验运行器 + 统计汇总
└── README.md            # 本文件
```

## 快速开始

### 1. 配置API Key

```bash
export OPENAI_API_KEY="your-key-here"
# 可选：自定义模型和endpoint
export MAIN_AGENT_MODEL="gpt-4o"
export WORKER_MODEL="gpt-4o"
export OPENAI_BASE_URL="https://your-endpoint/v1"
```

### 2. 运行模式

```bash
# 测试错误注入系统（不需要API Key）
python main.py --mode inject_test

# 查看所有可用选项
python main.py --mode list

# 快速测试（1个用例，2种架构对比）
python main.py --mode quick

# 完整实验（所有用例 × 所有场景 × 3次重复）
python main.py --mode full

# 单次运行（指定用例、架构、场景）
python main.py --mode single --case rotation_001 --arch A --scenario rotation_missing_selection
python main.py --mode single --case rotation_001 --arch B --scenario rotation_missing_selection
```

## 错误注入系统

### 工作原理

错误注入器在 **工具执行层** 拦截，对模型完全透明：

```
模型生成参数 → [ErrorInjector拦截] → 篡改参数/返回报错 → 模型看到报错 → 尝试修正
```

### 添加新的错误规则

在 `error_injector.py` 的 `ERROR_RULE_REGISTRY` 中添加：

```python
"your_new_error": ErrorRule(
    error_type=ErrorType.MISSING_REQUIRED_FIELD,  # 错误类型
    tool_name="rotation_trading_backtest_service",  # 目标工具
    field_path="arg0.some.nested.field",           # 字段路径
    error_message="Missing required field 'some.nested.field'. ...",  # 报错信息
    drop_field=True,  # 是否删除该字段
),
```

然后在 `get_experiment_scenarios()` 中创建使用该规则的场景：

```python
"your_scenario": [
    InjectionScript(
        tool_name="rotation_trading_backtest_service",
        sequence=["your_new_error", "SUCCESS"]  # 第1次报错，第2次成功
    )
],
```

### 支持的错误类型

| 类型 | 说明 | 注入方式 |
|------|------|----------|
| MISSING_REQUIRED_FIELD | 缺少必填字段 | 删除字段 |
| WRONG_TYPE | 字段类型错误 | 修改值类型 |
| WRONG_ENUM_VALUE | 枚举值不合法 | 修改为无效值 |
| INVALID_FORMAT | 格式错误 | 修改格式 |
| VALUE_OUT_OF_RANGE | 值超出范围 | 修改为越界值 |
| CUSTOM | 自定义 | 自定义mutate_fn |

## 评测维度

| 维度 | 说明 |
|------|------|
| 平均轮次 | 从开始到完成的对话轮次 |
| 工具调用次数 | 总工具调用数（含Skills/Schema加载） |
| 报错次数 | 工具返回错误的次数 |
| 纠错成功率 | 报错后成功修正的比率 |
| Token消耗 | 输入+输出Token总量 |
| Schema查看次数 | 架构A=Skills调用数，架构B=懒加载次数 |

## 添加新测试用例

在 `test_cases.py` 中添加：

```python
TestCase(
    id="your_case_001",
    user_query="你的测试查询",
    expected_tools=["tool1", "tool2"],
    target_backtest_tool="target_tool_name",
    difficulty="medium",  # easy/medium/hard
    description="用例描述",
),
```
