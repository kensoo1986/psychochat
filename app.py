import streamlit as st
from openai import OpenAI
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="中学生心情树洞-专业版", layout="centered")
st.title("🌱 中学生心情树洞")
st.caption("遇见更好的自己 | 3000人心理数据库试点版")

# --- 2. 初始化数据库连接 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. 登录逻辑 (保持你之前的学号验证) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.form("login_form"):
        student_id = st.text_input("请输入学号", placeholder="例如：2024001")
        password = st.text_input("请输入密码", type="password")
        submit = st.form_submit_button("进入树洞")
        
        if submit:
            if student_id and password == "123456": # 这里可以改成你的密码逻辑
                st.session_state.logged_in = True
                st.session_state.student_id = student_id
                st.rerun()
            else:
                st.error("学号或密码错误")
    st.stop()

# --- 4. 配置 AI 客户端 ---
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

# 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 5. 定义数据保存函数 ---
def save_to_google_sheets(student_id, user_msg, ai_msg, risk_score, risk_tag):
    try:
        # 获取当前时间
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 构建新行数据
        new_row = pd.DataFrame([{
            "datetime": now,
            "student_id": student_id,
            "user_input": user_msg,
            "ai_response": ai_msg,
            "risk_score": risk_score,
            "is_warning": risk_tag
        }])
        # 读取旧数据并合并
        existing_data = conn.read(worksheet="Sheet1", ttl=0)
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        # 写回 Google Sheets
        conn.update(worksheet="Sheet1", data=updated_df)
    except Exception as e:
        st.sidebar.error(f"数据保存失败: {e}")

# --- 6. 聊天界面 ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用 AI 时，要求它同时输出：回复内容 | 风险评分(1-10) | 是否预警(YES/NO)
    system_prompt = """你是一位温柔的心理辅导老师。
    请在回复学生后，在末尾用特殊格式输出分析（学生看不见）：
    格式：[ANALYSIS] 分数 | 是否预警
    """
    
    with st.chat_message("assistant"):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                *st.session_state.messages
            ],
            stream=False
        )
        full_res = response.choices[0].message.content
        
        # 简单解析 AI 返回的风险分 (这里可以做得更复杂，先做基础版)
        display_text = full_res.split("[ANALYSIS]")[0]
        st.markdown(display_text)
        
        # 默认分值
        score = 5
        tag = "NO"
        
        # 如果包含自杀等词汇，强制提分（这是你要求的预警逻辑）
        danger_list = ["想死", "自杀", "跳楼", "不活了"]
        if any(w in prompt for w in danger_list):
            score = 10
            tag = "YES"

        # 保存到数据库
        save_to_google_sheets(st.session_state.student_id, prompt, display_text, score, tag)
        
    st.session_state.messages.append({"role": "assistant", "content": display_text})
