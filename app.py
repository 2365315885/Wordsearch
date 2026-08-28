import streamlit as st
import json
import re
import google.generativeai as genai

# ================= 页面基础配置 =================
st.set_page_config(page_title="考研真题透视", page_icon="📖")
st.title("📖 考研英语真题透视 AI")
st.markdown("结合本地真题数据库与大模型，精准解析每个单词在真题中的具体考法。")

# ================= 侧边栏：API 密钥与配置 =================
with st.sidebar:
    st.header("⚙️ 系统配置")
    api_key = st.text_input("请输入 Gemini API Key", type="password")
    st.markdown("---")
    st.write("当前题库状态：测试版 (3条数据)")

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
    # 正则表达式：\b 匹配单词边界，防止 sub 匹配到 subject
    pattern = re.compile(rf'\b{word}\b', re.IGNORECASE)
    for item in data:
        if pattern.search(item['sentence']):
            results.append(item)
    return results

# ================= 主界面交互 =================
target_word = st.text_input("🔍 输入要查询的考研单词 (例如: subject)")

if st.button("透视真题考法"):
    if not target_word:
        st.warning("请先输入需要查询的单词。")
    elif not api_key:
        st.warning("请在左侧栏输入你的 Gemini API Key。")
    else:
        # --- 第一步：传统数据库精准检索 ---
        with st.spinner('正在真题库中检索原句...'):
            matched_results = search_word(target_word, exam_data)
        
        if not matched_results:
            st.info(f"在当前的题库中没有找到关于 '{target_word}' 的真题出处。")
        else:
            st.success(f"检索完毕！共找到 {len(matched_results)} 条原句。")
            
            # 整理检索结果并展示
            extracted_text = ""
            with st.expander("查看真题原句出处", expanded=False):
                for res in matched_results:
                    line = f"[{res['year']} {res['source']}] {res['sentence']}"
                    st.markdown(f"- {line}")
                    extracted_text += line + "\n"

            # --- 第二步：组装语料，交由大模型分析 ---
            with st.spinner('AI 正在深度解析真题考法，请稍候...'):
                genai.configure(api_key=api_key)
                # 使用较快的 flash 模型即可胜任阅读理解
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"""
                你是一个专业的考研英语分析专家。现在我要重点分析单词【{target_word}】。
                以下是这个单词在历年考研真题中的所有出处原句：
                {extracted_text}

                请根据以上【真实的真题语料】，进行归纳并输出：
                1. **考察释义**：该单词在真题中实际考察了哪些意思（请严格根据提供的原句进行总结）。
                2. **相关短语**：真题原句中出现了哪些由该单词构成的固定搭配或高频短语？
                3. **考察方式解析**：结合原句，分析出题人是怎么设置语境或长难句陷阱的（例如熟词僻义、指代题等），做题时应该如何应对？
                """
                
                try:
                    response = model.generate_content(prompt)
                    st.markdown("### 🧠 AI 考法解析")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"AI 解析失败，请检查 API Key 或网络连通性。错误信息: {e}")

