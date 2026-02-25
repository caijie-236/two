"""
架构A：双模型 + Skills纠错
"""
import json
import time
from typing import Dict, List, Any
import anthropic

from tool_schemas import get_simple_tools_for_agent, get_full_schema_by_name, is_complex_tool
from anthropic_adapter import (
    convert_tools_batch, convert_tool_schema_to_anthropic,
    extract_tool_calls_from_response, extract_text_from_response,
    build_tool_results_message, build_assistant_message_from_response, get_token_usage,
)
from mock_executor import MockToolExecutor
from config import MODEL_CONFIG


SKILLS_TOOL_DEFINITION = {
    "name": "get_tool_schema",
    "description": (
        "获取指定工具的完整JSON Schema定义。"
        "当调用某个工具后返回了参数错误（如缺少必填字段、类型不匹配等），"
        "请调用此工具查看该工具的完整参数Schema，"
        "然后根据Schema和错误信息修正参数后重新调用原工具。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {"tool_name": {"type": "string", "description": "需要查看Schema的工具名称"}},
        "required": ["tool_name"]
    }
}

SYSTEM_PROMPT = (
    "你是一个专业的金融策略Agent。根据用户需求，依次调用合适的工具完成任务。\n"
    "工具调用顺序建议：先映射（stock/factor/industry/exchange_mapping），"
    "再选因子（factor_selection），再筛选证券（security_selection），最后回测。\n"
    "如果工具返回了错误信息（如缺少必填字段），请先调用 get_tool_schema 查看该工具的完整参数定义，"
    "然后根据错误信息和Schema修正参数后重新调用该工具。\n"
    "当所有工具调用完成后，请直接用文字总结结果。"
)


class WorkerModel:
    def __init__(self, client: anthropic.Anthropic, model_name: str):
        self.client = client
        self.model_name = model_name
    
    def extract_params(self, tool_name: str, user_goal: str, task_history: List[Dict]) -> Dict[str, Any]:
        full_schema = get_full_schema_by_name(tool_name)
        if not full_schema:
            return {"error": f"未找到工具 {tool_name} 的完整Schema"}
        
        anthropic_tool = convert_tool_schema_to_anthropic(full_schema)
        history_text = "无" if not task_history else json.dumps(task_history, ensure_ascii=False, indent=2)
        
        user_message = (
            f"用户目标：{user_goal}\n\n"
            f"历史执行结果：\n{history_text}\n\n"
            f"请根据以上信息，调用 {tool_name} 工具并填写完整参数。"
        )
        
        try:
            response = self.client.messages.create(
                model=self.model_name, max_tokens=4096,
                system="你是参数提取专家。根据用户需求和上下文，准确填写工具的所有必填参数。",
                messages=[{"role": "user", "content": user_message}],
                tools=[anthropic_tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
            from anthropic_adapter import extract_tool_calls_from_response as extract_tc
            tool_calls = extract_tc(response)
            if tool_calls:
                tc = tool_calls[0]
                return {"arguments": tc["arguments"], "usage": get_token_usage(response)}
            return {"error": "Worker模型未生成tool_use"}
        except Exception as e:
            return {"error": f"Worker调用失败: {str(e)}"}


class ArchitectureA:
    def __init__(self, client: anthropic.Anthropic, main_model: str, worker_model: str, executor: MockToolExecutor):
        self.client = client
        self.main_model = main_model
        self.worker = WorkerModel(client, worker_model)
        self.executor = executor
        self.agent_tools = convert_tools_batch(get_simple_tools_for_agent()) + [SKILLS_TOOL_DEFINITION]
        self.messages: List[Dict] = []
        self.task_history: List[Dict] = []
        self.metrics: Dict[str, Any] = self._init_metrics()
    
    def _init_metrics(self):
        return {
            "total_turns": 0, "tool_calls": 0, "error_count": 0,
            "skills_calls": 0, "recovery_attempts": 0, "recovery_successes": 0,
            "input_tokens": 0, "output_tokens": 0,
        }
    
    def run(self, user_query: str, max_iterations: int = 15, verbose: bool = True) -> Dict[str, Any]:
        if verbose:
            print(f"\n{'='*80}")
            print(f"🏗️  架构A（双模型 + Skills）开始执行")
            print(f"📝 用户目标: {user_query}")
            print(f"{'='*80}")
        
        self.messages = [{"role": "user", "content": user_query}]
        self.task_history = []
        self.metrics = self._init_metrics()
        start_time = time.time()
        
        for iteration in range(max_iterations):
            self.metrics["total_turns"] += 1
            if verbose:
                print(f"\n{'─'*70}")
                print(f"  第 {iteration + 1} 轮")
                print(f"{'─'*70}")
            
            try:
                response = self.client.messages.create(
                    model=self.main_model, max_tokens=4096,
                    system=SYSTEM_PROMPT, messages=self.messages,
                    tools=self.agent_tools, tool_choice={"type": "auto"},
                )
            except Exception as e:
                if verbose: print(f"  ❌ 主Agent调用失败: {e}")
                break
            
            usage = get_token_usage(response)
            self.metrics["input_tokens"] += usage["input_tokens"]
            self.metrics["output_tokens"] += usage["output_tokens"]
            
            tool_calls = extract_tool_calls_from_response(response)
            self.messages.append(build_assistant_message_from_response(response))
            
            if not tool_calls:
                final_text = extract_text_from_response(response)
                if verbose:
                    print(f"  📤 模型最终回复:")
                    print(f"     {final_text}")
                    print(f"  ✅ 任务完成")
                self.metrics["elapsed_time"] = time.time() - start_time
                return {"final_response": final_text, "task_history": self.task_history, "metrics": self.metrics, "messages": self.messages}
            
            tool_results = []
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_use_id = tc["id"]
                tool_args = tc["arguments"]
                self.metrics["tool_calls"] += 1
                
                if verbose:
                    print(f"\n  🔧 主Agent调用: {tool_name}")
                    print(f"     入参: {json.dumps(tool_args, ensure_ascii=False, indent=2)}")
                
                # ---- Skills ----
                if tool_name == "get_tool_schema":
                    self.metrics["skills_calls"] += 1
                    target = tool_args.get("tool_name", "")
                    schema = get_full_schema_by_name(target)
                    content = json.dumps(schema, ensure_ascii=False, indent=2) if schema else f"未找到 {target}"
                    if verbose:
                        print(f"     出参: 📖 返回 {target} 的完整Schema ({len(content)} 字符)")
                    tool_results.append({"tool_use_id": tool_use_id, "content": content})
                    continue
                
                # ---- 简单工具 ----
                if not is_complex_tool(tool_name):
                    result, meta = self.executor.execute(tool_name, tool_args)
                    if verbose:
                        print(f"     出参: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    self.task_history.append({"step": len(self.task_history)+1, "tool": tool_name, "params": tool_args, "result": result})
                    tool_results.append({"tool_use_id": tool_use_id, "content": json.dumps(result, ensure_ascii=False)})
                    continue
                
                # ---- 复杂工具 → Worker ----
                if verbose: print(f"     → 复杂工具，交给Worker抽参...")
                worker_result = self.worker.extract_params(tool_name, user_query, self.task_history)
                
                if "usage" in worker_result:
                    self.metrics["input_tokens"] += worker_result["usage"].get("input_tokens", 0)
                    self.metrics["output_tokens"] += worker_result["usage"].get("output_tokens", 0)
                
                if "error" in worker_result:
                    if verbose: print(f"     ❌ Worker失败: {worker_result['error']}")
                    err = {"success": False, "message": worker_result["error"]}
                    tool_results.append({"tool_use_id": tool_use_id, "content": json.dumps(err, ensure_ascii=False)})
                    continue
                
                worker_params = worker_result["arguments"]
                if verbose:
                    print(f"     Worker填参: {json.dumps(worker_params, ensure_ascii=False, indent=2)}")
                
                result, meta = self.executor.execute(tool_name, worker_params)
                
                # ================================================================
                # 关键：task_history 里记录的参数 = actual_params（篡改后的）
                # 这样 Worker 下次看到的历史和报错信息一致
                # ================================================================
                params_for_history = meta["actual_params"]
                
                if verbose:
                    if meta["phase"] == "inject" and meta["blocked"]:
                        print(f"     ⚡ [inject] 报错层篡改后的参数:")
                        print(f"        {json.dumps(params_for_history, ensure_ascii=False, indent=2)}")
                    print(f"     出参 [{meta['phase']}]: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                if not result.get("success", True):
                    self.metrics["error_count"] += 1
                    self.metrics["recovery_attempts"] += 1
                else:
                    prev_errors = [h for h in self.task_history if h["tool"] == tool_name and not h["result"].get("success", True)]
                    if prev_errors:
                        self.metrics["recovery_successes"] += 1
                
                self.task_history.append({
                    "step": len(self.task_history)+1,
                    "tool": tool_name,
                    "params": params_for_history,  # ← 篡改后的参数，和报错一致
                    "result": result,
                })
                tool_results.append({"tool_use_id": tool_use_id, "content": json.dumps(result, ensure_ascii=False)})
            
            self.messages.append(build_tool_results_message(tool_results))
        
        self.metrics["elapsed_time"] = time.time() - start_time
        return {"final_response": "[超过最大迭代次数]", "task_history": self.task_history, "metrics": self.metrics, "messages": self.messages}
    
    def reset(self):
        self.messages, self.task_history, self.metrics = [], [], self._init_metrics()
