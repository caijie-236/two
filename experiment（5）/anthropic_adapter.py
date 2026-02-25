"""
Anthropic API 适配层

处理 OpenAI 格式 → Anthropic 格式的转换，包括：
1. 工具Schema格式转换
2. 消息格式差异
3. tool_calls / tool_result 格式差异

这样 tool_schemas.py 不需要改，只在调用层做一次转换。
"""
from typing import Dict, List, Any, Optional
import json


def convert_tool_schema_to_anthropic(openai_tool: Dict) -> Dict:
    """
    将 OpenAI 格式的工具定义转为 Anthropic 格式
    
    OpenAI 格式:
    {
        "type": "function",
        "function": {
            "name": "xxx",
            "description": "xxx",
            "parameters": {...}
        }
    }
    
    Anthropic 格式:
    {
        "name": "xxx",
        "description": "xxx",
        "input_schema": {...}
    }
    """
    func = openai_tool.get("function", openai_tool)
    return {
        "name": func["name"],
        "description": func.get("description", ""),
        "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
    }


def convert_tools_batch(openai_tools: List[Dict]) -> List[Dict]:
    """批量转换工具列表"""
    return [convert_tool_schema_to_anthropic(t) for t in openai_tools]


def extract_tool_calls_from_response(response) -> List[Dict]:
    """
    从 Anthropic response 中提取 tool_use blocks
    
    Anthropic 的 response.content 是一个 list，可能包含：
    - {"type": "text", "text": "..."}
    - {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
    
    返回格式统一为:
    [{"id": "toolu_xxx", "name": "tool_name", "arguments": {...}, "raw_arguments": "{}"}]
    """
    tool_calls = []
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "arguments": block.input,                          # 已经是dict
                "raw_arguments": json.dumps(block.input, ensure_ascii=False),  # 转成string备用
            })
    return tool_calls


def extract_text_from_response(response) -> str:
    """从 Anthropic response 中提取文本内容"""
    texts = []
    for block in response.content:
        if block.type == "text":
            texts.append(block.text)
    return "\n".join(texts)


def build_tool_result_message(tool_use_id: str, content: str) -> Dict:
    """
    构建 Anthropic 格式的工具结果消息
    
    Anthropic 要求工具结果以 user 角色返回：
    {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_xxx", "content": "..."}
        ]
    }
    """
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
            }
        ]
    }


def build_tool_results_message(results: List[Dict]) -> Dict:
    """
    构建包含多个工具结果的消息（同一轮多个tool_use时）
    
    results: [{"tool_use_id": "...", "content": "..."}, ...]
    """
    return {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": r["tool_use_id"], "content": r["content"]}
            for r in results
        ]
    }


def build_assistant_message_from_response(response) -> Dict:
    """
    把 Anthropic response 转为可放入 messages 的 assistant 消息
    
    需要保留原始 content blocks（包括 text 和 tool_use），
    这样下一轮 tool_result 才能对应上 tool_use_id
    """
    content_blocks = []
    for block in response.content:
        if block.type == "text":
            content_blocks.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            content_blocks.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    
    return {"role": "assistant", "content": content_blocks}


def get_token_usage(response) -> Dict[str, int]:
    """提取token使用量"""
    usage = getattr(response, 'usage', None)
    if usage:
        return {
            "input_tokens": getattr(usage, 'input_tokens', 0),
            "output_tokens": getattr(usage, 'output_tokens', 0),
        }
    return {"input_tokens": 0, "output_tokens": 0}
