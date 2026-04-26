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

# --- 3. 模式选择界面 ---
if "current_mode" not in st.session_state:
    st.title(f"你好，{st.session_state.student_id}")
    st.subheader("请选择你今天想进行的活动：")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌟 心灵之友 (自我探索)", use_container_width=True):
            st.session_state.current_mode = "Navigator"
            st.session_state.chat_count = 0
            st.session_state.completed_dimensions = [] # 初始化完成维度
            st.rerun()
    with col2:
        if st.button("🔍 心情检测 (PY计划)", use_container_width=True):
            st.session_state.current_mode = "PY"
            st.session_state.chat_count = 0
            st.rerun()
    
    st.divider()
    if st.button("🚪 退出账号"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    st.stop()

# --- 4. 初始化对话指令 (强化任务引导) ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        sys_prompt = """你是一位温柔的辅导老师‘心灵之友’。
        你的终极任务是引导学生聊透以下五个维度：
        1. 自我价值感 (自信来源)
        2. 家庭资源 (家庭支持/压力)
        3. 社交风格 (同伴关系)
        4. 应对机制 (面对挫败的表现)
        5. 职业志向 (梦想兴趣)

        [规则]：
        - 每次只深挖一个维度。只有当学生聊够了，再温柔转向下一个。
        - 必须先接住学生的情绪（共情），再进行引导。
        - 每条回复控制在 60 字内，像微信聊天一样。
        - **重点**：每当你觉得已经‘基本了解’了其中一个维度，请在回复的最末尾加上该维度的隐藏标签（例如：#向度1#），不要告诉学生。"""
        init_text = "你好呀！我是你的心灵之友。🌱 我们的话是保密的（安全风险除外）。今天想和我分享你的什么心情或故事吗？"
    else:
        sys_prompt = "你是一位专业心理辅导员，评估 PHQ-9 指标。完成后加 [COMPLETE]。"
        init_text = "你好，最近两周，你觉得自己心情怎么样？"

    st.session_state.messages = [{"role": "system", "content": sys_prompt}, {"role": "assistant", "content": init_text}]
    if "completed_dimensions" not in st.session_state:
        st.session_state.completed_dimensions = []

# --- 5. 侧边栏 (进度条与引导语) ---
with st.sidebar:
    st.title("💎 探索中心")
    st.info("💡 请尽量与AI对话。当完成五大维度评估后，会出现“完成退出”按键，并生成完整报告。")
    
    # 进度计算逻辑
    dim_count = len(set(st.session_state.completed_dimensions)) # 使用 set 避免重复计数
    progress = min(dim_count / 5.0, 1.0)
    
    st.markdown(f"**心灵图鉴完成度：{int(progress * 100)}%**")
    st.progress(progress)
    
    # 向度点亮显示
    dims_list = ["自我价值", "家庭资源", "社交风格", "应对机制", "职业志向"]
    for i, name in enumerate(dims_list):
        status = "🟢" if (i+1) in st.session_state.completed_dimensions else "⚪"
        st.write(f"{status} {name}")

    if progress >= 1.0:
        st.success("✨ 五大维度已完成！")
        if st.button("✅ 完成评估并退出", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key != "student_id": del st.session_state[key]
            st.rerun()

# 显示对话
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"].split("#")[0]) # 隐藏给 AI 看的标签

# 聊天输入与逻辑处理
if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(model="deepseek-chat", messages=st.session_state.messages)
        ai_msg = response.choices[0].message.content
        st.write(ai_msg.split("#")[0]) # 不让学生看到 #向度# 标签
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        
        # --- 核心逻辑：检测 AI 是否打上了维度完成标签 ---
        for i in range(1, 6):
            tag = f"#向度{i}#"
            if tag in ai_msg and i not in st.session_state.completed_dimensions:
                st.session_state.completed_dimensions.append(i)
                st.rerun() # 立即刷新侧边栏进度
        
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": st.session_state.current_mode
        }).execute()
