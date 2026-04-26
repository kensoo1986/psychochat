import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

# --- 1. 基础配置 ---
st.set_page_config(page_title="滨华生命向导", page_icon="🌱")

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)
client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# --- 2. 登录逻辑 ---
if "student_id" not in st.session_state:
    st.title("🌱 滨华中学：生命向导系统")
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

# --- 3. 模式选择界面 (登录后第一步) ---
if "current_mode" not in st.session_state:
    st.title(f"你好，{st.session_state.student_id}")
    st.subheader("请选择你今天想进行的活动：")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌱 生命向导 (探索自我)", use_container_width=True):
            st.session_state.current_mode = "Navigator"
            st.rerun()
    with col2:
        if st.button("🔍 心情检测 (PY计划)", use_container_width=True):
            st.session_state.current_mode = "PY"
            st.rerun()
    
    st.info("💡 提示：'生命向导'侧重于了解你的兴趣与成长；'心情检测'侧重于近期的情绪评估。")
    st.stop()

# --- 4. 初始化对话 (选择模式后) ---
if "messages" not in st.session_state:
    mode_name = "生命向导" if st.session_state.current_mode == "Navigator" else "心情检测"
    
    # 重新设计的精简指令
    if st.session_state.current_mode == "Navigator":
        sys_prompt = """你是一位滨华中学的心理辅导老师。你的灵魂核心是“共情”和“接住”。
        
        [沟通准则]：
        1. **先共情，后引导**：学生说话后，你必须先用一句话反映他的情感（如：‘这件事让你感到很委屈吧？’或‘我能感受到你现在的压力...’）。
        2. **禁止连环炮提问**：每一轮回复只能有一个温柔的追问，甚至可以没有追问，只是纯粹的理解。
        3. **微信化短句**：每条回复控制在 60 字左右。不要讲大道理，要像在耳边温柔低语。
        4. **记忆深挖**：利用 Context Chain 提到他之前说的情感点（如：‘你刚才说妈妈不理解，这种不被看见的感觉，是不是一直让你很孤独？’）。
        
        [保密提醒]：首句需简短提及保密例外。
        """
    else:
        sys_prompt = "你是一位专业的心理辅导员，请通过精简的对话评估 PHQ-9 指标。每条回复不超过 60 字。完成后加 [COMPLETE]。"
        initial_msg = "你好，我是心情检测员。🌱 我们的谈话保密（除非涉及安全风险）。最近两周，你的心情还好吗？"

    st.session_state.messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "assistant", "content": initial_msg}
    ]

# --- 5. 聊天界面 (侧边栏仅作退出用) ---
with st.sidebar:
    st.write(f"当前模式：{st.session_state.current_mode}")
    if st.button("切换模式 / 退出"):
        for key in list(st.session_state.keys()):
            if key != "student_id": del st.session_state[key]
        if "current_mode" in st.session_state: del st.session_state["current_mode"]
        st.rerun()

for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

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
        
        # 存入数据库
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": st.session_state.current_mode
        }).execute()
