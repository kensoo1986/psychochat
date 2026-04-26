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

# --- 3. 模式选择界面 ---
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

    st.divider() 
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        if st.button("退出账号", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    st.stop()

# --- 4. 初始化对话 (修复语法重叠问题) ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        sys_prompt = """你是一位滨华中学的心理辅导老师。你的任务是通过对话完成学生的“五维生命画像”。
        
        [五个核心向度]：
        1. 自我价值：关注其价值感是来自成绩还是内在认同。
        2. 家庭资源：识别家庭是支持系统还是压力源。
        3. 社交风格：了解其在同伴关系中的归属感与冲突处理。
        4. 应对机制：观察面对挫折时的情绪韧性与反应模式。
        5. 职业志向：捕捉其眼里有光的瞬间，识别职业兴趣原型。

        [沟通准则]：
        - 情感先行：必须先用一句话反映并接住学生的情绪（如：'听起来那次经历让你很挫败...'）。
        - 丝滑切换：利用 Context Chain 顺着学生的话题自然地滑向这五个向度。
        - 微信化短句：控制在 60 字左右，每次只问一个问题。
        - 保密例外：首句需简短提及。
        """
        init_text = "你好呀！我是你的生命向导。🌱 我们的话是保密的（安全风险除外）。今天有什么想和我聊聊的心情或故事吗？"
    else:
        sys_prompt = "你是一位专业的心理辅导员，请通过精简对话评估 PHQ-9 指标。回复不超过 30 字。完成后加 [COMPLETE]。"
        init_text = "你好，我是心情检测员。🌱 我们的话保密（安全风险除外）。最近两周，你觉得自己心情怎么样？"

    st.session_state.messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "assistant", "content": init_text}
    ]

# --- 5. 聊天界面与侧边栏 ---
with st.sidebar:
    st.write(f"当前模式：{st.session_state.current_mode}")
    if st.button("切换模式"):
        for key in list(st.session_state.keys()):
            if key != "student_id": del st.session_state[key]
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
        
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": st.session_state.current_mode
        }).execute()
