"""
架构B：懒加载 Lazy-Loading
"""
import json
import time
import copy
from typing import Dict, List, Any, Set
import anthropic

from tool_schemas import get_simple_tools_for_agent, get_full_schema_by_name, is_complex_tool
from anthropic_adapter import (
    convert_tools_batch,
    extract_tool_calls_from_response,
    extract_text_from_response,
    build_tool_results_message,
    get_token_usage,
)
from mock_executor import MockToolExecutor
from config import MODEL_CONFIG


SYSTEM_PROMPT = (
    "你是一个专业的金融策略Agent。根据用户需求，依次调用合适的工具完成任务。\n"
    "工具调用顺序建议：先映射（stock/factor/industry/exchange_mapping），"
    "再选因子（factor_selection），再筛选证券（security_selection），最后回测。\n"
    "对于复杂工具（如回测工具），第一次调用时系统会返回该工具的完整参数Schema。"
    "请仔细阅读Schema，然后第二次调用时按照Schema填写完整参数。\n"
    "如果工具执行返回了错误信息，请根据错误提示和已有的Schema修正参数后重新调用。\n"
    "当所有工具调用完成后，请直接用文字总结结果。"
)


class ArchitectureB:
    """架构B：懒加载（单模型，两阶段调用复杂工具）"""
    
    def __init__(self, client: anthropic.Anthropic, main_model: str, executor: MockToolExecutor):
        self.client = client
        self.main_model = main_model
        self.executor = executor
        self.agent_tools = convert_tools_batch(get_simple_tools_for_agent())
        
        self._schema_loaded: Set[str] = set()
        self.messages: List[Dict] = []
        self.task_history: List[Dict] = []
        self.metrics: Dict[str, Any] = self._init_metrics()
    
    def _init_metrics(self):
        return {
            "total_turns": 0, "tool_calls": 0, "error_count": 0,
            "schema_loads": 0, "recovery_attempts": 0, "recovery_successes": 0,
            "input_tokens": 0, "output_tokens": 0,
        }
    
    def run(self, user_query: str, max_iterations: int = 15, verbose: bool = True) -> Dict[str, Any]:
        if verbose:
            print(f"\n{'='*80}")
            print(f"🏗️  架构B（懒加载）开始执行")
            print(f"📝 用户目标: {user_query}")
            print(f"{'='*80}")
        
        self.messages = [{"role": "user", "content": user_query}]
        self.task_history = []
        self._schema_loaded = set()
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
                if verbose: print(f"  ❌ Agent调用失败: {e}")
                break
            
            usage = get_token_usage(response)
            self.metrics["input_tokens"] += usage["input_tokens"]
            self.metrics["output_tokens"] += usage["output_tokens"]
            
            tool_calls = extract_tool_calls_from_response(response)
            
            # ================================================================
            # 先暂存 assistant_content，不急着append
            # 因为注入时需要修改里面的 tool_use.input
            # ================================================================
            assistant_content = self._build_assistant_content(response)
            
            if not tool_calls:
                self.messages.append({"role": "assistant", "content": assistant_content})
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
                    print(f"\n  🔧 Agent调用: {tool_name}")
                    print(f"     模型原始入参: {json.dumps(tool_args, ensure_ascii=False, indent=2)}")
                
                # ---- 简单工具 ----
                if not is_complex_tool(tool_name):
                    result, meta = self.executor.execute(tool_name, tool_args)
                    if verbose:
                        print(f"     出参: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    self.task_history.append({
                        "step": len(self.task_history)+1, "tool": tool_name,
                        "params": tool_args, "result": result,
                    })
                    tool_results.append({"tool_use_id": tool_use_id, "content": json.dumps(result, ensure_ascii=False)})
                    continue
                
                # ---- 复杂工具 + 首次 → 返回Schema ----
                if tool_name not in self._schema_loaded:
                    self._schema_loaded.add(tool_name)
                    self.metrics["schema_loads"] += 1
                    full_schema = get_full_schema_by_name(tool_name)
                    schema_response = {
                        "status": "schema_loaded",
                        "message": f"这是 {tool_name} 的完整参数Schema。请仔细阅读后，按照Schema的required字段和参数结构重新调用此工具填写完整参数。",
                        "schema": full_schema,
                    }
                    content_str = json.dumps(schema_response, ensure_ascii=False)
                    if verbose:
                        print(f"     出参: 📖 返回完整Schema（{len(content_str)} 字符）")
                    tool_results.append({"tool_use_id": tool_use_id, "content": content_str})
                    continue
                
                # ---- 复杂工具 + 已加载Schema → 真正执行 ----
                if verbose:
                    print(f"     → 第二阶段: 执行 {tool_name}")
                
                result, meta = self.executor.execute(tool_name, tool_args)
                
                # ============================================================
                # 注入时：同步修改 messages 和 task_history
                # ============================================================
                params_for_history = meta["actual_params"]
                
                if meta["phase"] == "inject" and meta["blocked"]:
                    # 修改 assistant_content 里的 tool_use.input → 篡改后的参数
                    self._patch_assistant_content(assistant_content, tool_use_id, meta["actual_params"])
                    if verbose:
                        print(f"     ⚡ [inject] 报错层篡改后的参数:")
                        print(f"        {json.dumps(params_for_history, ensure_ascii=False, indent=2)}")
                        print(f"     📝 已同步修改messages中的入参（和报错一致）")
                
                if verbose:
                    print(f"     出参 [{meta['phase']}]: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                if not result.get("success", True):
                    self.metrics["error_count"] += 1
                    self.metrics["recovery_attempts"] += 1
                else:
                    prev_errors = [h for h in self.task_history if h["tool"] == tool_name and not h["result"].get("success", True)]
                    if prev_errors:
                        self.metrics["recovery_successes"] += 1
                        if verbose:
                            print(f"     🔄 纠错成功！")
                
                self.task_history.append({
                    "step": len(self.task_history)+1, "tool": tool_name,
                    "params": params_for_history,  # ← 注入时=篡改后，否则=原始
                    "result": result,
                })
                tool_results.append({"tool_use_id": tool_use_id, "content": json.dumps(result, ensure_ascii=False)})
            
            # 现在才把（可能已修改过的）assistant消息放入messages
            self.messages.append({"role": "assistant", "content": assistant_content})
            self.messages.append(build_tool_results_message(tool_results))
        
        self.metrics["elapsed_time"] = time.time() - start_time
        return {"final_response": "[超过最大迭代次数]", "task_history": self.task_history, "metrics": self.metrics, "messages": self.messages}
    
    @staticmethod
    def _build_assistant_content(response) -> List[Dict]:
        content_blocks = []
        for block in response.content:
            if block.type == "text":
                content_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content_blocks.append({
                    "type": "tool_use", "id": block.id,
                    "name": block.name, "input": copy.deepcopy(block.input),
                })
        return content_blocks
    
    @staticmethod
    def _patch_assistant_content(content_blocks: List[Dict], tool_use_id: str, tampered_params: dict):
        """修改 assistant_content 中指定 tool_use 的 input → 篡改后的参数"""
        for block in content_blocks:
            if block.get("type") == "tool_use" and block.get("id") == tool_use_id:
                block["input"] = copy.deepcopy(tampered_params)
                return
    
    def reset(self):
        self.messages, self.task_history = [], []
        self._schema_loaded = set()
        self.metrics = self._init_metrics()
