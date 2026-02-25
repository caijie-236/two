"""
实验入口

使用：
  python main.py --mode inject_test          # 单元测试（不需要API Key）
  python main.py --mode quick                # 每种回测工具各跑1个用例 × 2种架构
  python main.py --mode full                 # 全部用例 × 全部架构 × 重复3次
  python main.py --mode single --case rotation_001 --arch B --scenario rotation_missing_selection
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from error_injector import (
    ErrorInjector, InjectionScript, get_experiment_scenarios,
    validate_all_required_fields,
)
from mock_executor import MockToolExecutor
from test_cases import get_all_test_cases, TEST_CASES
from config import MODEL_CONFIG, EXPERIMENT_CONFIG


# ============================================================================
# 模式1：inject_test（不需要API Key，本地验证报错层逻辑）
# ============================================================================

def mode_inject_test():
    """
    验证报错层核心逻辑：
    1. 第1次调用回测工具 → 篡改入参 → 返回报错 → actual_params可用于同步messages
    2. 第2次调用 → 真实校验模型实际参数 → 缺什么报什么
    """
    print("="*80)
    print("🧪 报错层逻辑验证")
    print("="*80)
    
    injector = ErrorInjector()
    injector.load_script(InjectionScript(
        tool_name="rotation_trading_backtest_service",
        inject_rules=["rotation_missing_selectionConditions"],
    ))
    executor = MockToolExecutor(error_injector=injector)
    
    # 模拟模型生成的完整参数
    complete_params = {
        "arg0": {
            "stockSelection": {
                "rankingFactor": "pe_ttm",
                "rankingOrder": "ASC",
                "selectionConditions": [{"factor": "pe_ttm"}],
            },
            "timingRules": {
                "buyConditions": [{"factor": "RANK_AFTER_SORT"}],
                "sellConditions": [{"factor": "HOLD_CAL_DAYS"}],
            },
            "targetFinanceTypeList": ["STOCK"],
        }
    }
    
    # === 第1次调用：注入 ===
    print(f"\n{'─'*70}")
    print("第1次调用回测工具（注入模式）")
    print(f"{'─'*70}")
    
    print(f"\n  模型原始入参:")
    print(f"  {json.dumps(complete_params, ensure_ascii=False, indent=2)}")
    
    r1, m1 = executor.execute("rotation_trading_backtest_service", complete_params)
    
    print(f"\n  报错层篡改后的参数（用于同步到messages和task_history）:")
    print(f"  {json.dumps(m1['actual_params'], ensure_ascii=False, indent=2)}")
    
    print(f"\n  返回给模型的报错:")
    print(f"  {json.dumps(r1, ensure_ascii=False, indent=2)}")
    
    assert r1["success"] == False
    assert m1["phase"] == "inject"
    assert "selectionConditions" not in json.dumps(m1["actual_params"])
    print(f"\n  ✅ 注入成功：selectionConditions已从actual_params中删除，messages和task_history将同步此参数")
    
    # === 第2次调用：真实校验（参数正确）===
    print(f"\n{'─'*70}")
    print("第2次调用回测工具（真实校验模式 - 参数正确）")
    print(f"{'─'*70}")
    
    print(f"\n  模型提交的入参:")
    print(f"  {json.dumps(complete_params, ensure_ascii=False, indent=2)}")
    
    r2, m2 = executor.execute("rotation_trading_backtest_service", complete_params)
    
    print(f"\n  返回给模型的结果:")
    print(f"  {json.dumps(r2, ensure_ascii=False, indent=2)}")
    
    assert r2["success"] == True
    assert m2["phase"] == "validate"
    print(f"\n  ✅ 真实校验通过：所有必填字段都存在，放行")
    
    # === 第2次调用（另一种情况）：真实校验（参数有缺失）===
    print(f"\n{'─'*70}")
    print("第2次调用回测工具（真实校验模式 - 参数有缺失）")
    print(f"{'─'*70}")
    
    injector2 = ErrorInjector()
    injector2.load_script(InjectionScript(
        tool_name="rotation_trading_backtest_service",
        inject_rules=["rotation_missing_selectionConditions"],
    ))
    executor2 = MockToolExecutor(error_injector=injector2)
    
    # 第1次注入
    executor2.execute("rotation_trading_backtest_service", complete_params)
    
    # 第2次：模型修好了selectionConditions但漏了buyConditions
    bad_params = {
        "arg0": {
            "stockSelection": {
                "rankingFactor": "pe_ttm",
                "rankingOrder": "ASC",
                "selectionConditions": [{"factor": "pe_ttm"}],
            },
            "timingRules": {
                "sellConditions": [{"factor": "HOLD_CAL_DAYS"}],
                # buyConditions 缺失
            },
            "targetFinanceTypeList": ["STOCK"],
        }
    }
    
    print(f"\n  模型提交的入参（buyConditions缺失）:")
    print(f"  {json.dumps(bad_params, ensure_ascii=False, indent=2)}")
    
    r2b, m2b = executor2.execute("rotation_trading_backtest_service", bad_params)
    
    print(f"\n  返回给模型的报错:")
    print(f"  {json.dumps(r2b, ensure_ascii=False, indent=2)}")
    
    assert r2b["success"] == False
    assert "buyConditions" in r2b["message"]
    print(f"\n  ✅ 真实校验拦截：动态发现buyConditions缺失并报错")
    
    # === 汇总 ===
    print(f"\n{'='*70}")
    print("🎉 验证通过！")
    print(f"{'='*70}")
    print("报错层行为：")
    print("  第1次调用回测工具 → 注入模式：")
    print("    - 篡改入参（删掉指定字段）")
    print("    - 返回actual_params → 架构层用这个同步messages和task_history")
    print("    - 返回报错给模型")
    print("  第2次及以后调用 → 真实校验模式：")
    print("    - 不篡改，直接检查模型实际参数的所有必填字段")
    print("    - 缺什么报什么，全部ok才放行")


# ============================================================================
# 模式2：quick（每种回测工具各1个用例 × 2种架构）
# ============================================================================

def mode_quick(verbose=True):
    """
    快速实验：每种回测工具选1个代表性用例，跑两种架构。
    轮动回测用 rotation_001 + rotation_missing_selection
    买卖回测用 buysell_001 + buysell_missing_securities
    定投回测用 fixed_001 + fixed_missing_trigger
    """
    from runner import ExperimentRunner
    runner = ExperimentRunner()
    
    # 每种回测工具一个用例 + 对应的注入场景
    experiments = [
        ("rotation_001", "rotation_missing_selection"),
        ("buysell_001", "buysell_missing_securities"),
        ("fixed_001", "fixed_missing_trigger"),
    ]
    
    all_cases = {tc.id: tc for tc in get_all_test_cases()}
    
    for case_id, scenario in experiments:
        tc = all_cases.get(case_id)
        if not tc:
            print(f"⚠️ 用例 {case_id} 不存在，跳过")
            continue
        for arch in ["A", "B"]:
            runner.run_single(tc, arch, scenario, run_index=1, verbose=verbose)
    
    runner.print_summary()
    runner.save_results()


# ============================================================================
# 模式3：full（全部用例 × 全部适用场景 × 2种架构 × 重复N次）
# ============================================================================

def mode_full(verbose=True):
    from runner import ExperimentRunner
    runner = ExperimentRunner()
    runner.run_comparison(verbose=verbose)
    runner.print_summary()
    runner.save_results()


# ============================================================================
# 模式4：single（指定单个用例）
# ============================================================================

def mode_single(case_id: str, arch: str, scenario: str, verbose=True):
    from runner import ExperimentRunner
    
    all_cases = get_all_test_cases()
    tc = next((c for c in all_cases if c.id == case_id), None)
    if not tc:
        print(f"❌ 未找到用例: {case_id}")
        print(f"可用用例: {[c.id for c in all_cases]}")
        return
    
    runner = ExperimentRunner()
    runner.run_single(tc, arch, scenario, run_index=1, verbose=verbose)
    runner.print_summary()
    runner.save_results()


# ============================================================================
# 选项查看
# ============================================================================

def print_available_options():
    print("\n📋 可用测试用例:")
    for tc in get_all_test_cases():
        print(f"  {tc.id} [{tc.target_backtest_tool}]: {tc.user_query}")
    
    print("\n📋 可用实验场景（每种回测工具一个）:")
    for name, scripts in get_experiment_scenarios().items():
        rules = [s.inject_rules for s in scripts]
        tool = scripts[0].tool_name if scripts else "?"
        print(f"  {name}: 工具={tool}, 注入={rules}")
    
    print("\n📋 可用架构: A（双模型+Skills）, B（懒加载）")
    
    print("\n📋 推荐的 quick 模式实验组合：")
    print("  rotation_001 + rotation_missing_selection  → 轮动回测缺selectionConditions")
    print("  buysell_001  + buysell_missing_securities   → 买卖回测缺securities")
    print("  fixed_001    + fixed_missing_trigger         → 定投回测缺triggerSchedule")


# ============================================================================
# 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Agent工具调用实验")
    parser.add_argument("--mode", choices=["inject_test", "quick", "full", "single", "options"],
                        default="quick", help="运行模式")
    parser.add_argument("--case", default="rotation_001", help="测试用例ID")
    parser.add_argument("--arch", default="B", help="架构: A or B")
    parser.add_argument("--scenario", default="rotation_missing_selection", help="实验场景")
    parser.add_argument("--verbose", action="store_true", default=True)
    parser.add_argument("--quiet", action="store_true", default=False)
    
    args = parser.parse_args()
    verbose = not args.quiet
    
    if args.mode == "inject_test":
        mode_inject_test()
    elif args.mode == "quick":
        mode_quick(verbose=verbose)
    elif args.mode == "full":
        mode_full(verbose=verbose)
    elif args.mode == "single":
        mode_single(args.case, args.arch, args.scenario, verbose=verbose)
    elif args.mode == "options":
        print_available_options()


if __name__ == "__main__":
    main()
