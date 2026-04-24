import sys
import io
import os
import streamlit as st
from openai import OpenAI
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 编码修复
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 2. 配置 ---
st.set_page_config(page_title="心情树洞", page_icon="🌱", layout="centered")

# 初始化 Google Sheets 连接
conn = st.connection("gsheets", type=GSheetsConnection)

# 配置 DeepSeek
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"], 
    base_url="https://api.deepseek.com"
)

# 账号数据库
USER_DATABASE = {
    "2026001": "pw123",
    "2026002": "pw456",
    "test": "test123"
}

# 数据保存函数
# --- 升级后的数据保存函数 ---
def save_to_cloud(student_id, user_msg, ai_msg, is_summary=False):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. 数字化预警逻辑：检测关键词
        danger_list = ["想死", "自杀", "跳楼", "不活了", "离开世界", "吃药"]
        risk_score = 0  # 默认为安全
        
        # 如果学生说的话里包含危险词，直接打 10 分
        if any(word in user_msg for word in danger_list):
            risk_score = 10
        
        # 2. 构建新行
        new_row = pd.DataFrame([{
            "datetime": now,
            "student_id": student_id,
            "user_input": user_msg if not is_summary else "--- 系统总结 ---",
            "ai_response": ai_msg,
            "risk_score": risk_score # 这里现在会显示 0 或 10
        }])
        
        # 3. 写入云端
        existing_data = conn.read(ttl=0)
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(data=updated_df)
    except Exception as e:
        st.sidebar.error(f"云端同步失败: {e}")

# --- 3. 登录界面 ---
st.title("🌱 中学生心情树洞")

if "student_id" not in st.session_state:
    st.info("欢迎来到心情树洞。请输入学号和密码以开始。")
    with st.form("login_box"):
        input_id = st.text_input("学号：", placeholder="例如：2026001")
        input_pw = st.text_input("密码：", type="password")
        submit_button = st.form_submit_button("登录进入系统")
        
        if submit_button:
            if input_id.strip() in USER_DATABASE and USER_DATABASE[input_id.strip()] == input_pw:
                st.session_state.student_id = input_id.strip()
                st.session_state.chat_count = 0
                st.session_state.can_exit = False
                st.session_state.messages = [
                    {"role": "system", "content": "你是一位专业的学校心理辅导员。任务：通过对话温和评估 PHQ-9。完成后结尾加 [COMPLETE]。"},
                    {"role": "assistant", "content": f"同学你好（学号：{input_id}）！我是你的 AI 心理伙伴。🌱\n你最近在学校过得怎么样？"}
                ]
                st.success("验证成功，正在进入...")
                st.rerun()
            else:
                st.error("❌ 学号或密码错误")
    st.stop()

# --- 4. 侧边栏 ---
with st.sidebar:
    st.success(f"当前登录：{st.session_state.student_id}")
    is_unlocked = st.session_state.get("can_exit", False)
    current_count = st.session_state.get("chat_count", 0)
    st.write(f"💬 已交流轮数: **{current_count}**")
    
    if not is_unlocked:
        st.info("💡 真实分享感受，可以帮助 AI 更快完成评估。")
        st.progress(min(current_count / 20, 0.9))
    else:
        st.success("✨ 评估已完成！")
        st.balloons()
        st.progress(1.0)
    
    st.divider()
    
    # 退出逻辑
    can_exit_now = is_unlocked or current_count >= 20
    
    if st.button("✅ 提交评估并退出", disabled=not can_exit_now):
        st.info("正在生成 PHQ-9 总结并同步云端...")
        eval_messages = st.session_state.messages + [
            {"role": "user", "content": "请根据以上对话给出 PHQ-9 总结。格式：{'score': 分数, 'level': '等级', 'reason': '简析'}"}
        ]
        try:
            eval_res = client.chat.completions.create(model="deepseek-chat", messages=eval_messages)
            summary = eval_res.choices[0].message.content
            save_to_cloud(st.session_state.student_id, "FINAL_SUMMARY", summary, is_summary=True)
            st.success("保存成功！")
        except Exception as e:
            st.error(f"保存失败: {e}")

        # 清空状态
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 5. 聊天界面 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

if prompt := st.chat_input("在这里说说你的心事..."):
    st.session_state.chat_count += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            completion = client.chat.completions.create(
                model="deepseek-chat", 
                messages=st.session_state.messages
            )
            res = completion.choices[0].message.content
            
            if "[COMPLETE]" in res:
                st.session_state.can_exit = True
                res = res.replace("[COMPLETE]", "")
            
            st.write(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
            
            # 实时同步每一轮对话到 Google Sheets
            save_to_cloud(st.session_state.student_id, prompt, res)
            
        except Exception as e:
            st.error(f"连接出错: {e}")
