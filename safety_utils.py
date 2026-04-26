# safety_utils.py

# 定义预警词库（可以根据学校情况补充，如：死、杀、跳楼、割脉、不想活了等）
DANGER_KEYWORDS = ["想死", "自杀", "跳楼", "不想活了", "割脉", "吃药死", "杀人", "伤害自己", "结束生命"]

def check_safety(text):
    """检测输入内容是否包含危机词汇"""
    for word in DANGER_KEYWORDS:
        if word in text:
            return True
    return False

def get_safety_warning():
    """返回给学生的温馨提示"""
    return """
    ⚠️ **温馨提示**：
    亲爱的同学，看到你这段文字，老师很关心你现在的状态。
    请记得，你并不孤单，辅导老师们一直都在。
    
    如果你现在感到非常痛苦，请立刻通过以下方式联系我们：
    📞 **辅导处email**：counseling@smpinhwa.edu.my
    🆘 **Befrienders (24小时)**：03-76272929
    
    你可以现在就起身去辅导处找老师聊聊，我们随时欢迎你。
    """
