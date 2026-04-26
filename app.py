import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

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

# --- 3. 模式选择界面 (登录后的拦截页) ---
if "current_mode" not in st.session_state:
    st.title(f"你好，{st.session_state.student_id}")
    st.subheader("请选择你今天想进行的活动：")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌟 心灵之友 (自我探索)", use_container_width=True):
            st.session_state.current_mode = "Navigator"
            st.session_state.chat_count = 0 # 重置对话计数
            st.rerun()
    with col2:
        if st.button("🔍 心情检测 (PY计划)", use_container_width=True):
            st.session_state.current_mode = "PY"
            st.session_state.chat_count = 0
            st.rerun()
    
    st.info("💡 提示：'心灵之友' 通过对话带你探索自我；'心情检测' 关注你近期的情绪状态。")
    
    st.divider()
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        if st.button("🚪 退出账号 / 换人登录", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    st.stop()

# --- 4. 初始化对话指令 ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        sys_prompt = """你是一位滨华中学的辅导老师，现在身份是‘心灵之友’。
        你的任务是通过对话完成学生的“五维心灵图鉴”。
        
        [五个核心向度]：
        1. 自我价值：关注其价值感来源。
        2. 家庭资源：识别家庭支持力。
        3. 社交风格：了解同伴归属感。
        4. 应对机制：观察面对挫折的反应。
        5. 职业志向：捕捉其眼里有光的瞬间。

        [沟通准则]：
        - 情感先行：必须先接住学生的情绪（如：'这件事让你感到很委屈吧？'）。
        - 微信化短句：控制在 60 字内，每次只问一个问题。
        - 保密例外：首句需简短提及。
        """
        init_text = "你好呀！我是你的心灵之友。🌱 我们的话是保密的（安全风险除外）。今天想和我分享你的什么心情或故事吗？"
    else:
        sys_prompt = "你是一位专业的心理辅导员，请通过精简对话评估 PHQ-9 指标。每条回复不超过 40 字。完成后加 [COMPLETE]。"
        init_text = "你好，我是心情检测员。🌱 我们的话保密（安全风险除外）。最近两周，你觉得自己心情怎么样？"

    st.session_state.messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "assistant", "content": init_text}
    ]

# --- 5. 聊天界面与侧边栏 (加入温馨提示) ---
with st.sidebar:
    st.title("💎 探索中心")
    st.write(f"当前模式：{'心灵之友' if st.session_state.current_mode == 'Navigator' else '心情检测'}")
    
    st.divider()

    # --- 新增：给学生的引导提示 ---
    st.markdown("### 💡 温馨提示")
    st.info("""
    请尽量与 AI 深入对话。当进度达到 **100%** 时，下方会出现 **“完成评估”** 按键。
    
    点击后，辅导处将根据你的对话生成一份**完整的自我心灵图鉴**。
    """)
    st.divider()

    # 进度条逻辑
    max_rounds = 6
    progress = min(st.session_state.chat_count / max_rounds, 1.0)
    st.markdown(f"**目前探索进度：{int(progress * 100)}%**")
    st.progress(progress)
    
    # 动态显示完成按钮
    if progress >= 1.0:
        st.success("✨ 太棒了！探索已完成。")
        if st.button("✅ 完成评估并查看报告", use_container_width=True):
            # 这里是退出逻辑，后续我们可以接入跳转到报告页面的逻辑
            for key in list(st.session_state.keys()):
                if key != "student_id": del st.session_state[key]
            st.rerun()
    
    st.divider()
    if st.button("🔄 切换模式"):
        for key in list(st.session_state.keys()):
            if key != "student_id": del st.session_state[key]
        st.rerun()

# 显示历史消息
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# 聊天输入
if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=st.session_state.messages
        )
        ai_msg = response.choices[0].message.content
        st.write(ai_msg)
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        
        # 增加计数
        st.session_state.chat_count += 1
        
        # 存入数据库
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": st.session_state.current_mode
        }).execute()
