"""
实验运行器（Experiment Runner）—— Anthropic版
"""
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import asdict

import anthropic

from config import MODEL_CONFIG, EXPERIMENT_CONFIG
from error_injector import ErrorInjector, InjectionScript, get_experiment_scenarios
from mock_executor import MockToolExecutor
from architecture_a import ArchitectureA
from architecture_b import ArchitectureB
from test_cases import TestCase, get_all_test_cases


class ExperimentRecord:
    """单次实验运行的完整记录"""
    
    def __init__(self, test_case_id: str, architecture: str, scenario: str, run_index: int):
        self.test_case_id = test_case_id
        self.architecture = architecture
        self.scenario = scenario
        self.run_index = run_index
        self.result: Optional[Dict] = None
        self.injection_log: List[Dict] = []
        self.executor_log: List[Dict] = []
        self.validation_summary: Dict[str, Any] = {}  # ← 新增
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "test_case_id": self.test_case_id,
            "architecture": self.architecture,
            "scenario": self.scenario,
            "run_index": self.run_index,
            "timestamp": self.timestamp,
            "metrics": self.result.get("metrics", {}) if self.result else {},
            "task_history": self.result.get("task_history", []) if self.result else [],
            "final_response_length": len(self.result.get("final_response", "")) if self.result else 0,
            "injection_log": self.injection_log,
            "executor_log": self.executor_log,
            "validation_summary": self.validation_summary,  # ← 新增
        }


class ExperimentRunner:
    """实验运行器"""
    
    def __init__(self, api_key: str = None, main_model: str = None, worker_model: str = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or MODEL_CONFIG["api_key"],
            timeout=MODEL_CONFIG.get("timeout", 300),
            max_retries=MODEL_CONFIG.get("max_retries", 2),
        )
        self.main_model = main_model or MODEL_CONFIG["main_agent_model"]
        self.worker_model = worker_model or MODEL_CONFIG["worker_model"]
        self.records: List[ExperimentRecord] = []
        self.all_scenarios = get_experiment_scenarios()
    
    def run_single(
        self, test_case: TestCase, architecture: str, scenario_name: str,
        run_index: int = 1, verbose: bool = True,
    ) -> ExperimentRecord:
        record = ExperimentRecord(test_case.id, architecture, scenario_name, run_index)
        
        injector = ErrorInjector()
        scripts = self.all_scenarios.get(scenario_name, [])
        injector.load_scripts(scripts)
        executor = MockToolExecutor(error_injector=injector)
        
        if architecture == "A":
            engine = ArchitectureA(
                client=self.client, main_model=self.main_model,
                worker_model=self.worker_model, executor=executor,
            )
        elif architecture == "B":
            engine = ArchitectureB(
                client=self.client, main_model=self.main_model, executor=executor,
            )
        else:
            raise ValueError(f"未知架构: {architecture}")
        
        if verbose:
            print(f"\n{'#'*80}")
            print(f"# 用例: {test_case.id} | 架构: {architecture} | 场景: {scenario_name} | 运行#{run_index}")
            print(f"# Query: {test_case.user_query}")
            print(f"{'#'*80}")
        
        try:
            result = engine.run(user_query=test_case.user_query, max_iterations=EXPERIMENT_CONFIG["max_iterations"], verbose=verbose)
            record.result = result
        except Exception as e:
            print(f"❌ 运行异常: {e}")
            import traceback; traceback.print_exc()
            record.result = {
                "final_response": f"[异常: {str(e)}]",
                "task_history": [], "metrics": {"error": str(e)}, "messages": [],
            }
        
        # 收集日志 + 校验汇总
        record.injection_log = injector.injection_log
        record.executor_log = executor.execution_log
        record.validation_summary = injector.get_validation_summary()  # ← 新增
        
        if verbose and record.validation_summary.get("total_validations", 0) > 0:
            vs = record.validation_summary
            print(f"\n  📋 参数校验: 通过={vs['validated_true']}, 失败={vs['validated_false']}, 强制放行={vs.get('forced_pass',0)}")
            for detail in vs["details"]:
                if detail.get("failed_fields"):
                    print(f"     ❌ 失败字段: {detail['failed_fields']}")
                elif detail.get("passed"):
                    checks = detail.get("checks", [])
                    print(f"     ✅ 全部通过 ({len(checks)} 项检查)")
        
        self.records.append(record)
        return record
    
    def run_comparison(
        self, test_cases: List[TestCase] = None, scenarios: List[str] = None,
        repeat: int = None, verbose: bool = True,
    ) -> List[ExperimentRecord]:
        if test_cases is None:
            test_cases = get_all_test_cases()
        if scenarios is None:
            scenarios = list(self.all_scenarios.keys())  # 所有注入场景
        if repeat is None:
            repeat = EXPERIMENT_CONFIG["repeat_runs"]
        
        total_max = len(test_cases) * len(scenarios) * 2 * repeat
        current = 0
        
        print(f"\n{'='*80}")
        print(f"🔬 开始对比实验 (Anthropic Claude)")
        print(f"   模型: {self.main_model}")
        print(f"   用例数: {len(test_cases)}, 场景数: {len(scenarios)}, 重复: {repeat}")
        print(f"{'='*80}")
        
        results = []
        for tc in test_cases:
            for scenario in scenarios:
                if not self._is_scenario_applicable(tc, scenario):
                    continue
                for arch in ["A", "B"]:
                    for run_idx in range(1, repeat + 1):
                        current += 1
                        print(f"\n[{current}] 运行中...")
                        record = self.run_single(tc, arch, scenario, run_idx, verbose)
                        results.append(record)
                        time.sleep(1)
        
        print(f"\n✅ 实验完成！共 {len(results)} 次运行")
        return results
    
    def _is_scenario_applicable(self, tc: TestCase, scenario: str) -> bool:
        """判断某个场景是否适用于某个测试用例（目标回测工具要匹配）"""
        scripts = self.all_scenarios.get(scenario, [])
        if not scripts:
            return False
        return any(s.tool_name == tc.target_backtest_tool for s in scripts)
    
    def save_results(self, filepath: str = "experiment_results.json"):
        data = {
            "experiment_time": datetime.now().isoformat(),
            "config": {"main_model": self.main_model, "worker_model": self.worker_model},
            "records": [r.to_dict() for r in self.records],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到 {filepath}")
    
    def generate_summary(self) -> Dict[str, Any]:
        summary = {"by_architecture": {}, "by_scenario": {}}
        
        for arch in ["A", "B"]:
            records = [r for r in self.records if r.architecture == arch]
            if not records:
                continue
            metrics_list = [r.result.get("metrics", {}) for r in records if r.result]
            summary["by_architecture"][arch] = {
                "total_runs": len(records),
                "avg_turns": _safe_avg([m.get("total_turns", 0) for m in metrics_list]),
                "avg_tool_calls": _safe_avg([m.get("tool_calls", 0) for m in metrics_list]),
                "avg_error_count": _safe_avg([m.get("error_count", 0) for m in metrics_list]),
                "avg_input_tokens": _safe_avg([m.get("input_tokens", 0) for m in metrics_list]),
                "avg_output_tokens": _safe_avg([m.get("output_tokens", 0) for m in metrics_list]),
                "recovery_attempts": sum(m.get("recovery_attempts", 0) for m in metrics_list),
                "recovery_successes": sum(m.get("recovery_successes", 0) for m in metrics_list),
                "skills_or_schema_loads": sum(m.get("skills_calls", 0) + m.get("schema_loads", 0) for m in metrics_list),
                # 校验维度（区分真假纠错）
                "validated_true": sum(r.validation_summary.get("validated_true", 0) for r in records if r.validation_summary),
                "validated_false": sum(r.validation_summary.get("validated_false", 0) for r in records if r.validation_summary),
            }
        
        scenarios = set(r.scenario for r in self.records)
        for scenario in scenarios:
            scenario_data = {}
            for arch in ["A", "B"]:
                records = [r for r in self.records if r.scenario == scenario and r.architecture == arch]
                if not records:
                    continue
                metrics_list = [r.result.get("metrics", {}) for r in records if r.result]
                scenario_data[arch] = {
                    "runs": len(records),
                    "avg_turns": _safe_avg([m.get("total_turns", 0) for m in metrics_list]),
                    "avg_tool_calls": _safe_avg([m.get("tool_calls", 0) for m in metrics_list]),
                    "total_errors": sum(m.get("error_count", 0) for m in metrics_list),
                    "total_recoveries": sum(m.get("recovery_successes", 0) for m in metrics_list),
                    "validated_true": sum(r.validation_summary.get("validated_true", 0) for r in records if r.validation_summary),
                    "validated_false": sum(r.validation_summary.get("validated_false", 0) for r in records if r.validation_summary),
                    "avg_tokens": _safe_avg([m.get("input_tokens", 0) + m.get("output_tokens", 0) for m in metrics_list]),
                }
            summary["by_scenario"][scenario] = scenario_data
        return summary
    
    def print_summary(self):
        summary = self.generate_summary()
        
        print(f"\n{'='*80}")
        print(f"📊 实验汇总报告 (Anthropic Claude)")
        print(f"{'='*80}")
        
        print(f"\n{'─'*65}")
        print(f"{'指标':<25} {'架构A(双模型+Skills)':<20} {'架构B(懒加载)':<20}")
        print(f"{'─'*65}")
        
        for key, name in [
            ("total_runs", "总运行次数"),
            ("avg_turns", "平均轮次"),
            ("avg_tool_calls", "平均工具调用"),
            ("avg_error_count", "平均报错次数"),
            ("recovery_attempts", "纠错尝试总数"),
            ("recovery_successes", "纠错成功总数(工具返回)"),
            ("validated_true", "✅ 真正纠错成功(校验)"),
            ("validated_false", "❌ 假性纠错(校验失败)"),
            ("skills_or_schema_loads", "Schema查看次数"),
            ("avg_input_tokens", "平均输入Token"),
            ("avg_output_tokens", "平均输出Token"),
        ]:
            a = summary["by_architecture"].get("A", {}).get(key, "N/A")
            b = summary["by_architecture"].get("B", {}).get(key, "N/A")
            a_s = f"{a:.1f}" if isinstance(a, float) else str(a)
            b_s = f"{b:.1f}" if isinstance(b, float) else str(b)
            print(f"{name:<25} {a_s:<20} {b_s:<20}")
        
        print(f"{'─'*65}")
        
        print(f"\n按场景细分:")
        for scenario, data in summary["by_scenario"].items():
            print(f"\n  📌 {scenario}")
            for arch, m in data.items():
                v_true = m.get('validated_true', 0)
                v_false = m.get('validated_false', 0)
                print(f"     架构{arch}: 轮次={m.get('avg_turns', 0):.1f}, "
                      f"工具调用={m.get('avg_tool_calls', 0):.1f}, "
                      f"报错={m.get('total_errors', 0)}, "
                      f"真纠错={v_true}, 假纠错={v_false}, "
                      f"Token={m.get('avg_tokens', 0):.0f}")


def _safe_avg(values: list) -> float:
    nums = [v for v in values if isinstance(v, (int, float))]
    return sum(nums) / len(nums) if nums else 0.0
