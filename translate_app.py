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

def get_used_codes():
    user_data = load_user_data()
    used = []
    for user in user_data.values():
        used.extend(user.get("used_codes", []))
    return used

# ========== 会话状态初始化 ==========
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "is_vip" not in st.session_state:
    st.session_state.is_vip = False
if "vip_expire_time" not in st.session_state:
    st.session_state.vip_expire_time = datetime.now()
if "used_count" not in st.session_state:
    st.session_state.used_count = 0
if "today" not in st.session_state:
    st.session_state.today = datetime.now().date()

# 每日重置免费次数
current_date = datetime.now().date()
if current_date != st.session_state.today:
    st.session_state.used_count = 0
    st.session_state.today = current_date

# ========== 核心功能函数 ==========
def check_vip_valid():
    if not st.session_state.user_id:
        return False, "❌ 请先绑定手机号"
    user_data = load_user_data()
    if st.session_state.user_id not in user_data:
        return False, "❌ 未查询到会员信息"
    expire_str = user_data[st.session_state.user_id]["expire_time"]
    expire_time = datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    if now < expire_time:
        remain_days = (expire_time - now).days
        remain_hours = (expire_time - now).seconds // 3600
        st.session_state.is_vip = True
        st.session_state.vip_expire_time = expire_time
        return True, f"✅ 会员有效期至：{expire_str}（剩余{remain_days}天{remain_hours}小时）"
    else:
        st.session_state.is_vip = False
        return False, "❌ 会员已到期，请重新开通"

def bind_user(user_id):
    user_data = load_user_data()
    if user_id not in user_data:
        user_data[user_id] = {
            "expire_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "used_codes": []
        }
        save_user_data(user_data)
    st.session_state.user_id = user_id
    check_vip_valid()

def verify_vip_code(vip_code):
    if not st.session_state.user_id:
        return False, "❌ 请先绑定手机号"
    used_codes = get_used_codes()
    if vip_code not in CODE_DURATION_MAP:
        return False, "❌ 解锁码错误"
    if vip_code in used_codes:
        return False, "❌ 解锁码已被使用"
    
    add_days = CODE_DURATION_MAP[vip_code]
    user_data = load_user_data()
    user_info = user_data[st.session_state.user_id]
    expire_time = datetime.strptime(user_info["expire_time"], "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    
    if expire_time > now:
        new_expire = expire_time + timedelta(days=add_days)
    else:
        new_expire = now + timedelta(days=add_days)
    
    user_info["expire_time"] = new_expire.strftime("%Y-%m-%d %H:%M:%S")
    user_info["used_codes"].append(vip_code)
    save_user_data(user_data)
    
    st.session_state.vip_expire_time = new_expire
    st.session_state.is_vip = True
    return True, f"✅ 解锁成功！会员时长增加{add_days}天，有效期至：{new_expire.strftime('%Y-%m-%d %H:%M:%S')}"

def check_permission(comment_num):
    if st.session_state.user_id:
        vip_valid, vip_msg = check_vip_valid()
        if vip_valid:
            return True, vip_msg
    remaining = 50 - st.session_state.used_count
    if comment_num > remaining:
        return False, f"❌ 免费用户每日限50条，今日剩余 {remaining} 条，请升级会员解锁"
    else:
        st.session_state.used_count += comment_num
        return True, f"✅ 今日已使用 {st.session_state.used_count}/50 条"

def baidu_translate(query):
    if not query:
        return ""
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    salt = str(random.randint(32768, 65536))
    sign_str = APP_ID + query + salt + SECRET_KEY
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    params = {
        "q": query, "from": "en", "to": "zh",
        "appid": APP_ID, "salt": salt, "sign": sign
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        result = res.json()
        return result["trans_result"][0]["dst"] if "trans_result" in result else f"翻译失败：{result.get('error_msg', '未知错误')}"
    except Exception as e:
        return f"请求异常：{str(e)}"

def classify_comment(text):
    positive_words = ["good", "nice", "excellent", "perfect", "great", "love", "best", "satisfied", "recommend"]
    negative_words = ["bad", "terrible", "worse", "poor", "broken", "slow", "disappointed", "defective", "waste"]
    text_lower = text.lower()
    if any(word in text_lower for word in positive_words):
        return "好评"
    elif any(word in text_lower for word in negative_words):
        return "差评"
    else:
        return "中性"

def extract_negative_keywords(bad_comments, top_n=5):
    stop_words = ["the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "i", "you", "it", "this", "that"]
    pattern = re.compile(r'\b[a-zA-Z]+\b')
    all_words = []
    for comment in bad_comments:
        words = pattern.findall(comment.lower())
        all_words.extend([w for w in words if w not in stop_words and len(w) > 2])
    return Counter(all_words).most_common(top_n)

# ========== 网页界面搭建 ==========
st.title("跨境电商评论翻译工具")

with st.expander("📖 操作指南（点击展开）", expanded=False):
    st.markdown("""
    1.  先绑定**11位手机号**作为用户标识（换设备找回会员靠它）
    2.  免费用户每日限50条，会员无限制，支持时长叠加
    3.  支持 Excel/CSV 上传或手动粘贴评论，一键翻译+分类+关键词提取
    """)

# ========== 侧边栏：用户绑定+会员中心 ==========
st.sidebar.title("🔑 用户中心")

# 手机号格式验证绑定
user_id_input = st.sidebar.text_input("输入11位手机号绑定", placeholder="例如：13800138000")
if st.sidebar.button("绑定/登录"):
    user_id = user_id_input.strip()
    if len(user_id) == 11 and user_id.isdigit():
        bind_user(user_id)
        st.sidebar.success(f"✅ 已绑定：{user_id}")
    else:
        st.sidebar.error("❌ 请输入11位有效手机号！")

# 会员状态显示
if st.session_state.user_id:
    vip_valid, vip_msg = check_vip_valid()
    st.sidebar.markdown(vip_msg)
else:
    st.sidebar.markdown("❌ 未绑定手机号，仅可使用免费额度")

# 解锁码验证
st.sidebar.markdown("---")
vip_code = st.sidebar.text_input("输入会员解锁码", type="password")
if st.sidebar.button("验证解锁"):
    res, msg = verify_vip_code(vip_code)
    st.sidebar.markdown(msg)

# 会员套餐
st.sidebar.markdown("---")
st.sidebar.markdown("### 🛒 开通会员（微信支付）")
st.sidebar.markdown("""
- **体验卡：19元** | 7天无限制
- **月卡：49元** | 30天无限制
- **年卡：399元** | 365天无限制
""")
st.sidebar.markdown("#### 📸 扫码付款")
st.sidebar.markdown("请联系客服获取收款码：(微信:wxid_6hmb7mxw32t112)")

# ========== 主功能区 ==========
st.subheader("支持 Excel/CSV 批量导入 + 手动粘贴 + 自动分类")
tab1, tab2 = st.tabs(["📁 文件上传", "✏️ 手动粘贴"])

with tab1:
    uploaded_file = st.file_uploader("上传评论文件（Excel/CSV）", type=["xlsx", "csv"])
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
        comment_col = st.selectbox("选择评论列", df.columns)
        df.rename(columns={comment_col: "评论"}, inplace=True)
        comment_num = len(df)
        
        has_permission, msg = check_permission(comment_num)
        if has_permission:
            with st.spinner("处理中..."):
                df["中文翻译"] = df["评论"].apply(baidu_translate)
                df["评论分类"] = df["评论"].apply(classify_comment)
                bad_comments = df[df["评论分类"] == "差评"]["评论"].tolist()
                negative_keywords = extract_negative_keywords(bad_comments)
            
            st.success(msg)
            st.dataframe(df[["评论", "中文翻译", "评论分类"]])
            
            if negative_keywords:
                st.write("### 🔍 差评高频关键词 Top5")
                for word, count in negative_keywords:
                    st.write(f"- **{word}**: {count} 次")
            else:
                st.info("暂无差评数据")
            
            output = BytesIO()
            df[["评论", "中文翻译", "评论分类"]].to_excel(output, index=False, engine="openpyxl")
            output.seek(0)
            st.download_button("下载结果（Excel）", data=output, file_name="翻译分类结果.xlsx")
        else:
            st.warning(msg)

with tab2:
    input_text = st.text_area("粘贴评论（一行一条）", height=200, placeholder="Good product!\nTerrible quality!")
    if st.button("开始处理", type="primary"):
        if not input_text.strip():
            st.error("请输入评论内容！")
        else:
            comments = [line.strip() for line in input_text.strip().split("\n") if line.strip()]
            comment_num = len(comments)
            has_permission, msg = check_permission(comment_num)
            if has_permission:
                df_manual = pd.DataFrame({"评论": comments})
                with st.spinner("处理中..."):
                    df_manual["中文翻译"] = df_manual["评论"].apply(baidu_translate)
                    df_manual["评论分类"] = df_manual["评论"].apply(classify_comment)
                    bad_comments_manual = df_manual[df_manual["评论分类"] == "差评"]["评论"].tolist()
                    negative_keywords_manual = extract_negative_keywords(bad_comments_manual)
                
                st.success(msg)
                st.dataframe(df_manual)
                
                if negative_keywords_manual:
                    st.write("### 🔍 差评高频关键词 Top5")
                    for word, count in negative_keywords_manual:
                        st.write(f"- **{word}**: {count} 次")
                else:
                    st.info("暂无差评数据")
                
                output_manual = BytesIO()
                df_manual.to_excel(output_manual, index=False, engine="openpyxl")
                output_manual.seek(0)
                st.download_button("下载结果（Excel）", data=output_manual, file_name="手动输入翻译结果.xlsx")
            else:
                st.warning(msg)
