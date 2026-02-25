"""
错误注入系统 v3 —— 注入 + 真实校验

核心改动：
1. 去掉 "SUCCESS" 概念。序列只定义要注入的错误，用完后自动切到真实校验
2. 注入时不仅篡改参数，还返回篡改后的参数（供架构层同步修改messages）
3. 真实校验模式：根据模型实际提交的参数检查所有required字段，
   缺什么报什么，不用预设的报错文案
"""
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import copy


# ============================================================================
# 错误类型枚举
# ============================================================================

class ErrorType(Enum):
    MISSING_REQUIRED_FIELD = "missing_required_field"
    WRONG_TYPE = "wrong_type"
    WRONG_ENUM_VALUE = "wrong_enum_value"
    INVALID_FORMAT = "invalid_format"
    VALUE_OUT_OF_RANGE = "value_out_of_range"
    CUSTOM = "custom"


# ============================================================================
# 工具字段校验
# ============================================================================

_MISSING = object()


def _get_nested(d: dict, path: str) -> Any:
    keys = path.split(".")
    current = d
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return _MISSING
        current = current[key]
    return current


def _set_nested(d: dict, path: str, value: Any) -> dict:
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return d


def _delete_nested(d: dict, path: str) -> bool:
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            return False
        current = current[key]
    if keys[-1] in current:
        del current[keys[-1]]
        return True
    return False


def _preview(value: Any, max_len: int = 100) -> str:
    s = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return s[:max_len] + "..." if len(s) > max_len else s


# ============================================================================
# 必填字段定义
# ============================================================================

@dataclass
class RequiredField:
    field_path: str
    description: str
    expected_type: type = None
    allowed_values: list = None
    allow_empty: bool = False


TOOL_REQUIRED_FIELDS: Dict[str, List[RequiredField]] = {
    "rotation_trading_backtest_service": [
        RequiredField("arg0.stockSelection.rankingFactor", "排序因子（stockSelection.rankingFactor）", str),
        RequiredField("arg0.stockSelection.rankingOrder", "排序方向（stockSelection.rankingOrder）", str, ["ASC", "DESC"]),
        RequiredField("arg0.stockSelection.selectionConditions", "选股条件（stockSelection.selectionConditions）", list),
        RequiredField("arg0.timingRules.buyConditions", "买入条件（timingRules.buyConditions）", list),
        RequiredField("arg0.timingRules.sellConditions", "卖出条件（timingRules.sellConditions）", list),
        RequiredField("arg0.targetFinanceTypeList", "标的类型（targetFinanceTypeList）", list),
    ],
    "buy_sell_backtest_service": [
        RequiredField("arg0.securities", "证券列表（securities）", list),
        RequiredField("arg0.buyRules", "买入规则（buyRules）", list),
        RequiredField("arg0.sellRules", "卖出规则（sellRules）", list),
        RequiredField("arg0.targetFinanceTypeList", "标的类型（targetFinanceTypeList）", list),
    ],
    "fixed_investment_backtest_service": [
        RequiredField("arg0.securities", "证券列表（securities）", list),
        RequiredField("arg0.investmentAmount", "定投金额（investmentAmount）", (int, float)),
        RequiredField("arg0.triggerSchedule", "定投触发时间（triggerSchedule）", dict),
        RequiredField("arg0.targetFinanceTypeList", "标的类型（targetFinanceTypeList）", list),
    ],
    "smart_fixed_investment_backtest_service": [
        RequiredField("arg0.securities", "证券列表（securities）", list),
        RequiredField("arg0.baseAmount", "基础定投金额（baseAmount）", (int, float)),
        RequiredField("arg0.triggerSchedule", "定投触发时间（triggerSchedule）", dict),
        RequiredField("arg0.adjustmentRules", "智能调仓规则（adjustmentRules）", list),
        RequiredField("arg0.targetFinanceTypeList", "标的类型（targetFinanceTypeList）", list),
    ],
    "security_selection": [
        RequiredField("arg0.conditions", "筛选条件（conditions）", list),
    ],
}


def _check_one_field(params: dict, rf: RequiredField) -> Dict[str, Any]:
    """检查单个字段"""
    value = _get_nested(params, rf.field_path)
    
    if value is _MISSING:
        return {
            "valid": False, "field_path": rf.field_path,
            "error_message": f"Missing required field '{rf.description}'. Please include '{rf.field_path.split('.')[-1]}' in your request.",
        }
    if value is None:
        return {
            "valid": False, "field_path": rf.field_path,
            "error_message": f"Field '{rf.description}' cannot be null.",
        }
    if not rf.allow_empty and isinstance(value, (list, dict)) and len(value) == 0:
        return {
            "valid": False, "field_path": rf.field_path,
            "error_message": f"Field '{rf.description}' cannot be empty.",
        }
    if rf.expected_type and not isinstance(value, rf.expected_type):
        return {
            "valid": False, "field_path": rf.field_path,
            "error_message": f"Field '{rf.description}' has wrong type. Expected {rf.expected_type.__name__}, got {type(value).__name__}.",
        }
    if rf.allowed_values and value not in rf.allowed_values:
        return {
            "valid": False, "field_path": rf.field_path,
            "error_message": f"Invalid value for '{rf.description}'. Expected one of {rf.allowed_values}, got '{value}'.",
        }
    
    return {"valid": True, "field_path": rf.field_path, "error_message": None}


def validate_all_required_fields(tool_name: str, params: dict) -> Dict[str, Any]:
    """
    根据模型实际提交的参数，检查所有required字段。
    缺什么报什么，多出来的不管。
    """
    required_fields = TOOL_REQUIRED_FIELDS.get(tool_name, [])
    if not required_fields:
        return {"all_passed": True, "checks": [], "failed": [], "error_message": None}
    
    checks = []
    failed = []
    for rf in required_fields:
        result = _check_one_field(params, rf)
        checks.append(result)
        if not result["valid"]:
            failed.append(result)
    
    if not failed:
        return {"all_passed": True, "checks": checks, "failed": [], "error_message": None}
    
    lines = [f"Parameter validation failed with {len(failed)} error(s):"]
    for i, f in enumerate(failed, 1):
        lines.append(f"  {i}. {f['error_message']}")
    lines.append("")
    lines.append("Please fix ALL the above errors and call the tool again with complete parameters.")
    
    return {
        "all_passed": False,
        "checks": checks,
        "failed": failed,
        "error_message": "\n".join(lines),
    }


# ============================================================================
# 注入规则
# ============================================================================

@dataclass
class ErrorRule:
    error_type: ErrorType
    tool_name: str
    field_path: str
    error_message: str
    drop_field: bool = True
    mutate_fn: Optional[Callable] = None


ERROR_RULE_REGISTRY: Dict[str, ErrorRule] = {
    "rotation_missing_selectionConditions": ErrorRule(
        error_type=ErrorType.MISSING_REQUIRED_FIELD,
        tool_name="rotation_trading_backtest_service",
        field_path="arg0.stockSelection.selectionConditions",
        error_message="Missing required field 'stockSelection.selectionConditions'. selectionConditions should be an array of objects with 'factor' (string) and optional 'condition'.",
    ),
    "rotation_missing_rankingFactor": ErrorRule(
        error_type=ErrorType.MISSING_REQUIRED_FIELD,
        tool_name="rotation_trading_backtest_service",
        field_path="arg0.stockSelection.rankingFactor",
        error_message="Missing required field 'stockSelection.rankingFactor'. Please provide a valid factor code.",
    ),
    "rotation_missing_buyConditions": ErrorRule(
        error_type=ErrorType.MISSING_REQUIRED_FIELD,
        tool_name="rotation_trading_backtest_service",
        field_path="arg0.timingRules.buyConditions",
        error_message="Missing required field 'timingRules.buyConditions'. Please include buyConditions array.",
    ),
    "buysell_missing_securities": ErrorRule(
        error_type=ErrorType.MISSING_REQUIRED_FIELD,
        tool_name="buy_sell_backtest_service",
        field_path="arg0.securities",
        error_message="Missing required field 'securities'. Please provide a list of security tickers.",
    ),
    "buysell_missing_sellRules": ErrorRule(
        error_type=ErrorType.MISSING_REQUIRED_FIELD,
        tool_name="buy_sell_backtest_service",
        field_path="arg0.sellRules",
        error_message="Missing required field 'sellRules'. Please include sellRules array.",
    ),
    "fixed_missing_triggerSchedule": ErrorRule(
        error_type=ErrorType.MISSING_REQUIRED_FIELD,
        tool_name="fixed_investment_backtest_service",
        field_path="arg0.triggerSchedule",
        error_message="Missing required field 'triggerSchedule'. Please include triggerSchedule with 'every' and 'frequency'.",
    ),
    "rotation_wrong_commissionType": ErrorRule(
        error_type=ErrorType.WRONG_ENUM_VALUE,
        tool_name="rotation_trading_backtest_service",
        field_path="arg0.backtestParams.commissionType",
        error_message="Invalid value for 'backtestParams.commissionType'. Expected one of: 'FIXED', 'PERCENT'. Got: 'percent'.",
        drop_field=False,
        mutate_fn=lambda params: _set_nested(params, "arg0.backtestParams.commissionType", "percent"),
    ),
}


# ============================================================================
# 注入脚本 —— 不再有 "SUCCESS"
# ============================================================================

@dataclass
class InjectionScript:
    """
    注入剧本
    
    inject_rules: 要注入的错误列表（按顺序）
    - 第1次调用 → 注入 inject_rules[0]
    - 第2次调用 → 注入 inject_rules[1]（如果有）
    - 用完后 → 自动切到真实校验模式
    """
    tool_name: str
    inject_rules: List[str]  # ERROR_RULE_REGISTRY 的 key 列表
    
    def get_phase(self, call_count: int) -> Tuple[str, Optional[str]]:
        """
        返回 (phase, rule_key)
        - ("inject", "rotation_missing_selectionConditions")  → 注入模式
        - ("validate", None)                                  → 真实校验模式
        """
        if call_count < len(self.inject_rules):
            return ("inject", self.inject_rules[call_count])
        else:
            return ("validate", None)


# ============================================================================
# 错误注入器
# ============================================================================

class ErrorInjector:
    """
    错误注入器 v3
    
    两种模式：
    1. 注入模式（前N次调用）：篡改参数 + 返回报错 + 返回篡改后的参数供messages同步
    2. 真实校验模式（之后的调用）：根据模型实际参数校验所有required字段
    """
    
    def __init__(self, max_validation_retries: int = 3):
        self._scripts: Dict[str, InjectionScript] = {}
        self._call_counts: Dict[str, int] = {}
        self._injection_log: List[Dict] = []
        self._validation_retry_counts: Dict[str, int] = {}
        self._max_validation_retries = max_validation_retries
        self._enabled: bool = True
    
    def load_script(self, script: InjectionScript):
        self._scripts[script.tool_name] = script
        self._call_counts[script.tool_name] = 0
        self._validation_retry_counts[script.tool_name] = 0
    
    def load_scripts(self, scripts: List[InjectionScript]):
        for s in scripts:
            self.load_script(s)
    
    def clear(self):
        self._scripts.clear()
        self._call_counts.clear()
        self._injection_log.clear()
        self._validation_retry_counts.clear()
    
    def reset_counts(self):
        for key in self._call_counts:
            self._call_counts[key] = 0
        for key in self._validation_retry_counts:
            self._validation_retry_counts[key] = 0
        self._injection_log.clear()
    
    @property
    def injection_log(self) -> List[Dict]:
        return self._injection_log
    
    def get_validation_summary(self) -> Dict[str, Any]:
        injects = [l for l in self._injection_log if l["phase"] == "inject"]
        validates = [l for l in self._injection_log if l["phase"] == "validate"]
        return {
            "total_injections": len(injects),
            "total_validations": len(validates),
            "validated_true": sum(1 for v in validates if v.get("passed")),
            "validated_false": sum(1 for v in validates if not v.get("passed")),
            "forced_pass": sum(1 for v in validates if v.get("forced_pass")),
            "details": validates,
        }
    
    def intercept(self, tool_name: str, params: Dict) -> Dict[str, Any]:
        """
        拦截工具调用。
        
        Returns:
            {
                "should_block": bool,            # True=返回报错给模型, False=放行
                "error_response": dict|None,     # 报错内容
                "actual_params": dict,           # 模型"实际发出"的参数
                                                 #   注入模式 → 篡改后的参数
                                                 #   校验模式 → 原始参数（不改）
                "phase": "inject"|"validate"|"passthrough",
                "detail": dict,                  # 日志详情
            }
        """
        passthrough = {
            "should_block": False, "error_response": None,
            "actual_params": params, "phase": "passthrough", "detail": {},
        }
        
        if not self._enabled:
            return passthrough
        
        script = self._scripts.get(tool_name)
        if not script:
            return passthrough
        
        call_count = self._call_counts.get(tool_name, 0)
        self._call_counts[tool_name] = call_count + 1
        
        phase, rule_key = script.get_phase(call_count)
        
        if phase == "inject":
            return self._do_inject(tool_name, params, call_count, rule_key)
        else:
            return self._do_validate(tool_name, params, call_count)
    
    # ----------------------------------------------------------------
    # 注入模式
    # ----------------------------------------------------------------
    def _do_inject(self, tool_name: str, params: dict,
                   call_count: int, rule_key: str) -> Dict:
        rule = ERROR_RULE_REGISTRY.get(rule_key)
        if not rule:
            return {
                "should_block": False, "error_response": None,
                "actual_params": params, "phase": "inject", "detail": {"error": f"rule not found: {rule_key}"},
            }
        
        # 篡改参数
        tampered = copy.deepcopy(params)
        if rule.drop_field:
            _delete_nested(tampered, rule.field_path)
        if rule.mutate_fn:
            tampered = rule.mutate_fn(tampered)
        
        error_response = {
            "success": False,
            "error_code": 400,
            "message": rule.error_message,
        }
        
        log_entry = {
            "tool_name": tool_name,
            "call_number": call_count + 1,
            "phase": "inject",
            "rule_key": rule_key,
            "field_path": rule.field_path,
            "error_message": rule.error_message,
        }
        self._injection_log.append(log_entry)
        
        return {
            "should_block": True,
            "error_response": error_response,
            "actual_params": tampered,    # ← 架构层用这个同步messages
            "phase": "inject",
            "detail": log_entry,
        }
    
    # ----------------------------------------------------------------
    # 真实校验模式
    # ----------------------------------------------------------------
    def _do_validate(self, tool_name: str, params: dict, call_count: int) -> Dict:
        retry_count = self._validation_retry_counts.get(tool_name, 0)
        
        # 超过重试上限 → 强制放行
        if retry_count >= self._max_validation_retries:
            log_entry = {
                "tool_name": tool_name,
                "call_number": call_count + 1,
                "phase": "validate",
                "passed": False,
                "forced_pass": True,
                "reason": f"exceeded max retries ({self._max_validation_retries}), forced pass",
                "failed_fields": [],
            }
            self._injection_log.append(log_entry)
            return {
                "should_block": False, "error_response": None,
                "actual_params": params, "phase": "validate", "detail": log_entry,
            }
        
        # 真实校验
        validation = validate_all_required_fields(tool_name, params)
        
        if validation["all_passed"]:
            log_entry = {
                "tool_name": tool_name,
                "call_number": call_count + 1,
                "phase": "validate",
                "passed": True,
                "forced_pass": False,
                "failed_fields": [],
                "checks": [{"field": c["field_path"], "valid": c["valid"]} for c in validation["checks"]],
            }
            self._injection_log.append(log_entry)
            return {
                "should_block": False, "error_response": None,
                "actual_params": params, "phase": "validate", "detail": log_entry,
            }
        
        # 有问题 → 返回真实报错
        self._validation_retry_counts[tool_name] = retry_count + 1
        
        error_response = {
            "success": False,
            "error_code": 400,
            "message": validation["error_message"],
        }
        
        log_entry = {
            "tool_name": tool_name,
            "call_number": call_count + 1,
            "phase": "validate",
            "passed": False,
            "forced_pass": False,
            "failed_fields": [f["field_path"] for f in validation["failed"]],
            "error_message": validation["error_message"],
            "checks": [{"field": c["field_path"], "valid": c["valid"]} for c in validation["checks"]],
        }
        self._injection_log.append(log_entry)
        
        return {
            "should_block": True,
            "error_response": error_response,
            "actual_params": params,   # 校验模式不篡改参数
            "phase": "validate",
            "detail": log_entry,
        }


# ============================================================================
# 实验场景 —— 不再有 "SUCCESS"
# ============================================================================

def get_experiment_scenarios() -> Dict[str, List[InjectionScript]]:
    """
    每种回测工具一个场景：第1次注入缺失一个关键字段，之后真实校验。
    """
    return {
        # 轮动回测：缺 selectionConditions
        "rotation_missing_selection": [
            InjectionScript(
                tool_name="rotation_trading_backtest_service",
                inject_rules=["rotation_missing_selectionConditions"],
            )
        ],
        
        # 买卖回测：缺 securities
        "buysell_missing_securities": [
            InjectionScript(
                tool_name="buy_sell_backtest_service",
                inject_rules=["buysell_missing_securities"],
            )
        ],
        
        # 定投回测：缺 triggerSchedule
        "fixed_missing_trigger": [
            InjectionScript(
                tool_name="fixed_investment_backtest_service",
                inject_rules=["fixed_missing_triggerSchedule"],
            )
        ],
    }
