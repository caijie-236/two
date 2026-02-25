"""
工具定义：包含简化目录（主Agent看到的）和完整Schema（Worker/Skills/LazyLoad看到的）
"""
from typing import Dict, List, Any
import json


# ============================================================================
# 简化工具目录 —— 主Agent在function call中看到的工具定义
# 只有工具名 + 简短描述 + 极简参数（或仅一个query参数）
# ============================================================================

SIMPLE_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "stock_mapping",
            "description": "证券代码映射工具：将用户输入的股票/ETF表述智能匹配为标准证券代码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "包含股票信息的用户查询"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "factor_mapping",
            "description": "因子代码映射工具：将用户提到的因子表述（如ROE、PE）匹配为标准因子代码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "包含财务指标信息的用户查询"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "industry_mapping",
            "description": "行业代码映射工具：将用户提到的行业表述匹配为标准行业代码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "包含行业信息的用户查询"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exchange_mapping",
            "description": "交易所代码映射工具：将用户提到的交易所表述匹配为标准交易所代码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "包含交易所信息的用户查询"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "factor_selection",
            "description": "因子选择工具：根据交易模型类型、标的类型、策略风格，从因子库中筛选对应场景的选股/择时因子。",
            "parameters": {
                "type": "object",
                "properties": {
                    "trading_model": {"type": "string", "description": "交易模型类型"},
                    "asset_type": {"type": "string", "description": "标的类型"},
                    "strategy_style": {"type": "string", "description": "策略风格"},
                    "user_specified_factors": {"type": "array", "items": {"type": "string"}, "description": "用户明确提到的因子代码列表"}
                },
                "required": ["trading_model", "asset_type", "strategy_style", "user_specified_factors"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "security_selection",
            "description": "证券筛选工具：根据选股条件组合从股票池中筛选TOPN证券标的。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "选股需求描述"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buy_sell_backtest_service",
            "description": "买卖交易模型回测工具：基于择时因子条件模拟买入/卖出，计算策略核心指标并输出可视化结果。需要提供标的代码、资产类型、买入规则、卖出规则等参数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "回测需求描述"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rotation_trading_backtest_service",
            "description": "轮动交易模型回测工具：基于选股因子和择时因子实现动态轮动交易策略回测。需要提供选股因子配置、择时规则、资产类型等参数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "轮动回测需求描述"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fixed_investment_backtest_service",
            "description": "定投交易模型回测工具：模拟定期定额投资策略的历史表现。需要提供标的池配置、定投金额、定投频率等参数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "定投回测需求描述"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "smart_fixed_investment_backtest_service",
            "description": "智能定投交易模型回测工具：根据择时因子动态调整定投金额。需要提供标的池、分档规则、择时因子等参数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "智能定投回测需求描述"}
                },
                "required": ["query"]
            }
        }
    },
]


# ============================================================================
# 完整Schema定义 —— Worker/Skills/LazyLoad模式下看到的完整参数结构
# 这里只放复杂工具的完整schema，简单工具（mapping类）本身就是完整的
# ============================================================================

def get_full_tool_schemas() -> Dict[str, Dict]:
    """返回所有工具的完整Schema（key=工具名）"""
    return {
        "stock_mapping": SIMPLE_TOOL_DEFINITIONS[0],
        "factor_mapping": SIMPLE_TOOL_DEFINITIONS[1],
        "industry_mapping": SIMPLE_TOOL_DEFINITIONS[2],
        "exchange_mapping": SIMPLE_TOOL_DEFINITIONS[3],
        "factor_selection": SIMPLE_TOOL_DEFINITIONS[4],
        "security_selection": _get_security_selection_full_schema(),
        "buy_sell_backtest_service": _get_buy_sell_backtest_full_schema(),
        "rotation_trading_backtest_service": _get_rotation_trading_backtest_full_schema(),
        "fixed_investment_backtest_service": _get_fixed_investment_backtest_full_schema(),
        "smart_fixed_investment_backtest_service": _get_smart_fixed_investment_backtest_full_schema(),
    }


def get_simple_tools_for_agent() -> List[Dict]:
    """返回主Agent使用的简化工具列表"""
    return SIMPLE_TOOL_DEFINITIONS


def get_full_schema_by_name(tool_name: str) -> Dict:
    """根据工具名获取完整Schema"""
    all_schemas = get_full_tool_schemas()
    return all_schemas.get(tool_name)


# ============================================================================
# 判断工具是否为"复杂工具"（需要Worker抽参或LazyLoad的）
# ============================================================================

COMPLEX_TOOLS = {
    "security_selection",
    "buy_sell_backtest_service",
    "rotation_trading_backtest_service",
    "fixed_investment_backtest_service",
    "smart_fixed_investment_backtest_service",
}

def is_complex_tool(tool_name: str) -> bool:
    """判断是否为复杂工具"""
    return tool_name in COMPLEX_TOOLS


# ============================================================================
# 以下为完整Schema定义（从你提供的文件中提取）
# ============================================================================

def _get_security_selection_full_schema() -> Dict:
    return {
        "type": "function",
        "function": {
            "name": "security_selection",
            "description": "证券筛选工具：基于用户指定的选股时间点、股票池范围、选股条件组合，提取对应时间点的证券基本信息及因子值，通过核心因子排序筛选出TOPN证券标的。",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_point": {"type": "string", "description": "选股时间点，默认为库中最新交易日"},
                    "exchange": {"type": "string", "enum": ["纳斯达克+纽交所", "coinbase"], "description": "交易所"},
                    "product_type": {"type": "string", "enum": ["股票", "ETF", "股票+ETF", "比特币"], "description": "产品类型"},
                    "selection_conditions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "factor_name": {"type": "string"},
                                "condition": {"type": "string"},
                                "value": {"type": "number"}
                            }
                        },
                        "description": "选股条件组合"
                    },
                    "top_n": {"type": "integer", "default": 20, "maximum": 100, "description": "返回结果数量"}
                },
                "required": ["selection_conditions"]
            }
        }
    }


def _get_buy_sell_backtest_full_schema() -> Dict:
    """买卖交易模型回测完整Schema"""
    return {
        "type": "function",
        "function": {
            "name": "buy_sell_backtest_service",
            "description": "买卖交易模型回测工具，基于择时因子条件模拟买入和卖出交易逻辑，计算策略核心指标并输出可视化结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg0": {
                        "type": "object",
                        "properties": {
                            "backtestParams": {
                                "type": "object",
                                "properties": {
                                    "adjustmentType": {"type": "string", "enum": ["forward", "backward", "none"], "description": "复权方式，默认forward"},
                                    "benchmark": {"type": "string", "description": "基准代码：股票/ETF用GSPC，加密货币用BTC/USDT"},
                                    "commission": {"type": "number", "description": "交易佣金"},
                                    "commissionType": {"type": "string", "description": "佣金类型：FIXED或PERCENT"},
                                    "endDate": {"type": "string", "description": "回测结束日期，固定2025-07-01"},
                                    "initialCapital": {"type": "number", "description": "初始资金，默认100000"},
                                    "slippage": {"type": "number", "description": "滑点，默认0.0025"},
                                    "startDate": {"type": "string", "description": "回测开始日期，YYYY-MM-DD"}
                                },
                                "required": ["commissionType", "endDate", "startDate"]
                            },
                            "buyRules": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ruleConditionList": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "condition": {
                                                        "type": "object",
                                                        "properties": {
                                                            "conditionType": {"type": "string", "enum": ["CLOSE_OPEN", "CLOSE_CLOSE", "OPEN_OPEN", "OPEN_CLOSE"]},
                                                            "conditionValue": {"type": "string", "description": "条件值，百分比转小数"}
                                                        },
                                                        "required": ["conditionType", "conditionValue"]
                                                    },
                                                    "factor": {"type": "string", "description": "择时因子代码"}
                                                },
                                                "required": ["factor"]
                                            }
                                        },
                                        "tradePct": {"type": "number", "description": "交易比例"}
                                    }
                                },
                                "description": "买入条件列表"
                            },
                            "securities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "标的证券代码列表"
                            },
                            "sellRules": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ruleConditionList": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "condition": {
                                                        "type": "object",
                                                        "properties": {
                                                            "conditionType": {"type": "string", "enum": ["CLOSE_OPEN", "CLOSE_CLOSE", "OPEN_OPEN", "OPEN_CLOSE"]},
                                                            "conditionValue": {"type": "string"}
                                                        },
                                                        "required": ["conditionType", "conditionValue"]
                                                    },
                                                    "factor": {"type": "string"}
                                                },
                                                "required": ["factor"]
                                            }
                                        },
                                        "tradePct": {"type": "number"}
                                    },
                                    "required": ["tradePct"]
                                },
                                "description": "卖出条件列表"
                            },
                            "targetFinanceTypeList": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["ETF", "STOCK", "CRYPTO"]},
                                "description": "资产类型"
                            }
                        },
                        "required": ["securities", "targetFinanceTypeList", "buyRules", "sellRules"]
                    }
                }
            }
        }
    }


def _get_rotation_trading_backtest_full_schema() -> Dict:
    """轮动交易模型回测完整Schema"""
    return {
        "type": "function",
        "function": {
            "name": "rotation_trading_backtest_service",
            "description": "轮动交易模型回测工具，基于选股因子和择时因子实现动态轮动交易策略。",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg0": {
                        "type": "object",
                        "properties": {
                            "backtestParams": {
                                "type": "object",
                                "properties": {
                                    "adjustmentType": {"type": "string", "enum": ["forward", "backward", "none"]},
                                    "benchmark": {"type": "string"},
                                    "commission": {"type": "number"},
                                    "commissionType": {"type": "string"},
                                    "endDate": {"type": "string"},
                                    "initialCapital": {"type": "number"},
                                    "slippage": {"type": "number"},
                                    "startDate": {"type": "string"}
                                },
                                "required": ["commissionType", "endDate", "startDate"]
                            },
                            "industryList": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "stockSelection": {
                                "type": "object",
                                "properties": {
                                    "exchanges": {
                                        "type": "array",
                                        "items": {"type": "string", "description": "交易所代码（NMS, XBQ, ARC, NAS, NYS, PSE, MID, BTS, AS, ALL_CRYPTO）"}
                                    },
                                    "rankingFactor": {"type": "string", "description": "排序因子代码"},
                                    "rankingOrder": {"type": "string", "enum": ["ASC", "DESC"]},
                                    "securities": {"type": "array", "items": {"type": "string"}},
                                    "selectionConditions": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "condition": {
                                                    "type": "object",
                                                    "properties": {
                                                        "conditionType": {"type": "string", "enum": ["CLOSE_OPEN", "CLOSE_CLOSE", "OPEN_OPEN", "OPEN_CLOSE"]},
                                                        "conditionValue": {"type": "string"}
                                                    },
                                                    "required": ["conditionType", "conditionValue"]
                                                },
                                                "factor": {"type": "string"}
                                            },
                                            "required": ["factor"]
                                        },
                                        "description": "选股条件列表"
                                    }
                                },
                                "required": ["rankingFactor", "rankingOrder", "selectionConditions"]
                            },
                            "targetFinanceTypeList": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["ETF", "STOCK", "CRYPTO"]}
                            },
                            "timingRules": {
                                "type": "object",
                                "properties": {
                                    "buyConditions": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "condition": {
                                                    "type": "object",
                                                    "properties": {
                                                        "conditionType": {"type": "string", "enum": ["CLOSE_OPEN", "CLOSE_CLOSE", "OPEN_OPEN", "OPEN_CLOSE"]},
                                                        "conditionValue": {"type": "string"}
                                                    },
                                                    "required": ["conditionType", "conditionValue"]
                                                },
                                                "factor": {"type": "string", "description": "可用因子: RANK_AFTER_SORT, PRODUCT_POSITION_PCT, INDUSTRY_POSITION_PCT, HOLD_CAL_DAYS"}
                                            },
                                            "required": ["factor"]
                                        }
                                    },
                                    "positionLimits": {
                                        "type": "object",
                                        "properties": {
                                            "maxPositionWeight": {"type": "number", "description": "单只证券最大仓位，默认0.15"},
                                            "perSecurityWeight": {"type": "number", "description": "单只证券目标买入比例，默认0.02"},
                                            "rebalanceTargetWeight": {"type": "number", "description": "再平衡目标权重，默认0.1"}
                                        }
                                    },
                                    "sellConditions": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "condition": {
                                                    "type": "object",
                                                    "properties": {
                                                        "conditionType": {"type": "string", "enum": ["CLOSE_OPEN", "CLOSE_CLOSE", "OPEN_OPEN", "OPEN_CLOSE"]},
                                                        "conditionValue": {"type": "string"}
                                                    },
                                                    "required": ["conditionType", "conditionValue"]
                                                },
                                                "factor": {"type": "string"}
                                            },
                                            "required": ["factor"]
                                        }
                                    },
                                    "triggerSchedule": {
                                        "type": "object",
                                        "properties": {
                                            "every": {"type": "integer"},
                                            "frequency": {"type": "string", "enum": ["date_abs", "daily", "weekly", "monthly", "yearly"]},
                                            "periodDates": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "day": {"type": "string"},
                                                        "month": {"type": "string"}
                                                    }
                                                }
                                            }
                                        },
                                        "required": ["every", "frequency"]
                                    }
                                },
                                "required": ["sellConditions", "buyConditions"]
                            }
                        },
                        "required": ["stockSelection", "timingRules", "targetFinanceTypeList"]
                    }
                }
            }
        }
    }


def _get_fixed_investment_backtest_full_schema() -> Dict:
    """定投交易模型回测完整Schema"""
    return {
        "type": "function",
        "function": {
            "name": "fixed_investment_backtest_service",
            "description": "定投交易模型回测工具，模拟定期定额投资策略的历史表现。",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg0": {
                        "type": "object",
                        "properties": {
                            "backtestParams": {
                                "type": "object",
                                "properties": {
                                    "adjustmentType": {"type": "string", "enum": ["forward", "backward", "none"]},
                                    "benchmark": {"type": "string"},
                                    "commission": {"type": "number"},
                                    "commissionType": {"type": "string"},
                                    "endDate": {"type": "string"},
                                    "initialCapital": {"type": "number"},
                                    "slippage": {"type": "number"},
                                    "startDate": {"type": "string"}
                                },
                                "required": ["commissionType", "endDate", "startDate"]
                            },
                            "investmentAmount": {"type": "number", "description": "定投金额，默认500"},
                            "rebalanceConfig": {
                                "type": "object",
                                "properties": {
                                    "enabled": {"type": "boolean"},
                                    "threshold": {"type": "number"},
                                    "triggerSchedule": {
                                        "type": "object",
                                        "properties": {
                                            "every": {"type": "integer"},
                                            "frequency": {"type": "string", "enum": ["date_abs", "daily", "weekly", "monthly", "yearly"]},
                                            "periodDates": {"type": "array", "items": {"type": "object", "properties": {"day": {"type": "string"}, "month": {"type": "string"}}}}
                                        }
                                    }
                                }
                            },
                            "stockPoolScales": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "securityCode": {"type": "string"},
                                        "weight": {"type": "number"}
                                    },
                                    "required": ["securityCode", "weight"]
                                }
                            },
                            "targetFinanceTypeList": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["ETF", "STOCK", "CRYPTO"]}
                            },
                            "triggerSchedule": {
                                "type": "object",
                                "properties": {
                                    "every": {"type": "integer"},
                                    "frequency": {"type": "string", "enum": ["date_abs", "daily", "weekly", "monthly", "yearly"]},
                                    "periodDates": {"type": "array", "items": {"type": "object", "properties": {"day": {"type": "string"}, "month": {"type": "string"}}}}
                                },
                                "required": ["every", "frequency"]
                            }
                        },
                        "required": ["stockPoolScales", "targetFinanceTypeList", "investmentAmount", "triggerSchedule"]
                    }
                }
            }
        }
    }


def _get_smart_fixed_investment_backtest_full_schema() -> Dict:
    """智能定投交易模型回测完整Schema"""
    return {
        "type": "function",
        "function": {
            "name": "smart_fixed_investment_backtest_service",
            "description": "智能定投交易模型回测工具，根据择时因子动态调整定投金额。",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg0": {
                        "type": "object",
                        "properties": {
                            "backtestParams": {
                                "type": "object",
                                "properties": {
                                    "adjustmentType": {"type": "string", "enum": ["forward", "backward", "none"]},
                                    "benchmark": {"type": "string"},
                                    "commission": {"type": "number"},
                                    "commissionType": {"type": "string"},
                                    "endDate": {"type": "string"},
                                    "initialCapital": {"type": "number"},
                                    "slippage": {"type": "number"},
                                    "startDate": {"type": "string"}
                                },
                                "required": ["commissionType", "endDate", "startDate"]
                            },
                            "investmentAmount": {"type": "number"},
                            "ratingInvestConfig": {
                                "type": "object",
                                "properties": {
                                    "factor": {"type": "string", "description": "择时因子: rsi_14_crypto 或 ema_20_crypto"},
                                    "levels": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "range": {
                                                    "type": "object",
                                                    "properties": {
                                                        "conditionType": {"type": "string", "enum": ["CLOSE_OPEN", "CLOSE_CLOSE", "OPEN_OPEN", "OPEN_CLOSE"]},
                                                        "conditionValue": {"type": "string"}
                                                    },
                                                    "required": ["conditionType", "conditionValue"]
                                                },
                                                "scale": {"type": "number"}
                                            },
                                            "required": ["scale"]
                                        }
                                    }
                                },
                                "required": ["factor", "levels"]
                            },
                            "rebalanceConfig": {
                                "type": "object",
                                "properties": {
                                    "enabled": {"type": "boolean"},
                                    "threshold": {"type": "number"},
                                    "triggerSchedule": {
                                        "type": "object",
                                        "properties": {
                                            "every": {"type": "integer"},
                                            "frequency": {"type": "string", "enum": ["date_abs", "daily", "weekly", "monthly", "yearly"]},
                                            "periodDates": {"type": "array", "items": {"type": "object", "properties": {"day": {"type": "string"}, "month": {"type": "string"}}}}
                                        }
                                    }
                                }
                            },
                            "stockPoolScales": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "securityCode": {"type": "string"},
                                        "weight": {"type": "number"}
                                    },
                                    "required": ["securityCode", "weight"]
                                }
                            },
                            "targetFinanceTypeList": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["ETF", "STOCK", "CRYPTO"]}
                            },
                            "triggerSchedule": {
                                "type": "object",
                                "properties": {
                                    "every": {"type": "integer"},
                                    "frequency": {"type": "string", "enum": ["date_abs", "daily", "weekly", "monthly", "yearly"]},
                                    "periodDates": {"type": "array", "items": {"type": "object", "properties": {"day": {"type": "string"}, "month": {"type": "string"}}}}
                                },
                                "required": ["every", "frequency"]
                            }
                        },
                        "required": ["stockPoolScales"]
                    }
                }
            }
        }
    }
