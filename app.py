import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

# --- 1. 基础配置 ---
st.set_page_config(page_title="滨华生命向导", page_icon="🌱")

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# --- 2. 登录逻辑 (保持不变) ---
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

# --- 3. 侧边栏：系统切换与知情同意 ---
with st.sidebar:
    st.title(f"你好, {st.session_state.student_id}")
    system_mode = st.radio("选择模式", ["🌱 生命向导 (心理画像)", "🔍 心情检测 (PY计划)"])
    
    st.divider()
    st.markdown("### 📜 知情同意与保密")
    st.caption("""
    我们的谈话是保密的。
    只有当你提到想要**伤害自己或他人**时，
    我会联系学校辅导老师协助以确保安全。
    """)
    
    if st.button("安全退出登录"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# --- 4. 初始化不同模式的指令 ---
if "messages" not in st.session_state or "current_mode" not in st.session_state or st.session_state.current_mode != system_mode:
    st.session_state.current_mode = system_mode
    
    if system_mode == "🌱 生命向导 (心理画像)":
        sys_prompt = """你是一位温柔包容的滨华中学辅导老师。
        你的任务是：通过访谈建立学生的‘心理画像’。
        
        [核心访谈维度]：
        1. 自我价值：深挖学生价值感来源（成绩还是内在）。
        2. 家庭资源：了解家庭是支持还是压力。
        3. 职业志向：通过兴趣捕捉未来的可能性。
        
        [沟通规则]：
        - 必须在第一句话告知保密协议与保密例外。
        - 采用‘主动引导’。根据Context Chain记忆，对学生提到的关键词（如‘怕’、‘梦想’、‘父母’）进行深挖。
        - 语气要像春风一样，多用‘我注意到...’‘谢谢你愿意分享...’。
        """
    else:
        sys_prompt = "你是一位专业的心理辅导员，请通过对话评估 PHQ-9 忧郁指标。完成后加 [COMPLETE]。"

    st.session_state.messages = [{"role": "system", "content": sys_prompt}]
    # 引导语
    initial_msg = "你好呀！我是你的 AI 心理伙伴。在这里我们可以聊任何事，我也想陪你一起发现更好的自己。我们要聊的事是保密的（除非涉及安全风险）。准备好了吗？"
    st.session_state.messages.append({"role": "assistant", "content": initial_msg})

# --- 5. 聊天界面与 Context Chain 实现 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        # 发送完整的 st.session_state.messages (实现 Context Chain)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=st.session_state.messages
        )
        ai_msg = response.choices[0].message.content
        st.write(ai_msg)
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        
        # 存入数据库，标记系统类型
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": "Navigator" if system_mode == "🌱 生命向导 (心理画像)" else "PY"
        }).execute()
