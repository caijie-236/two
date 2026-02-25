"""
实验配置文件
"""
import os

# ============================================================================
# 模型配置（Anthropic Claude）
# ============================================================================
MODEL_CONFIG = {
    "main_agent_model": os.getenv("MAIN_AGENT_MODEL", "claude-sonnet-4-20250514"),
    "worker_model": os.getenv("WORKER_MODEL", "claude-sonnet-4-20250514"),
    "api_key": os.getenv("ANTHROPIC_API_KEY", "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"),
    "timeout": 300,  # API调用超时秒数（5分钟）
    "max_retries": 2,  # API调用失败自动重试次数
}

# ============================================================================
# 实验配置
# ============================================================================
EXPERIMENT_CONFIG = {
    "max_iterations": 15,          # 单次任务最大迭代轮数
    "max_error_retries": 3,        # 报错后最大重试次数
    "repeat_runs": 3,              # 每个用例重复运行次数（考虑模型随机性）
    "verbose": True,
}

# ============================================================================
# 评测维度权重
# ============================================================================
EVAL_WEIGHTS = {
    "param_accuracy": 0.30,
    "task_completion": 0.25,
    "error_recovery": 0.20,
    "token_efficiency": 0.15,
    "turn_efficiency": 0.10,
}
