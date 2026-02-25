"""
测试用例定义

每个用例包含：
- user_query: 用户输入
- expected_tools: 期望调用的工具序列
- difficulty: 难度等级
- target_backtest_tool: 最终要调用的回测工具（用于错误注入定位）
- description: 用例描述
"""
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class TestCase:
    id: str
    user_query: str
    expected_tools: List[str]           # 期望的工具调用序列
    target_backtest_tool: str            # 目标回测工具（错误注入的对象）
    difficulty: str                      # easy / medium / hard
    description: str = ""
    expected_params_hint: Dict = field(default_factory=dict)  # 关键参数的期望值提示


# ============================================================================
# 测试用例集
# ============================================================================

TEST_CASES: List[TestCase] = [
    
    # ---- 轮动交易模型（rotation） ----
    
    TestCase(
        id="rotation_001",
        user_query="帮我构建一个美股轮动策略，用市盈率PE从低到高排名选股，每月调仓一次，选前10名，回测近3年表现。",
        expected_tools=["factor_mapping", "rotation_trading_backtest_service"],
        target_backtest_tool="rotation_trading_backtest_service",
        difficulty="medium",
        description="轮动策略-明确因子和调仓频率",
    ),
    
    TestCase(
        id="rotation_002",
        user_query="我想做一个动量轮动策略，在纳斯达克上选成长股，用RSI14做择时，涨幅排名前5买入，持仓超过30天卖出。",
        expected_tools=["factor_mapping", "rotation_trading_backtest_service"],
        target_backtest_tool="rotation_trading_backtest_service",
        difficulty="hard",
        description="轮动策略-复杂条件（择时+持仓天数）",
    ),

    TestCase(
        id="rotation_003",
        user_query="做一个简单的轮动策略，苹果和微软两只股票，按市净率排序每周轮动。",
        expected_tools=["stock_mapping", "rotation_trading_backtest_service"],
        target_backtest_tool="rotation_trading_backtest_service",
        difficulty="easy",
        description="轮动策略-简单两只股票",
    ),

    # ---- 买卖交易模型（buy_sell） ----
    
    TestCase(
        id="buysell_001",
        user_query="用苹果和微软构建一个成长策略，RSI低于30买入，RSI高于70卖出，每次全仓操作。",
        expected_tools=["stock_mapping", "factor_mapping", "buy_sell_backtest_service"],
        target_backtest_tool="buy_sell_backtest_service",
        difficulty="medium",
        description="买卖策略-RSI择时",
    ),

    TestCase(
        id="buysell_002",
        user_query="我看好英伟达，想做一个买卖策略回测，PE低于25倍买入50%仓位，PE超过40倍全部卖出。",
        expected_tools=["stock_mapping", "factor_mapping", "buy_sell_backtest_service"],
        target_backtest_tool="buy_sell_backtest_service",
        difficulty="medium",
        description="买卖策略-PE估值择时",
    ),

    # ---- 定投交易模型（fixed_investment） ----
    
    TestCase(
        id="fixed_001",
        user_query="做一个定投策略，每周定投SPY 500美元，回测5年。",
        expected_tools=["stock_mapping", "fixed_investment_backtest_service"],
        target_backtest_tool="fixed_investment_backtest_service",
        difficulty="easy",
        description="定投策略-简单周定投",
    ),

    TestCase(
        id="fixed_002",
        user_query="我想每月15号定投苹果和微软，各占50%权重，每次投1000美元。",
        expected_tools=["stock_mapping", "fixed_investment_backtest_service"],
        target_backtest_tool="fixed_investment_backtest_service",
        difficulty="medium",
        description="定投策略-多标的月定投",
    ),

    # ---- 智能定投交易模型（smart_fixed_investment） ----

    TestCase(
        id="smart_fixed_001",
        user_query="做一个比特币智能定投策略，用RSI14分档，RSI低于30加倍定投，RSI高于70减半，基础定投500美元每月。",
        expected_tools=["smart_fixed_investment_backtest_service"],
        target_backtest_tool="smart_fixed_investment_backtest_service",
        difficulty="hard",
        description="智能定投-RSI分档策略",
    ),
]


def get_test_cases_by_tool(tool_name: str) -> List[TestCase]:
    """按目标回测工具筛选用例"""
    return [tc for tc in TEST_CASES if tc.target_backtest_tool == tool_name]


def get_test_cases_by_difficulty(difficulty: str) -> List[TestCase]:
    """按难度筛选用例"""
    return [tc for tc in TEST_CASES if tc.difficulty == difficulty]


def get_all_test_cases() -> List[TestCase]:
    return TEST_CASES
