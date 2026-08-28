import streamlit as st
import json
import re
from openai import OpenAI

# ================= 页面基础配置 =================
st.set_page_config(page_title="考研真题透视", page_icon="📖")
st.title("📖 考研英语真题透视 (SiliconFlow 版)")
st.markdown("结合本地真题数据库与 SiliconFlow 模型，精准解析每个单词在真题中的具体考法。")

# ================= 侧边栏：API 密钥与配置 =================
with st.sidebar:
    st.header("⚙️ 系统配置")
    
    # 尝试从 Streamlit Secrets 中读取
    api_key = st.secrets.get("SILICONFLOW_API_KEY", "")
    
    # 判断逻辑：如果 Secrets 里没有配置，才显示手动输入框
    if not api_key:
        api_key = st.text_input("请输入 SiliconFlow API Key", type="password")
        st.warning("👈 未检测到内置密钥，请手动输入")
    else:
        st.success("✅ 密钥已自动加载，无需输入！")
        
    st.markdown("---")
    st.caption("当前调用模型: `deepseek-ai/DeepSeek-V4-Flash`")


# ================= 核心逻辑：加载数据与检索 =================
@st.cache_data
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("找不到 data.json，请确保真题语料文件在同一目录下。")
        return []

exam_data = load_data()

def search_word(word, data):
    results = []
    # 正则表达式：\b 匹配单词边界
    pattern = re.compile(rf'\b{word}\b', re.IGNORECASE)
    for item in data:
        if pattern.search(item['sentence']):
            results.append(item)
    return results

# ================= 主界面交互 =================
target_word = st.text_input("🔍 输入要查询的考研单词 (例如: subject)")

if st.button("透视真题考法"):
    if not target_word.strip():
        st.warning("请先输入需要查询的单词。")
    elif not api_key.strip():
        st.warning("请在左侧栏输入你的 SiliconFlow API Key。")
    else:
        # 1. 本地真题检索
        with st.spinner('正在真题库中检索原句...'):
            matched_results = search_word(target_word.strip(), exam_data)
        
        if not matched_results:
            st.info(f"在当前的题库中没有找到关于 '{target_word}' 的真题出处。")
        else:
            st.success(f"检索完毕！共找到 {len(matched_results)} 条原句。")
            
            # 展示原句出处
            extracted_text = ""
            with st.expander("查看真题原句出处", expanded=False):
                for res in matched_results:
                    line = f"[{res['year']} {res['source']}] {res['sentence']}"
                    st.markdown(f"- {line}")
                    extracted_text += line + "\n"

            # 2. 组装 Prompt 并调用 SiliconFlow API
            with st.spinner('AI 正在深度解析真题考法，请稍候...'):
                prompt = f"""
你是一个专业的考研英语分析专家。现在我要重点分析单词【{target_word}】。
以下是这个单词在历年考研真题中的所有出处原句：
{extracted_text}

请根据以上【真实的真题语料】，进行归纳并输出：
1. **考察释义**：该单词在真题中实际考察了哪些意思（请严格根据提供的原句进行总结，标明对应年份）。
2. **相关短语**：真题原句中出现了哪些由该单词构成的固定搭配或高频短语？
3. **考察方式解析**：结合原句，分析出题人是怎么设置语境或长难句陷阱的（例如熟词僻义、主被动转换、长定语干扰等），做题时应该如何应对？
"""
                try:
                    # 连接硅基流动 API
                    client = OpenAI(
                        api_key=api_key,
                        base_url="https://api.siliconflow.cn/v1"
                    )
                    
                    response = client.chat.completions.create(
                        model="deepseek-ai/DeepSeek-V4-Flash",
                        messages=[
                            {"role": "system", "content": "你是一个严谨的考研英语语料分析助手。"},
                            {"role": "user", "content": prompt}
                        ],
                        stream=False
                    )
                    
                    st.markdown("### 🧠 真题考法深度解析")
                    st.markdown(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"调用失败，错误信息: {e}")

