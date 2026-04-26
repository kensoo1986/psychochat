import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

import navigator_logic
import py_logic
import safety_utils
import crisis_manager # 新增危机管理模块

# --- 1. 基础配置 ---
st.set_page_config(page_title="心灵之友 AI - 安全版", page_icon="🌱")
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)
client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# --- 2. 登录与状态初始化 ---
if "student_id" not in st.session_state:
    st.title("🌱 滨华中学：心灵辅助系统")
    with st.form("login"):
        sid = st.text_input("学号").strip()
        pw = st.text_input("密码", type="password").strip()
        if st.form_submit_button("登录"):
            res = supabase.table("students").select("*").eq("student_id", sid).execute()
            if res.data and str(res.data[0]["password"]) == pw:
                st.session_state.student_id = sid
                st.rerun()
            else: st.error("登录失败")
    st.stop()

if "completed_dimensions" not in st.session_state: st.session_state.completed_dimensions = []
if "is_crisis" not in st.session_state: st.session_state.is_crisis = False # 危机标记

# --- 3. 模式选择 ---
if "current_mode" not in st.session_state:
    st.title(f"你好，{st.session_state.student_id}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌟 心灵探索之旅", use_container_width=True):
            st.session_state.current_mode = "Navigator"; st.rerun()
    with col2:
        if st.button("🔍 心情检测 (PY计划)", use_container_width=True):
            st.session_state.current_mode = "PY"; st.rerun()
    st.stop()

# --- 4. 初始化对话 ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        sys_prompt = navigator_logic.get_navigator_prompt()
        init_text = "你好呀！我是你的心灵之友 🌱。今天想和我聊聊吗？"
    else:
        sys_prompt = py_logic.get_py_prompt()
        init_text = py_logic.get_py_init_text()
    
    st.session_state.messages = [{"role": "system", "content": sys_prompt}, {"role": "assistant", "content": init_text}]

# --- 5. 侧边栏 ---
with st.sidebar:
    if st.session_state.is_crisis:
        st.error("❗ 处于预警评估状态")
        st.warning("请立即联系辅导处或拨打 Befrienders: 03-76272929")
    else:
        st.title("💎 探索中心")
        # 常规向度显示逻辑...
        if st.session_state.current_mode == "Navigator":
            current_done = set(st.session_state.completed_dimensions)
            details = navigator_logic.get_navigator_details()
            for i in range(1, 6):
                st.write(f"{'🟢' if i in current_done else '⚪'} {details[i]}")

# --- 6. 聊天逻辑 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"].split("#")[0].split("[URGENT")[0])

if prompt := st.chat_input("说点什么..."):
    # 安全检测
    if safety_utils.check_safety(prompt) and not st.session_state.is_crisis:
        st.session_state.is_crisis = True
        # 强制切换 AI 指令为危机干预模式
        st.session_state.messages = [{"role": "system", "content": crisis_manager.get_crisis_sys_prompt()}]
        st.rerun()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(model="deepseek-chat", messages=st.session_state.messages)
        ai_msg = response.choices[0].message.content
        st.write(ai_msg.split("#")[0].split("[URGENT")[0])
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        
        # 评估向度或危机等级记录
        db_type = "CRISIS" if st.session_state.is_crisis else st.session_state.current_mode
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": db_type
        }).execute()

        # Navigator 向度逻辑检测
        if st.session_state.current_mode == "Navigator" and not st.session_state.is_crisis:
            updated = False
            for i in range(1, 6):
                if f"#向度{i}#" in ai_msg and i not in st.session_state.completed_dimensions:
                    st.session_state.completed_dimensions.append(i); updated = True
            if updated: st.rerun()
