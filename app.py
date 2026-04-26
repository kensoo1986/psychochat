import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

# --- 1. 基础配置 ---
st.set_page_config(page_title="心灵之友 AI", page_icon="🌱")

# 初始化 API 与 数据库连接
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
    st.stop()

# --- 4. 初始化对话指令 (深度核查版：确保覆盖 20 个细分要点) ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        # 这里是核心：把您的要求变成 AI 的“硬性结案标准”
        sys_prompt = """你是一位专业的心理辅导老师。你的任务是完成【五维心灵图鉴】。
        
        【重要：你必须深入询问并确认以下所有细节，否则严禁标记完成】
        
        1. 【自我价值感】：
           - 必须深挖：价值来源(内外驱动)、自我效能感、核心负面信念(如'我不配')、身体与自我接纳。
        2. 【家庭资源】：
           - 必须深挖：情感联结深度、支持与压力平衡(期望是否过重)、边界感独立性、冲突解决模式。
        3. 【社交风格】：
           - 必须深挖：归属感与孤独感、社交面具(真实自我展示程度)、冲突处理、社交边界。
        4. 【个人情绪稳定度】：
           - 必须观察：情绪波动的频率与振幅、触发门槛、自我调节修复能力、极端表现形式。
        5. 【生涯志向】：
           - 必须深挖：兴趣深度(是否有心流体验)、生涯掌控感自主权、目标感、职业原型匹配。

        【访谈策略】：
        - 严禁‘查户口’。请通过‘共情 -> 引导 -> 深度追问’的方式进行。
        - 如果学生回答模糊(如'还可以'、'挺好的')，你必须换角度继续追问，直到获得具体的事实或感受。
        - 只有当你确信已经搜集齐了该向度【所有细分内容】的证据，才在回复末尾打上 #向度X#。
        - 每一条回复必须字数严控在 80 字内，保持温暖、专业。"""
        
        init_text = "你好呀！我是你的心灵之友 🌱。在这里，你可以放心地做自己。今天想和我聊聊关于你自己、学校或者未来的任何事情吗？"
    else:
        sys_prompt = "你是一位专业心理辅导员，评估 PHQ-9 指标。完成后加 [COMPLETE]。"
        init_text = "你好，最近两周，你觉得自己心情怎么样？"

    st.session_state.messages = [
        {"role": "system", "content": sys_prompt}, 
        {"role": "assistant", "content": init_text}
    ]

# --- 5. 侧边栏 (显示实时评估进度) ---
with st.sidebar:
    st.title("💎 评估进度")
    st.info("AI 会针对你的自我、家庭、社交、情绪和未来进行深度访谈。只有当 5 个向度的细节全部聊透，评估才算完成。")
    
    current_done = set(st.session_state.completed_dimensions)
    dim_count = len(current_done)
    progress = dim_count / 5.0
    
    st.progress(progress)
    st.write(f"总体完成度: {int(progress * 100)}%")
    
    # 细项提示展示
    details = {
        1: "自我价值 (来源/效能/信念/接纳)",
        2: "家庭资源 (联结/平衡/边界/冲突)",
        3: "社交风格 (归属/面具/冲突/边界)",
        4: "情绪稳定 (振幅/门槛/修复/表现)",
        5: "生涯志向 (心流/自主/目标/原型)"
    }

    for i in range(1, 6):
        status = "🟢" if i in current_done else "⚪"
        st.write(f"{status} 向度 {i}: {details[i]}")

    st.divider()

    if dim_count >= 5:
        st.success("🎉 所有细节已评估完毕！")
        if st.button("✅ 提交报告并退出", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    else:
        st.button(f"评估中 (还剩 {5 - dim_count} 项未深入)", disabled=True)

# 显示历史消息 (过滤掉给 AI 看的隐藏标签)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            clean_content = msg["content"].split("#向度")[0].split("[COMPLETE]")[0]
            st.write(clean_content)

# 聊天输入处理
if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        # 将整个对话历史发送给 AI，让它有记忆地去核对“评估清单”
        response = client.chat.completions.create(model="deepseek-chat", messages=st.session_state.messages)
        ai_msg = response.choices[0].message.content
        
        # 显示时不让学生看到标签
        st.write(ai_msg.split("#向度")[0]) 
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        
        # 标签侦测
        updated = False
        for i in range(1, 6):
            tag = f"#向度{i}#"
            if tag in ai_msg and i not in st.session_state.completed_dimensions:
                st.session_state.completed_dimensions.append(i)
                updated = True
        
        # 存入数据库供辅导员后期查阅
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": st.session_state.current_mode
        }).execute()
        
        # 如果点亮了新绿灯，立即刷新
        if updated: st.rerun()
