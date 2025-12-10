import streamlit as st
import pandas as pd
import hashlib
import random
import requests
from io import BytesIO
from collections import Counter
import re
from datetime import datetime, timedelta
import json
import os
import socket

# 百度翻译 API 配置
APP_ID = st.secrets["APP_ID"]
SECRET_KEY = st.secrets["SECRET_KEY"]

# ========== 本地数据持久化核心配置 ==========
USER_DATA_FILE = "vip_users.json"

def init_user_data():
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_user_data():
    init_user_data()
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user_data(user_data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=4)

# 获取用户IP（作为免费用户唯一标识）
def get_user_ip():
    try:
        # Streamlit Cloud 获取客户端IP
        ip = st.connection_state.client_ip
    except:
        # 本地运行时的兜底方案
        ip = socket.gethostbyname(socket.gethostname())
    return f"免费用户-{ip}"

# 解锁码对应时长配置
CODE_DURATION_MAP = {
    # 体验卡（19元/7天）
    "8A9B7C6D5E4F3G2H": 7, "7F8E9D0C1B2A3Z4Y": 7, "6Y5X4W3V2U1T0S9R": 7,
    "5R4S3T2U1V0W9X8Y": 7, "4H3G2F1E0D9C8B7A": 7, "3A2B1C0D9E8F7G6H": 7,
    "2H1G0F9E8D7C6B5A": 7, "1A0B9C8D7E6F5G4H": 7, "9H8G7F6E5D4C3B2A": 7,
    "8B7A6Z5Y4X3W2V1U": 7, "7U6V5W4X3Y2Z1A0B": 7, "6B0A1Z2Y3X4W5V6U": 7,
    "5U5V4W3X2Y1Z0A9B": 7, "4B9A8Z7Y6X5W4V3U": 7, "3U3V2W1X0Y9Z8A7B": 7,
    "2B7A8Z9Y0X1W2V3U": 7, "1U1V0W9X8Y7Z6A5B": 7, "0B5A6Z7Y8X9W0V1U": 7,
    "9U9V8W7X6Y5Z4A3B": 7, "8B3A4Z5Y6X7W8V9U": 7,
    # 月卡（49元/30天）
    "5X6W7V8U9T0S1R2Q": 30, "4Q3R2S1T0U9V8W7X": 30, "3X7W8V9U0T1S2R3Q": 30,
    "2Q2R3S4T5U6V7W8X": 30, "1X8W9V0U1T2S3R4Q": 30, "0Q4R5S6T7U8V9W0X": 30,
    "9X0W1V2U3T4S5R6Q": 30, "8Q6R7S8T9U0V1W2X": 30, "7X2W3V4U5T6S7R8Q": 30,
    "6Q8R9S0T1U2V3W4X": 30, "5X4W5V6U7T8S9R0Q": 30, "4Q0R1S2T3U4V5W6X": 30,
    "3X6W7V8U9T0S1R2Q": 30, "2Q2R3S4T5U6V7W8X": 30, "1X8W9V0U1T2S3R4Q": 30,
    "0Q4R5S6T7U8V9W0X": 30, "9X0W1V2U3T4S5R6Q": 30, "8Q6R7S8T9U0V1W2X": 30,
    "7X2W3V4U5T6S7R8Q": 30, "6Q8R9S0T1U2V3W4X": 30,
    # 年卡（399元/365天）
    "9Z8Y7X6W5V4U3T2S": 365, "8S2T3U4V5W6X7Y8Z": 365, "7Z6Y5X4W3V2U1T0S": 365,
    "6S0T1U2V3W4X5Y6Z": 365, "5Z4Y3X2W1V0U9T8S": 365, "4S8T9U0V1W2X3Y4Z": 365,
    "3Z2Y1X0W9V8U7T6S": 365, "2S6T7U8V9W0X1Y2Z": 365, "1Z0Y9X8W7V6U5T4S": 365,
    "1S4T5U6V7W8X9Y0Z": 365
}

# ========== 核心功能函数 ==========
def check_vip_valid(user_id):
    """检查会员是否有效（兼容手机号/IP标识）"""
    if not user_id:
        return False, "❌ 未识别到用户标识"
    user_data = load_user_data()
    if user_id not in user_data:
        return False, "❌ 未查询到会员信息"
    
    user_info = user_data[user_id]
    if "expire_time" not in user_info:
        return False, "❌ 会员信息异常"
    
    expire_str = user_info["expire_time"]
    expire_time = datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    
    if now < expire_time:
        remain_days = (expire_time - now).days
        remain_hours = (expire_time - now).seconds // 3600
        return True, f"✅ 会员有效期至：{expire_str}（剩余{remain_days}天{remain_hours}小时）"
    else:
        return False, "❌ 会员已到期，请重新开通"

def bind_user(user_id):
    """绑定手机号（仅11位数字）"""
    user_data = load_user_data()
    if user_id not in user_data:
        user_data[user_id] = {
            "expire_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "used_count": 0,
            "last_date": datetime.now().strftime("%Y-%m-%d"),
            "used_codes": []
        }
    save_user_data(user_data)
    st.session_state.user_id = user_id

def update_free_user_usage(user_id, add_count=1):
    """更新免费用户当日使用次数（持久化）"""
    user_data = load_user_data()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 初始化免费用户记录
    if user_id not in user_data:
        user_data[user_id] = {
            "expire_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "used_count": 0,
            "last_date": today,
            "used_codes": []
        }
    
    user_info = user_data[user_id]
    # 跨天重置次数
    if user_info["last_date"] != today:
        user_info["used_count"] = 0
        user_info["last_date"] = today
    
    # 更新使用次数
    user_info["used_count"] += add_count
    save_user_data(user_data)
    return user_info["used_count"]

def get_free_user_usage(user_id):
    """获取免费用户当日已用次数"""
    user_data = load_user_data()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_id not in user_data:
        return 0
    
    user_info = user_data[user_id]
    # 跨天重置
    if user_info["last_date"] != today:
        return 0
    return user_info["used_count"]

def verify_vip_code(user_id, vip_code):
    """验证解锁码并延长会员时长"""
    if not user_id:
        return False, "❌ 请先绑定手机号"
    
    user_data = load_user_data()
    used_codes = []
    # 收集所有已使用的解锁码
    for u in user_data.values():
        if "used_codes" in u:
            used_codes.extend(u["used_codes"])
    
    if vip_code not in CODE_DURATION_MAP:
        return False, "❌ 解锁码错误"
    if vip_code in used_codes:
        return False, "❌ 解锁码已被使用"
    
    # 计算新的到期时间
    add_days = CODE_DURATION_MAP[vip_code]
    user_info = user_data.get(user_id, {})
    
    if "expire_time" in user_info and datetime.strptime(user_info["expire_time"], "%Y-%m-%d %H:%M:%S") > datetime.now():
        expire_time = datetime.strptime(user_info["expire_time"], "%Y-%m-%d %H:%M:%S") + timedelta(days=add_days)
    else:
        expire_time = datetime.now() + timedelta(days=add_days)
    
    # 更新用户信息
    if user_id not in user_data:
        user_data[user_id] = {
            "expire_time": expire_time.strftime("%Y-%m-%d %H:%M:%S"),
            "used_count": 0,
            "last_date": datetime.now().strftime("%Y-%m-%d"),
            "used_codes": []
        }
    else:
        user_data[user_id]["expire_time"] = expire_time.strftime("%Y-%m-%d %H:%M:%S")
    
    user_data[user_id]["used_codes"].append(vip_code)
    save_user_data(user_data)
    
    return True, f"✅ 解锁成功！会员时长增加{add_days}天，有效期至：{expire_time.strftime('%Y-%m-%d %H:%M:%S')}"

def check_permission(user_id, is_vip_user, comment_num):
    """检查使用权限（会员无限/免费用户50条上限，持久化）"""
    # 会员用户直接放行
    if is_vip_user:
        return True, "✅ 会员用户，无使用次数限制"
    
    # 免费用户检查当日次数（持久化）
    today_used = get_free_user_usage(user_id)
    remain = 50 - today_used
    
    if today_used + comment_num > 50:
        return False, f"❌ 免费用户当日剩余次数不足！今日已用{today_used}条，剩余{remain}条，本次需使用{comment_num}条"
    
    # 更新使用次数
    update_free_user_usage(user_id, comment_num)
    new_used = today_used + comment_num
    return True, f"✅ 免费用户使用成功！今日已用{new_used}/50条，剩余{50 - new_used}条"

def baidu_translate(query):
    """百度翻译接口"""
    if not query:
        return ""
    try:
        salt = str(random.randint(32768, 65536))
        sign = hashlib.md5((APP_ID + query + salt + SECRET_KEY).encode()).hexdigest()
        url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
        params = {
            "q": query,
            "from": "en",
            "to": "zh",
            "appid": APP_ID,
            "salt": salt,
            "sign": sign
        }
        res = requests.get(url, params=params, timeout=10)
        result = res.json()
        if "trans_result" in result:
            return result["trans_result"][0]["dst"]
        return f"翻译失败：{result.get('error_msg', '未知错误')}"
    except Exception as e:
        return f"翻译异常：{str(e)}"

def classify_comment(text):
    """评论情感分类（简单关键词匹配）"""
    positive_words = ["good", "nice", "excellent", "perfect", "great", "love", "best", "satisfied", "recommend"]
    negative_words = ["bad", "terrible", "worse", "poor", "broken", "slow", "disappointed", "defective", "waste"]
    
    text_lower = text.lower()
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    
    if pos_count > neg_count:
        return "好评"
    elif neg_count > pos_count:
        return "差评"
    else:
        return "中性"

def extract_negative_keywords(bad_comments, top_n=5):
    """提取差评关键词"""
    stop_words = ["the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "i", "you", "it", "this", "that"]
    all_words = []
    for comment in bad_comments:
        words = re.findall(r'\b[a-zA-Z]+\b', comment.lower())
        all_words.extend([w for w in words if w not in stop_words and len(w) > 2])
    return Counter(all_words).most_common(top_n)

# ========== 页面初始化 ==========
st.set_page_config(page_title="跨境电商评论翻译工具", page_icon="🌐", layout="wide")
st.title("🌐 跨境电商评论翻译工具")

# 获取用户标识（会员用手机号，免费用户用IP）
user_ip = get_user_ip()
st.session_state.setdefault("user_id", "")
current_user_id = st.session_state.user_id if st.session_state.user_id else user_ip

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("🔑 用户中心")
    
    # 手机号绑定（11位数字验证）
    phone_input = st.text_input("输入11位手机号绑定会员", placeholder="例如：13800138000")
    if st.button("绑定/登录"):
        phone = phone_input.strip()
        if len(phone) == 11 and phone.isdigit():
            bind_user(phone)
            st.success(f"✅ 已绑定：{phone}")
            current_user_id = phone
        else:
            st.error("❌ 请输入11位有效手机号！")
    
    # 会员状态检查
    if st.session_state.user_id:
        is_vip, vip_msg = check_vip_valid(st.session_state.user_id)
        st.markdown(vip_msg)
    else:
        st.markdown("⚠️ 未绑定手机号，当前为免费用户（每日50条上限）")
        is_vip = False
    
    # 解锁码验证
    st.divider()
    vip_code = st.text_input("输入会员解锁码", type="password")
    if st.button("验证解锁码"):
        if st.session_state.user_id:
            success, msg = verify_vip_code(st.session_state.user_id, vip_code)
            if success:
                st.success(msg)
                # 刷新会员状态
                is_vip, vip_msg = check_vip_valid(st.session_state.user_id)
            else:
                st.error(msg)
        else:
            st.error("❌ 请先绑定手机号再验证解锁码！")
    
    # 会员套餐说明
    st.divider()
    st.subheader("🛒 开通会员")
    st.markdown("""
    - **体验卡：19元** | 7天无限制使用
    - **月卡：49元** | 30天无限制使用
    - **年卡：399元** | 365天无限制使用
    """)
    st.markdown("📞 联系客服：微信号（wxid_6hmb7mxw32t112）")

# ========== 主功能区 ==========
tab1, tab2 = st.tabs(["📁 文件上传翻译", "✏️ 手动输入翻译"])

with tab1:
    st.subheader("Excel/CSV文件上传")
    uploaded_file = st.file_uploader("选择文件（支持.xlsx/.csv）", type=["xlsx", "csv"])
    
    if uploaded_file:
        # 读取文件
        try:
            if uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            # 检查是否有"评论"列
            if "评论" not in df.columns:
                st.error("❌ 文件中未找到「评论」列，请确保列名正确")
            else:
                comment_list = df["评论"].dropna().tolist()
                comment_num = len(comment_list)
                
                # 检查使用权限
                permission, perm_msg = check_permission(current_user_id, is_vip, comment_num)
                st.info(perm_msg)
                
                if permission:
                    # 翻译和分类
                    with st.spinner("正在翻译和分类..."):
                        df["中文翻译"] = df["评论"].apply(baidu_translate)
                        df["评论分类"] = df["评论"].apply(classify_comment)
                    
                    # 显示结果
                    st.dataframe(df[["评论", "中文翻译", "评论分类"]], use_container_width=True)
                    
                    # 提取差评关键词
                    bad_comments = df[df["评论分类"] == "差评"]["评论"].tolist()
                    if bad_comments:
                        st.subheader("🔍 差评高频关键词")
                        keywords = extract_negative_keywords(bad_comments)
                        for word, count in keywords:
                            st.markdown(f"- {word}：{count}次")
                    
                    # 导出Excel
                    output = BytesIO()
                    df[["评论", "中文翻译", "评论分类"]].to_excel(output, index=False, engine="openpyxl")
                    output.seek(0)
                    st.download_button(
                        label="📥 下载翻译结果",
                        data=output,
                        file_name=f"评论翻译结果_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        except Exception as e:
            st.error(f"❌ 文件处理失败：{str(e)}")

with tab2:
    st.subheader("手动输入评论翻译")
    input_text = st.text_area("输入评论（一行一条）", height=200, placeholder="例如：\nGood product!\nTerrible quality!")
    
    if st.button("开始翻译"):
        if input_text.strip():
            comment_list = [line.strip() for line in input_text.split("\n") if line.strip()]
            comment_num = len(comment_list)
            
            # 检查使用权限
            permission, perm_msg = check_permission(current_user_id, is_vip, comment_num)
            st.info(perm_msg)
            
            if permission:
                # 翻译和分类
                with st.spinner("正在翻译和分类..."):
                    result = []
                    for comment in comment_list:
                        trans = baidu_translate(comment)
                        cls = classify_comment(comment)
                        result.append({"评论": comment, "中文翻译": trans, "评论分类": cls})
                    df = pd.DataFrame(result)
                
                # 显示结果
                st.dataframe(df, use_container_width=True)
                
                # 提取差评关键词
                bad_comments = df[df["评论分类"] == "差评"]["评论"].tolist()
                if bad_comments:
                    st.subheader("🔍 差评高频关键词")
                    keywords = extract_negative_keywords(bad_comments)
                    for word, count in keywords:
                        st.markdown(f"- {word}：{count}次")
                
                # 导出Excel
                output = BytesIO()
                df.to_excel(output, index=False, engine="openpyxl")
                output.seek(0)
                st.download_button(
                    label="📥 下载翻译结果",
                    data=output,
                    file_name=f"手动翻译结果_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.warning("❌ 请输入需要翻译的评论！")
