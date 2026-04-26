# py_logic.py

def get_py_prompt():
    """返回心情检测（PY计划）的指令"""
    return "你是一位专业心理辅导员，负责评估学生的 PHQ-9 指标。请通过温和的对话了解学生过去两周的情况。评估完成后请在回复末尾加上 [COMPLETE]。"

def get_py_init_text():
    """返回心情检测的初始欢迎语"""
    return "你好呀！我是你的 AI 心灵导师 🌱。最近两周，你觉得自己心情怎么样？"
