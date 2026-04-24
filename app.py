import sys
import io
import os
import streamlit as st
from openai import OpenAI
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 强制设置 UTF-8 编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 2. 基础配置与连接 ---
st.set_page_config(page_title="中学生心情树洞", page_icon="🌱", layout="centered")

# 初始化 Google Sheets 连接
conn = st.connection("gsheets", type=GSheetsConnection)

# 配置 DeepSeek 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"], 
    base_url="https://api.deepseek.com"
)

# --- 3. 账号数据库 ---
USER_DATABASE = {
    "2026001": "pw123",
    "2026002": "pw456",
    "2026003": "pw789",
    "test": "test123"
}

# --- 4. 数据保存函数 (写入 Google Sheets) ---
def save_to_cloud(student_id, user_msg, ai_msg, risk_score="N/A", is_summary=False):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 构建新行
        new_row = pd.DataFrame([{
            "datetime": now,
            "student_id": student_id,
            "user_input": user_msg if not is_summary else "--- 系统总结 ---",
            "ai_response": ai_msg,
            "risk_score": risk_score
        }])
        # 读取并追加
        existing_data = conn.read(ttl=0)
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        # 写回云端
        conn.update(data=updated_df)
    except Exception as e:
        st.sidebar.error(f"云端同步失败: {e}")

# --- 5. 登录界面 ---
st.title("🌱 中学生心情树洞")

if "student_id" not in st.session_state:
    st.info("欢迎来到心情树洞。请输入学号和密码以开始你的心理健康评估。")
    
    input_id = st.text_input("请输入学号：", placeholder="例如：2026001")
    input_pw = st.text_input("请输入密码：", type="password")
    
    if st.button("登录进入系统"):
        if input_id.strip() in USER_DATABASE and USER_DATABASE[input_id.strip()] == input_pw:
            st.session_state.student_id = input_id
            st.session_state.chat_count = 0
            st.session_state.can_exit = False
            st.session_state.messages = [
                {"role": "system", "content": """你是一位专业的学校心理辅导员。
                你的任务：通过对话温和地评估 PHQ-9 的 9 个维度。
                重要规则：如果学生回答敷衍，请换种方式引导。
                当你认为已经收集到了足够的心理状态信息，请在回复的结尾加上特殊标记 [COMPLETE]。"""},
                {"role": "assistant", "content": f"同学你好（学号：{input_id}）！我是你的 AI 心理伙伴。🌱\n今天的对话是为了了解你最近的心情和生活状态。\n\n当左边的退出按钮解锁时，说明我们的评估已完成。通常需要认真交流 10 到 15 轮。\n我们先开始吧：你最近在学校过得怎么样？"}
            ]
            st.success("验证成功，正在进入...")
            st.rerun()
        else:
            st.error("❌ 学号或密码错误。")
    st.stop()

# --- 6. 侧边栏：对话指南与退出逻辑 ---
with st.sidebar:
    st.success(f"当前登录：{st.session_state.student_id}")
    
    is_unlocked = st.session_state.get("can_exit", False)
    current_count = st.session_state.get("chat_count", 0)
    
    st.markdown("### 📝 对话指南")
    st.write(f"💬 已交流轮数: **{current_count}**")
    
    if not is_unlocked:
        st.info("💡 真实分享感受，可以帮助 AI 更快完成评估。")
        st.progress(min(current_count / 20, 0.9))
    else:
        st.success("✨ 评估信息已收集充分！")
        st.balloons()
        st.progress(1.0)
    
    st.divider()

    # 退出逻辑：AI判定完成 或 满20轮
    can_exit_now = is_unlocked or current_count >= 20
    
    if not can_exit_now:
        st.button("提交评估并安全退出", disabled=True, help="请继续对话以解锁退出")
    else:
        if st.button("✅ 进度已完成：点击提交并退出"):
            st.info("正在生成 PHQ-9 心理状态总结并上传云端...")
            eval_messages = st.session_state.messages + [
                {"role": "user", "content": "请根据以上对话，参照 PHQ-9 标准（0-27分），给该学生的忧郁倾向打分。只需返回一个简洁的 JSON 格式：{'score': 分数, 'level': '等级', 'reason': '简短分析'}"}
            ]
            try:
                eval_res = client.chat.completions.create(model="deepseek-chat", messages=eval_messages)
                assessment_report = eval_res.choices[0].message.content
                # 将最终总结存入 Google Sheets
                save_to_cloud(st.session_state.student_id, "FINAL_SUMMARY", assessment_report, is_summary=True)
                st.success("总结已成功存入云端数据库！")
            except Exception as e:
                st.error(f"总结上传失败: {e}")

            # 清空并返回登录
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- 7. 对话界面 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

if prompt := st.chat_input("在这里输入你想说的话..."):
    st.session_state.chat_count += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            completion = client.chat.completions.create(
                model="deepseek-chat",
                messages=st.session_state.messages,
            )
            full_response = completion.choices[0].message.content
            
            # 逻辑：检查是否完成采集
            if "[COMPLETE]" in full_response:
                st.session_state.can_exit = True
                full_response = full_response.replace("[COMPLETE]", "")
            
            st.write(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 【核心升级】每轮对话实时存入 Google Sheets
            save_to_cloud(st.session_state.student_id, prompt, full_response)
            
        except Exception as e:
            st.error(f"连接出错: {e}")
