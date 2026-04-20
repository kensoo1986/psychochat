import sys
import io
import os
import streamlit as st
from openai import OpenAI
import pandas as pd
from datetime import datetime

# 1. 强制设置 UTF-8 编码，防止 Windows 环境下中文报错
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 配置 DeepSeek ---
client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

st.set_page_config(page_title="心情树洞", page_icon="🌱")

# --- 2. 账号数据库 (你可以在这里添加更多学生) ---
USER_DATABASE = {
    "2026001": "pw123",
    "2026002": "pw456",
    "2026003": "pw789",
    "test": "test123"
}

# --- 界面初始化 ---
st.title("🌱 中学生心情树洞")

# 检查登录状态
if "student_id" not in st.session_state:
    st.info("欢迎来到心情树洞。请输入学号和密码以开始你的心理健康评估。")
    
    # 学号和密码输入框
    input_id = st.text_input("请输入学号：", placeholder="例如：2026001")
    input_pw = st.text_input("请输入密码：", type="password", placeholder="请输入你的密码")
    
    if st.button("登录进入系统"):
        # 验证逻辑：学号必须在数据库中，且密码必须匹配
        if input_id.strip() in USER_DATABASE:
            if USER_DATABASE[input_id.strip()] == input_pw:
                st.session_state.student_id = input_id
                st.session_state.chat_count = 0  
                st.session_state.can_exit = False  
                
                # 初始化对话历史和引导词
                st.session_state.messages = [
                    {"role": "system", "content": """你是一位专业的学校心理辅导员。
                    你的任务：通过对话温和地评估 PHQ-9 的 9 个维度。
                    重要规则：如果学生回答敷衍，请换种方式引导。
                    当你认为已经收集到了足够的心理状态信息，请在回复的结尾加上特殊标记 [COMPLETE]。"""},
                    {"role": "assistant", "content": f"""同学你好（学号：{input_id}）！我是你的 AI 心理伙伴。🌱
今天的对话是为了了解你最近的心情和生活状态。

当左边的退出按钮解锁时，说明我们的评估已完成。通常需要认真交流 10 到 15 轮。
我们先开始吧：你最近在学校过得怎么样？"""}
                ]
                st.success("验证成功，正在进入...")
                st.rerun()
            else:
                st.error("❌ 密码错误，请检查后重试。")
        else:
            st.error("❌ 未找到该学号，请联系老师开通权限。")
            
    st.stop()

# --- 3. 对话界面 (登录后可见) ---

# 显示历史记录
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# 接收学生输入
if prompt := st.chat_input("在这里输入你想说的话..."):
    st.session_state.chat_count += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # 调用 DeepSeek API
    with st.chat_message("assistant"):
        try:
            completion = client.chat.completions.create(
                model="deepseek-chat",
                messages=st.session_state.messages,
            )
            full_response = completion.choices[0].message.content
            
            # 检查 AI 判定：是否信息采集足够
            if "[COMPLETE]" in full_response:
                st.session_state.can_exit = True
                full_response = full_response.replace("[COMPLETE]", "")
            
            st.write(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 保存对话记录
            chat_data = [
                {"Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Student_ID": st.session_state.student_id, "Role": "User", "Content": prompt},
                {"Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Student_ID": st.session_state.student_id, "Role": "Assistant", "Content": full_response}
            ]
            pd.DataFrame(chat_data).to_csv("results.csv", mode='a', header=not os.path.isfile("results.csv"), index=False, encoding='utf-8-sig')
            
        except Exception as e:
            st.error(f"连接出错: {e}")

# --- 4. 侧边栏动态引导与退出锁定 ---
with st.sidebar:
    st.success(f"当前登录：{st.session_state.student_id}")
    
    is_unlocked = st.session_state.get("can_exit", False)
    current_count = st.session_state.get("chat_count", 0)
    
    if not is_unlocked:
        st.markdown("### 📝 对话指南")
        st.write(f"💬 已交流轮数: **{current_count}**")
        st.info("💡 真实分享关于睡眠、情绪和精力的感受，可以帮助 AI 更快完成评估。")
        st.progress(min(current_count / 20, 0.9))
    else:
        st.success("✨ 评估信息已收集充分！")
        st.balloons()
        st.write("感谢配合！你现在可以点击下方按钮提交并退出了。")
        st.progress(1.0)
    
    st.divider()

    # 逻辑判断：AI 判定完成 OR 20 轮保底
    can_exit_now = is_unlocked or current_count >= 20
    
    if not can_exit_now:
        st.button("提交评估并安全退出", disabled=True)
    else:
        if st.button("✅ 进度已完成：点击提交并退出"):
            st.info("正在生成 PHQ-9 心理状态总结...")
            eval_messages = st.session_state.messages + [
                {"role": "user", "content": "请根据以上对话，参照 PHQ-9 标准（0-27分），给该学生的忧郁倾向打分。只需返回一个简洁的 JSON 格式：{'score': 分数, 'level': '等级', 'reason': '简短分析'}"}
            ]
            
            try:
                eval_res = client.chat.completions.create(model="deepseek-chat", messages=eval_messages)
                assessment_report = eval_res.choices[0].message.content
                
                pd.DataFrame([{
                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Student_ID": st.session_state.student_id,
                    "PHQ9_Result": assessment_report
                }]).to_csv("summary_results.csv", mode='a', header=not os.path.isfile("summary_results.csv"), index=False, encoding='utf-8-sig')
                st.success("保存成功！")
            except Exception as e:
                st.warning(f"总结保存失败: {e}")

            # 清空状态回到登录页
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
