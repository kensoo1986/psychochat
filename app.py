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

# --- 4. 初始化对话指令 (深度评估版) ---
if "messages" not in st.session_state:
    if st.session_state.current_mode == "Navigator":
        sys_prompt = """你是一位专业的心理辅导老师。你必须通过深度对话，逐一评估以下五个向度及其细分内容。
        
        【评估清单与标准】：
        1. 自我价值感：必须确认其‘价值感来源’、‘自我效能感（面对困难的信心）’、‘核心负面信念（如：我不配）’及‘身体与自我接纳’。
        2. 家庭资源：必须确认‘情感联结’、‘支持与压力的平衡’、‘边界感与独立性’以及家庭的‘冲突解决模式’。
        3. 社交风格：必须确认学生的‘归属感与孤独感’、‘社交面具（是否在演戏）’、‘冲突处理能力’及‘社交边界感’。
        4. 情绪稳定度：必须观察‘情绪波动的振幅频率’、‘触发门槛（什么会激怒他）’、‘自我调节修复能力’及‘极端情绪表现’。
        5. 生涯志向：必须确认‘兴趣的深度（心流）’、‘生涯掌控感与自主权’、‘自我效能目标感’并初步匹配‘职业原型’。

        【执行指令】：
        - **强制深度**：针对以上每个小点，你必须有针对性地提问。禁止在没有获取具体细节前打勾。
        - **逐项过关**：你不需要一次性问完，可以顺着话题聊。但只有当你认为某向度的【所有细节】都搜集完毕，才在末尾加上 #向度X#。
        - **回复要求**：第一句必须共情。回复严控在 100 字内。
        """
    else:
        sys_prompt = "你是一位专业心理辅导员，评估 PHQ-9 指标。完成后加 [COMPLETE]。"
        init_text = "你好，最近两周，你觉得自己心情怎么样？"

    st.session_state.messages = [{"role": "system", "content": sys_prompt}, {"role": "assistant", "content": init_text}]

# --- 5. 侧边栏 (实时进度监控) ---
with st.sidebar:
    st.title("💎 探索中心")
    st.info("💡 请尽量与 AI 深入交流。当五大维度全部评估完成后，才会出现“完成评估”按键。")
    
    # 使用 set 去重
    current_done = set(st.session_state.completed_dimensions)
    dim_count = len(current_done)
    progress = dim_count / 5.0
    
    st.markdown(f"**心灵图鉴完成度：{int(progress * 100)}%**")
    st.progress(progress)
    
    dims_list = ["自我价值感", "家庭资源", "社交风格", "情绪稳定度", "生涯志向"]
    for i, name in enumerate(dims_list):
        status = "🟢" if (i+1) in current_done else "⚪"
        st.write(f"{status} {name}")

    st.divider()
    if dim_count >= 5:
        st.success("✨ 评估已圆满完成！")
        if st.button("✅ 完成评估并退出", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key != "student_id": del st.session_state[key]
            st.rerun()
    else:
        st.warning(f"还需要探索 {5 - dim_count} 个维度...")

# 显示历史消息
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            # 过滤掉隐藏标签再显示给学生
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
        
        # --- 核心修复点：检测标签并触发 rerun ---
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
        
        if updated: st.rerun() # 如果进度更新，立刻刷新界面
