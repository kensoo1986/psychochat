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

# --- 4. 初始化对话指令 (含 20 个细分评估点) ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        sys_prompt = """你是一位专业的心理辅导老师。你必须通过深度对话，逐一评估以下五个向度及其所有细分内容：

        1. 【自我价值感】：必须确认其‘价值感来源’、‘自我效能感’、‘核心负面信念’及‘身体与自我接纳’。
        2. 【家庭资源】：必须确认‘情感联结’、‘支持与压力平衡’、‘边界感与独立性’及‘冲突解决模式’。
        3. 【社交风格】：必须确认‘归属感与孤独感’、‘社交面具’、‘冲突处理能力’及‘社交边界感’。
        4. 【情绪稳定度】：必须观察‘情绪波动的振幅频率’、‘触发门槛’、‘自我调节修复能力’及‘极端表现’。
        5. 【生涯志向】：必须确认‘兴趣深度(心流)’、‘生涯掌控感’、‘目标感’并初步匹配‘职业原型’。

        [执行指令]：
        - 针对每个细项必须有针对性追问，禁止学生回答‘还好’就通过。
        - 只有当你确信该向度的【所有细项】都已搜集完毕，才在回复末尾加上隐藏标签 #向度X# (X为1-5)。
        - 每一条回复必须先共情，字数严控在 80 字内。"""
        init_text = "你好呀！我是你的心灵之友。🌱 我们的话是保密的（安全风险除外）。今天想和我分享你的什么心情或故事吗？"
    else:
        sys_prompt = "你是一位专业心理辅导员，评估 PHQ-9 指标。完成后加 [COMPLETE]。"
        init_text = "你好，最近两周，你觉得自己心情怎么样？"

    st.session_state.messages = [
        {"role": "system", "content": sys_prompt}, 
        {"role": "assistant", "content": init_text}
    ]

# --- 5. 侧边栏 (实时进度监控) ---
with st.sidebar:
    st.title("💎 探索中心")
    st.info("💡 请尽量与 AI 深入交流。AI 需要完成以下细节评估后，才会出现“完成评估”按键。")
    
    current_done = set(st.session_state.completed_dimensions)
    dim_count = len(current_done)
    progress = dim_count / 5.0
    
    st.markdown(f"**心灵图鉴完成度：{int(progress * 100)}%**")
    st.progress(progress)
    
    # 细项提示展示
    details = {
        1: "自我价值（来源、效能、信念、接纳）",
        2: "家庭资源（联结、平衡、边界、冲突）",
        3: "社交风格（归属、面具、冲突、边界）",
        4: "情绪稳定（振幅、门槛、修复、表现）",
        5: "生涯志向（心流、自主、目标、原型）"
    }

    for i in range(1, 6):
        status = "🟢" if i in current_done else "⚪"
        st.write(f"{status} **向度 {i}**")
        st.caption(details[i]) 

    st.divider()

    # 按钮逻辑：只有满 5 个向度才释放
    if dim_count >= 5:
        st.success("✨ 评估已圆满完成！")
        if st.button("✅ 完成评估并退出账号", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    else:
        st.button(f"还差 {5 - dim_count} 个向度，暂不可退出", disabled=True)

# 显示历史消息
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            # 过滤隐藏标签
            clean_content = msg["content"].split("#向度")[0].split("[COMPLETE]")[0]
            st.write(clean_content)

# 聊天输入
if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        response = client.chat.completions.create(model="deepseek-chat", messages=st.session_state.messages)
        ai_msg = response.choices[0].message.content
        st.write(ai_msg.split("#向度")[0]) 
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        
        # 标签侦测
        updated = False
        for i in range(1, 6):
            tag = f"#向度{i}#"
            if tag in ai_msg and i not in st.session_state.completed_dimensions:
                st.session_state.completed_dimensions.append(i)
                updated = True
        
        # 存入数据库
        supabase.table("chat_logs").insert({
            "student_id": st.session_state.student_id,
            "user_input": prompt,
            "ai_response": ai_msg,
            "system_type": st.session_state.current_mode
        }).execute()
        
        if updated: st.rerun()
