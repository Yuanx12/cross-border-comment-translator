import streamlit as st
import pandas as pd
import hashlib
import random
import requests
from io import BytesIO  # 新增：用于处理Excel字节流

# 百度翻译 API 配置
APP_ID = '20251211002516789'  # 替换成你的 AppID
SECRET_KEY = 't75Q_utkDoU30xYQsbPb'  # 替换成你的密钥

def baidu_translate(query):
    """英译中函数，带异常处理"""
    if not query:
        return ""
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    salt = str(random.randint(32768, 65536))
    sign_str = APP_ID + query + salt + SECRET_KEY
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    params = {
        "q": query,
        "from": "en",
        "to": "zh",
        "appid": APP_ID,
        "salt": salt,
        "sign": sign
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        result = res.json()
        if "trans_result" in result:
            return result["trans_result"][0]["dst"]
        else:
            return f"翻译失败：{result.get('error_msg', '未知错误')}"
    except Exception as e:
        return f"请求异常：{str(e)}"

def classify_comment(text):
    """评论自动分类：好评/中性/差评（关键词匹配）"""
    positive_words = ["good", "nice", "excellent", "perfect", "great", "love", "best"]
    negative_words = ["bad", "terrible", "worse", "poor", "broken", "slow", "disappointed"]
    text_lower = text.lower()
    if any(word in text_lower for word in positive_words):
        return "好评"
    elif any(word in text_lower for word in negative_words):
        return "差评"
    else:
        return "中性"

# 网页界面搭建
st.title("跨境电商评论翻译工具")
st.subheader("支持 Excel/CSV 批量导入+自动分类")

# 上传文件
uploaded_file = st.file_uploader("上传评论文件（Excel/CSV）", type=["xlsx", "csv"])
if uploaded_file is not None:
    # 读取文件
    if uploaded_file.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)
    
    # 检查是否有"评论"列
    if "评论" not in df.columns:
        st.error("文件必须包含名为【评论】的列！")
    else:
        with st.spinner("正在翻译和分类..."):
            # 批量处理
            df["中文翻译"] = df["评论"].apply(baidu_translate)
            df["评论分类"] = df["评论"].apply(classify_comment)
        
        # 显示结果
        st.success("处理完成！")
        st.dataframe(df)
        
        # 导出结果（修复to_excel报错）
        output_df = df[["评论", "中文翻译", "评论分类"]]
        output = BytesIO()  # 创建内存字节流
        output_df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)  # 重置字节流指针到开头
        
        st.download_button(
            label="下载结果（Excel）",
            data=output,
            file_name="翻译分类结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
