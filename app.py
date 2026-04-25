import sys
import io
import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
from datetime import datetime

# 1. 编码修复
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 2. 配置 ---
st.set_page_config(page_title="心情树洞", page_icon="🌱", layout="centered")

# 初始化 Supabase 连接 (3000人并发支持)
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# 配置 DeepSeek
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"], 
    base_url="https://api.deepseek.com"
)

# --- 3. 核心保存函数 (Supabase 版) ---
def save_to_db(student_id, user_msg, ai_msg, is_summary=False):
    try:
        # 数字化预警逻辑：检测关键词
        danger_list = ["想死", "自杀", "跳楼", "不活了", "离开世界", "吃药"]
        risk_score = 0
        
        # 如果是总结内容，不参与风险词检测，否则检测用户输入
        if not is_summary and any(word in user_msg for word in danger_list):
            risk_score = 10
        
        data = {
            "student_id": student_id,
            "user_input": user_msg if not is_summary else "--- 评估总结 ---",
            "ai_response": ai_msg,
            "risk_score": risk_score
        }
        # 插入 Supabase 数据库
        supabase.table("chat_logs").insert(data).execute()
    except Exception as e:
        st.sidebar.error(f"云端同步失败: {e}")

# --- 4. 登录界面 (增强兼容版) ---
if "student_id" not in st.session_state:
    st.title("🌱 中学生心情树洞")
    st.info("欢迎来到滨华中学心情树洞。请输入学号和密码以开始评估。")
    
    with st.form("login_box"):
        # 使用 .strip() 确保用户输入的学号前后没有意外空格
        input_id = st.text_input("学号：", placeholder="例如：2026001").strip()
        input_pw = st.text_input("密码：", type="password").strip()
        submit_button = st.form_submit_button("登录进入系统")
        
        if submit_button:
            if not input_id or not input_pw:
                st.warning("请完整填写学号和密码")
            else:
                with st.spinner("正在核对名单..."):
                    # 💡 尝试查询数据库
                    try:
                        # 核心修复：无论数据库里存的是数字还是文字，都尝试匹配
                        res = supabase.table("students").select("*").eq("student_id", input_id).execute()
                        
                        if res.data and len(res.data) > 0:
                            # 💡 再次增强兼容性：将库里的密码和输入的密码都转为字符串进行对比
                            db_pw = str(res.data[0]["password"]).strip()
                            
                            if db_pw == input_pw:
                                # 验证成功
                                st.session_state.student_id = input_id
                                st.session_state.chat_count = 0
                                st.session_state.can_exit = False
                                st.session_state.messages = [
                                    {"role": "system", "content": """你是一位专业的学校心理辅导员。
                                    你的任务：通过对话温和地评估 PHQ-9 的 9 个维度。
                                    重要规则：如果学生回答敷衍，请换种方式引导。完成后加 [COMPLETE]。"""},
                                    {"role": "assistant", "content": f"同学你好（学号：{input_id}）！我是你的 AI 心理伙伴。🌱\n今天的对话是为了了解你最近的心情和生活状态。我们先开始吧：你最近在学校过得怎么样？"}
                                ]
                                st.success("验证成功，正在进入...")
                                st.rerun()
                            else:
                                st.error("❌ 密码不匹配，请重新输入。")
                        else:
                            st.error("❌ 找不到该学号。请确保学号输入正确，或联系咨询处老师。")
                    except Exception as e:
                        st.error(f"数据库连接异常: {e}")
    st.stop()

# --- 5. 侧边栏：状态显示与评估总结 ---
with st.sidebar:
    st.success(f"当前登录：{st.session_state.student_id}")
    
    is_unlocked = st.session_state.get("can_exit", False)
    current_count = st.session_state.get("chat_count", 0)
    
    st.markdown("### 📝 对话指南")
    st.write(f"💬 已交流轮数: **{current_count}**")
    
    if not is_unlocked:
        st.info("💡 真实分享感受，可以帮助 AI 更快完成评估。")
        st.progress(min(current_count / 15, 0.95)) # 进度条显示
    else:
        st.success("✨ 评估信息已收集充分！")
        st.balloons()
        st.progress(1.0)
    
    st.divider()

    # 退出逻辑：AI 判定完成 OR 20 轮强制解锁
    can_exit_now = is_unlocked or current_count >= 20
    
    if st.button("✅ 提交评估并安全退出", disabled=not can_exit_now):
        st.info("正在生成 PHQ-9 心理状态总结并上传云端...")
        eval_messages = st.session_state.messages + [
            {"role": "user", "content": "请根据以上对话，参照 PHQ-9 标准（0-27分），给该学生的忧郁倾向打分。只需返回一个简洁的 JSON 格式：{'score': 分数, 'level': '等级', 'reason': '简短分析'}"}
        ]
        try:
            eval_res = client.chat.completions.create(model="deepseek-chat", messages=eval_messages)
            summary = eval_res.choices[0].message.content
            # 保存最终总结到 Supabase
            save_to_db(st.session_state.student_id, "FINAL_SUMMARY", summary, is_summary=True)
            st.success("保存成功！正在退出...")
        except Exception as e:
            st.warning(f"总结保存失败: {e}")

        # 清空状态并重启
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 6. 聊天界面 ---
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
            
            # 检查 AI 是否觉得信息采集足够
            if "[COMPLETE]" in res:
                st.session_state.can_exit = True
                res = res.replace("[COMPLETE]", "")
            
            st.write(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
            
            # 实时同步每一轮对话到 Supabase
            save_to_db(st.session_state.student_id, prompt, res)
            
        except Exception as e:
            st.error(f"连接出错: {e}")
