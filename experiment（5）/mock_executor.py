"""
Mock工具执行器 v3

核心改动：
- execute() 返回 (result, meta) 元组
- meta 包含 actual_params（用于架构层同步messages）和 phase 信息
"""
from typing import Dict, Any, Tuple
import json


MOCK_TOOL_RESULTS: Dict[str, Dict] = {
    "stock_mapping": {
        "success": True, "message": "证券代码映射完成",
        "data": {"stocks": [{"name": "苹果", "code": "AAPL", "market": "纳斯达克"}, {"name": "微软", "code": "MSFT", "market": "纳斯达克"}]}
    },
    "factor_mapping": {
        "success": True, "message": "因子映射完成",
        "data": {"factors": [{"name": "市盈率", "code": "pe_ttm", "unit": "倍"}, {"name": "市净率", "code": "pb", "unit": "倍"}]}
    },
    "industry_mapping": {"success": True, "message": "行业映射完成", "data": {"industry_code": "IT", "industry_name": "信息技术"}},
    "exchange_mapping": {"success": True, "message": "交易所映射完成", "data": {"exchange_code": "NAS", "exchange_name": "纳斯达克"}},
    "factor_selection": {
        "success": True, "message": "因子选择完成",
        "data": {"core_stock_factors": [{"code": "pb", "name": "市净率"}], "core_timing_factors": [{"code": "rsi_14", "name": "RSI14"}]}
    },
    "security_selection": {"success": True, "message": "证券筛选完成", "data": {"securities": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]}},
    "buy_sell_backtest_service": {
        "success": True, "message": "买卖交易模型回测完成",
        "data": {"backtest_results": {"total_return": 0.186, "sharpe_ratio": 1.25, "max_drawdown": -0.12}, "image_component": {"image_id": "buy_sell_001"}}
    },
    "rotation_trading_backtest_service": {
        "success": True, "message": "轮动交易模型回测完成",
        "data": {"backtest_results": {"total_return": 0.256, "sharpe_ratio": 1.45, "max_drawdown": -0.15}, "image_component": {"image_id": "rotation_001"}}
    },
    "fixed_investment_backtest_service": {
        "success": True, "message": "定投交易模型回测完成",
        "data": {"backtest_results": {"total_return": 0.156, "sharpe_ratio": 1.05, "max_drawdown": -0.08}, "image_component": {"image_id": "fixed_001"}}
    },
    "smart_fixed_investment_backtest_service": {
        "success": True, "message": "智能定投交易模型回测完成",
        "data": {"backtest_results": {"total_return": 0.196, "sharpe_ratio": 1.15, "max_drawdown": -0.10}, "image_component": {"image_id": "smart_fixed_001"}}
    },
}


class MockToolExecutor:
    """Mock工具执行器"""
    
    def __init__(self, error_injector=None):
        self.error_injector = error_injector
        self.execution_log: list = []
    
    def execute(self, tool_name: str, params: Dict) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        执行工具调用。
        
        Returns:
            (result, meta)
            - result: 返回给模型的结果 {"success":..., "message":..., ...}
            - meta: 元信息 {
                "blocked": bool,          # 是否被拦截（返回了报错）
                "actual_params": dict,    # "实际执行"的参数（注入时=篡改后，否则=原始）
                "phase": str,             # "inject" | "validate" | "passthrough" | "none"
              }
        """
        if self.error_injector:
            intercept = self.error_injector.intercept(tool_name, params)
            
            if intercept["should_block"]:
                result = intercept["error_response"]
                meta = {
                    "blocked": True,
                    "actual_params": intercept["actual_params"],
                    "phase": intercept["phase"],
                }
                self._log(tool_name, params, result, meta)
                return result, meta
            
            # 放行
            result = MOCK_TOOL_RESULTS.get(
                tool_name, {"success": True, "message": f"{tool_name} 执行完成", "data": {}})
            meta = {
                "blocked": False,
                "actual_params": intercept["actual_params"],
                "phase": intercept["phase"],
            }
            self._log(tool_name, params, result, meta)
            return result, meta
        
        # 无注入器
        result = MOCK_TOOL_RESULTS.get(
            tool_name, {"success": True, "message": f"{tool_name} 执行完成", "data": {}})
        meta = {"blocked": False, "actual_params": params, "phase": "none"}
        self._log(tool_name, params, result, meta)
        return result, meta
    
    def _log(self, tool_name, original_params, result, meta):
        self.execution_log.append({
            "tool_name": tool_name,
            "original_params": _preview(original_params),
            "actual_params": _preview(meta["actual_params"]),
            "result_success": result.get("success"),
            "phase": meta["phase"],
            "blocked": meta["blocked"],
        })
    
    def reset_log(self):
        self.execution_log.clear()


def _preview(params: dict, max_len: int = 0) -> str:
    """参数完整输出"""
    return json.dumps(params, ensure_ascii=False)
