import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import os

# --- 1. 初始化连接 ---
st.set_page_config(page_title="心情树洞", page_icon="🌱")

# 数据库连接（工业级并发支持）
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# AI 连接
client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# --- 2. 账号数据库 ---
USER_DATABASE = {
    "2026001": "pw123",
    "2026002": "pw456",
    "test": "test123"
}

# --- 3. 核心保存函数 (Supabase) ---
def save_to_db(student_id, user_msg, ai_msg, risk_score=0):
    try:
        data = {
            "student_id": student_id,
            "user_input": user_msg,
            "ai_response": ai_msg,
            "risk_score": risk_score
        }
        # 即使 3000 人同时操作，数据库也会自动排队处理
        supabase.table("chat_logs").insert(data).execute()
    except Exception as e:
        st.sidebar.error(f"存储异常: {e}")

# --- 4. 登录界面 ---
if "student_id" not in st.session_state:
    st.title("🌱 中学生心情树洞")
    with st.form("login_form"):
        input_id = st.text_input("请输入学号：")
        input_pw = st.text_input("请输入密码：", type="password")
        if st.form_submit_button("登录进入系统"):
            if input_id in USER_DATABASE and USER_DATABASE[input_id] == input_pw:
                st.session_state.student_id = input_id
                st.session_state.chat_count = 0
                st.session_state.can_exit = False
                st.session_state.messages = [
                    {"role": "system", "content": "你是一位学校辅导员，温和评估 PHQ-9。完成后结尾加 [COMPLETE]。"},
                    {"role": "assistant", "content": f"同学你好（{input_id}）！最近心情怎么样？"}
                ]
                st.rerun()
            else:
                st.error("❌ 验证失败")
    st.stop()

# --- 5. 侧边栏与退出 ---
with st.sidebar:
    st.success(f"当前：{st.session_state.student_id}")
    count = st.session_state.chat_count
    st.write(f"💬 对话轮数: {count}")
    st.progress(min(count / 15, 1.0))
    
    if st.session_state.can_exit or count >= 20:
        if st.button("✅ 评估完成：点击提交退出"):
            # 生成最终总结逻辑
            st.success("数据已同步至云端。")
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

# --- 6. 聊天逻辑 ---
for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]): st.write(msg["content"])

if prompt := st.chat_input("说吧..."):
    st.session_state.chat_count += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        completion = client.chat.completions.create(model="deepseek-chat", messages=st.session_state.messages)
        full_res = completion.choices[0].message.content
        
        if "[COMPLETE]" in full_res:
            st.session_state.can_exit = True
            full_res = full_res.replace("[COMPLETE]", "")
        
        st.write(full_res)
        st.session_state.messages.append({"role": "assistant", "content": full_res})
        
        # 数字化预警逻辑
        score = 10 if any(w in prompt for w in ["想死", "自杀", "跳楼", "不活了"]) else 0
        save_to_db(st.session_state.student_id, prompt, full_res, score)
