import sys
import io
import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
from datetime import datetime

# 1. 编码修复 (确保服务器端中文显示正常)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 2. 基础配置 ---
st.set_page_config(page_title="心情树洞", page_icon="🌱", layout="centered")

# 初始化 Supabase 连接
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# 配置 DeepSeek AI
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"], 
    base_url="https://api.deepseek.com"
)

# --- 3. 核心保存函数 (同步到 chat_logs 表) ---
def save_to_db(student_id, user_msg, ai_msg, is_summary=False):
    try:
        # 数字化预警：检测关键词
        danger_list = ["想死", "自杀", "跳楼", "不活了", "离开世界", "吃药"]
        risk_score = 0
        
        if not is_summary and any(word in user_msg for word in danger_list):
            risk_score = 10
        
        data = {
            "student_id": student_id,
            "user_input": user_msg if not is_summary else "--- 评估总结 ---",
            "ai_response": ai_msg,
            "risk_score": risk_score
        }
        supabase.table("chat_logs").insert(data).execute()
    except Exception as e:
        st.sidebar.error(f"云端同步失败: {e}")

# --- 4. 登录界面 (3000人名单校验) ---
if "student_id" not in st.session_state:
    st.title("🌱 中学生心情树洞")
    st.info("欢迎来到滨华中学心情树洞。请输入学号和密码以开始你的心理健康评估。")
    
    with st.form("login_box"):
        input_id = st.text_input("学号：", placeholder="例如：2026001").strip()
        input_pw = st.text_input("密码：", type="password").strip()
        submit_button = st.form_submit_button("登录进入系统")
        
        if submit_button:
            if not input_id or not input_pw:
                st.warning("请填写完整的学号和密码")
            else:
                try:
                    # 联网比对名单
                    res = supabase.table("students").select("*").eq("student_id", input_id).execute()
                    
                    if res.data and len(res.data) > 0:
                        db_pw = str(res.data[0]["password"]).strip()
                        if db_pw == input_pw:
                            st.session_state.student_id = input_id
                            st.session_state.chat_count = 0
                            st.session_state.can_exit = False
                            st.session_state.messages = [
                                {"role": "system", "content": """你是一位专业的学校心理辅导员。
                                你的任务：通过对话温和地评估 PHQ-9 的 9 个维度。
                                重要规则：如果学生回答敷衍，请换种方式引导。
                                当你认为已经收集到了足够的心理状态信息，请在回复的结尾加上特殊标记 [COMPLETE]。"""},
                                {"role": "assistant", "content": f"同学你好（学号：{input_id}）！我是你的 AI 心理伙伴。🌱\n今天的对话是为了了解你最近的心情和生活状态。\n\n当左边的退出按钮解锁时，说明我们的评估已完成。通常需要认真交流 10 到 15 轮。\n我们先开始吧：你最近在学校过得怎么样？"}
                            ]
                            st.success("验证成功，正在进入...")
                            st.rerun()
                        else:
                            st.error("❌ 密码错误")
                    else:
                        st.error("❌ 学号不存在，请联系咨询处。")
                except Exception as e:
                    st.error(f"系统连接异常: {e}")
    st.stop()

# --- 5. 侧边栏：对话指南与总结导出 ---
with st.sidebar:
    st.success(f"当前登录：{st.session_state.student_id}")
    
    is_unlocked = st.session_state.get("can_exit", False)
    current_count = st.session_state.get("chat_count", 0)
    
    st.markdown("### 📝 对话指南")
    st.write(f"💬 已交流轮数: **{current_count}**")
    
    # 动态进度条
    if not is_unlocked:
        st.info("💡 真实分享感受，可以帮助 AI 更快完成评估。")
        st.progress(min(current_count / 15, 0.95))
    else:
        st.success("✨ 评估信息已收集充分！")
        st.balloons()
        st.progress(1.0)
    
    st.divider()

    # 退出逻辑：AI判定完成 OR 20轮强制解锁
    can_exit_now = is_unlocked or current_count >= 20
    
    if st.button("✅ 提交评估并安全退出", disabled=not can_exit_now):
        with st.status("正在生成心理状态总结并上传云端..."):
            eval_messages = st.session_state.messages + [
                {"role": "user", "content": "请根据以上对话，参照 PHQ-9 标准，给该学生的忧郁倾向打分。返回 JSON: {'score': 分数, 'level': '等级', 'reason': '分析'}"}
            ]
            try:
                eval_res = client.chat.completions.create(model="deepseek-chat", messages=eval_messages)
                summary = eval_res.choices[0].message.content
                save_to_db(st.session_state.student_id, "FINAL_SUMMARY", summary, is_summary=True)
                st.success("评估已安全保存。")
                # 清空状态并重启
                for key in list(st.session_state.keys()): del st.session_state[key]
                st.rerun()
            except Exception as e:
                st.error(f"保存失败: {e}")

# --- 6. 聊天界面 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.chat_count += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
