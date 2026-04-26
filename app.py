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
if st.session_state.current_mode == "Navigator":
        sys_prompt = """你是一位专业的心理辅导老师（心灵之友 AI）。
        
        你的任务是完成【五维心灵图鉴】的评估。在对话结束前，你必须确保调查完以下所有要点：

        1. 【自我价值感】：
           - 确认价值感来源（内在 vs 外在成绩）
           - 确认自我效能感（面对挑战的信心）
           - 探测是否有“我不够好”等负面核心信念
        
        2. 【家庭资源】：
           - 确认与父母的情感联结深度
           - 确认父母期待带来的压力值
           - 确认家庭内部的冲突处理模式
        
        3. 【社交风格】：
           - 确认班级归属感（是否有真实朋友）
           - 观察是否存在社交掩饰（面具）
        
        4. 【情绪稳定度】：
           - 观察近期情绪波动的频率
           - 确认情绪失衡后的自我修复能力
        
        5. 【生涯志向】：
           - 确认是否存在自发热爱的兴趣点
           - 确认对未来选择的掌控感
        
        [访谈策略]：
        - 禁止连续提问：每轮对话必须先针对学生上一句话进行“情感回应（共情）”，然后再抛出一个深挖的问题。
        - 深度要求：每个向度至少需要 2-3 次追问，确认学生给出了“实质性内容”而非敷衍（如“还好”、“不知道”）。
        - 标签机制：只有当你确信已经掌握了该向度的所有“数据采集点”，才在回复末尾加上 #向度X#。
        """
    else:
        sys_prompt = "你是一位专业心理辅导员，评估 PHQ-9 指标。完成后加 [COMPLETE]。"
        init_text = "你好，最近两周，你觉得自己心情怎么样？"

    st.session_state.messages = [{"role": "system", "content": sys_prompt}, {"role": "assistant", "content": init_text}]
    if "completed_dimensions" not in st.session_state:
        st.session_state.completed_dimensions = []

# --- 5. 侧边栏 (进度条与引导语) ---
# --- 侧边栏逻辑修改 ---
with st.sidebar:
    st.title("💎 探索中心")
    
    # 获取当前已点亮的向度数量
    dim_count = len(set(st.session_state.completed_dimensions))
    progress = dim_count / 5.0
    
    # 动态提示
    if dim_count < 5:
        st.warning(f"目前已完成 {dim_count}/5 个向度。")
        st.info("AI 需要更深入地了解你的家庭、社交、情绪和未来志向后，才能为你生成报告。")
    else:
        st.success("🎉 太棒了！五大向度已全部评估完成。")

    # 只有进度条满 100% (5个向度) 且 AI 确认后，按钮才可用
    if progress >= 1.0:
        if st.button("✅ 点击生成完整心灵报告并退出", use_container_width=True):
            # 这里可以调用一个专门的总结函数，把对话发给 AI 总结出 5 个维度的分数或文字
            # 然后再清空状态退出
            for key in list(st.session_state.keys()):
                if key != "student_id": del st.session_state[key]
            st.rerun()
    else:
        # 进度没满时，按钮是灰色不可点的
        st.button("评估进行中，暂不可退出", disabled=True)

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
