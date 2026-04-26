import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

# 导入新建立的区块化模块
import navigator_logic
import py_logic

# --- 1. 基础配置 ---
st.set_page_config(page_title="心灵之友 AI", page_icon="🌱")

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)
client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# --- 2. 登录逻辑 ---
if "student_id" not in st.session_state:
    st.title("🌱 滨华中学：心灵之友 AI")
    with st.form("login"):
        sid = st.text_input("学号").strip()
        pw = st.text_input("密码", type="password").strip()
        if st.form_submit_button("登录"):
            res = supabase.table("students").select("*").eq("student_id", sid).execute()
            if res.data and str(res.data[0]["password"]) == pw:
                st.session_state.student_id = sid
                st.rerun()
            else:
                st.error("学号或密码错误")
    st.stop()

# 初始化全局变量
if "completed_dimensions" not in st.session_state:
    st.session_state.completed_dimensions = []

# --- 3. 模式选择界面 ---
if "current_mode" not in st.session_state:
    st.title(f"你好，{st.session_state.student_id}")
    st.subheader("请选择你今天想进行的活动：")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌟 心灵之友 (自我探索)", use_container_width=True):
            st.session_state.current_mode = "Navigator"
            st.session_state.completed_dimensions = []
            st.rerun()
    with col2:
        if st.button("🔍 心情检测 (PY计划)", use_container_width=True):
            st.session_state.current_mode = "PY"
            st.rerun()
    
    st.divider()
    if st.button("🚪 退出账号"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    st.stop()

# --- 4. 初始化对话逻辑 (从模块获取指令) ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        sys_prompt = navigator_logic.get_navigator_prompt()
        init_text = "你好呀！我是你的心灵之友 🌱。我们的话是保密的（安全风险除外）。今天想和我聊聊关于你自己、学校或者未来的任何事情吗？"
    else:
        sys_prompt = py_logic.get_py_prompt()
        init_text = py_logic.get_py_init_text()

    st.session_state.messages = [{"role": "system", "content": sys_prompt}, {"role": "assistant", "content": init_text}]

# --- 5. 侧边栏 ---
with st.sidebar:
    st.title("💎 探索中心")
    if st.session_state.current_mode == "Navigator":
        current_done = set(st.session_state.completed_dimensions)
        dim_count = len(current_done)
        progress = dim_count / 5.0
        
        st.markdown(f"**心灵图鉴完成度：{int(progress * 100)}%**")
        st.progress(progress)
        
        details = navigator_logic.get_navigator_details()
        for i in range(1, 6):
            status = "🟢" if i in current_done else "⚪"
            st.write(f"{status} 向度 {i}: {details[i]}")

        st.divider()
        if dim_count >= 5:
            st.success("✨ 评估已圆满完成！")
            if st.button("✅ 完成评估并退出", use_container_width=True):
                for key in list(st.session_state.keys()):
                    if key != "student_id": del st.session_state[key]
                st.rerun()
        else:
            st.button(f"还需要探索 {5 - dim_count} 个维度", disabled=True)
    else:
        st.write("正在进行心情检测...")
        if st.button("返回主菜单"):
            for key in list(st.session_state.keys()):
                if key != "student_id": del st.session_state[key]
            st.rerun()

# --- 6. 聊天处理 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"].split("#")[0].split("[COMPLETE]")[0])

if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(model="deepseek-chat", messages=st.session_state.messages)
        ai_msg = response.choices[0].message.content
        st.write(ai_msg.split("#")[0].split("[COMPLETE]")[0])
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        
        # 心灵之友模式下的向度检测逻辑
        if st.session_state.current_mode == "Navigator":
            updated = False
            for i in range(1, 6):
                tag = f"#向度{i}#"
                if tag in ai_msg and i not in st.session_state.completed_dimensions:
                    st.session_state.completed_dimensions.append(i)
                    updated = True
            if updated: st.rerun()
        
        # 存入数据库
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": st.session_state.current_mode
        }).execute()
