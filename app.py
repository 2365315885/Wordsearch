import streamlit as st
import json
import re
from openai import OpenAI

# ================= 页面基础配置 =================
st.set_page_config(page_title="考研真题透视", page_icon="📖")
st.title("📖 考研英语真题透视 (终极扩展版)")
st.markdown("结合本地真题数据库与 SiliconFlow 模型，精准解析单词及其**所有变形**在真题中的具体考法。")

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

# ================= 核心功能函数 =================

@st.cache_data
def load_data():
    """加载本地真题 JSON 数据"""
    try:
        # 这里默认读取 data.json，如果你合并了 PDF/Word 的数据，确保都存进了这个文件
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("找不到 data.json，请确保真题语料文件在同一目录下。")
        return []

exam_data = load_data()

def get_word_variants(word, client):
    """利用大模型获取单词的所有变形"""
    prompt = f"""
    请给出英语单词 "{word}" 的所有常见屈折变化形式（包括复数、过去式、过去分词、现在分词、第三人称单数等）。
    要求：只输出单词本身，用竖线 "|" 分隔。绝对不要输出任何标点符号、解释或其他多余文字。
    示例：输入 "make"，输出 "make|makes|made|making"
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V4-Flash",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        # 清理返回结果，去除可能包含的空格或换行
        variants = response.choices[0].message.content.strip()
        variants = re.sub(r'\s+', '', variants) 
        return variants
    except Exception as e:
        # 如果调用失败，保底返回原词
        return word

def search_word_expanded(word_variants_str, data):
    """使用包含多变形的正则表达式在本地库中精确搜索"""
    results = []
    # 构建多重匹配正则，例如 \b(subject|subjects|subjected)\b，忽略大小写
    try:
        pattern = re.compile(rf'\b({word_variants_str})\b', re.IGNORECASE)
    except re.error:
        # 如果 AI 返回了奇怪的符号导致正则崩溃，回退到普通匹配
        pattern = re.compile(rf'\b{word_variants_str}\b', re.IGNORECASE)
        
    for item in data:
        if pattern.search(item['sentence']):
            results.append(item)
    return results

# ================= 主界面交互逻辑 =================
target_word = st.text_input("🔍 输入要查询的考研单词 (例如: seek)")

if st.button("透视真题考法"):
    if not target_word.strip():
        st.warning("请先输入需要查询的单词。")
    elif not api_key:
        st.warning("请配置 SiliconFlow API Key。")
    else:
        # 初始化 API 客户端
        client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
        
        # --- 第 0 步：词形动态扩展 ---
        with st.spinner('🤖 正在智能推演单词变形...'):
            variants_str = get_word_variants(target_word.strip(), client)
            st.caption(f"🔍 实际检索词根簇: `{variants_str}`")

        # --- 第一步：传统数据库精准检索 ---
        with st.spinner('⚡ 正在真题库中扫荡原句...'):
            matched_results = search_word_expanded(variants_str, exam_data)
        
        if not matched_results:
            st.info(f"在当前的题库中没有找到关于 '{target_word}' 及其变形的真题出处。")
        else:
            st.success(f"检索完毕！共找到 {len(matched_results)} 条原句。")
            
            # 展示原句出处并拼装上下文
            extracted_text = ""
            with st.expander("查看真题原句出处", expanded=False):
                for res in matched_results:
                    line = f"[{res['year']} {res['source']}] {res['sentence']}"
                    st.markdown(f"- {line}")
                    extracted_text += line + "\n"

            # --- 第二步：组装 Prompt 并调用大模型深度分析 ---
            with st.spinner('🧠 AI 正在深度解析真题考法，请稍候...'):
                prompt = f"""
你是一个专业的考研英语分析专家。现在我要重点分析单词【{target_word}】及其变形【{variants_str}】。
以下是它们在历年考研真题中的所有出处原句：
{extracted_text}

请根据以上【真实的真题语料】，进行归纳并输出：
1. **考察释义**：该单词在真题中实际考察了哪些意思（请严格根据提供的原句进行总结，标明对应年份）。
2. **相关短语**：真题原句中出现了哪些由该单词构成的固定搭配或高频短语？
3. **考察方式解析**：结合原句，分析出题人是怎么设置语境或长难句陷阱的（例如熟词僻义、主被动转换、长定语干扰等），做题时应该如何应对？
"""
                try:
                    response = client.chat.completions.create(
                        model="deepseek-ai/DeepSeek-V4-Flash",
                        messages=[
                            {"role": "system", "content": "你是一个严谨的考研英语语料分析助手。"},
                            {"role": "user", "content": prompt}
                        ],
                        stream=False
                    )
                    
                    st.markdown("### 🎯 真题考法深度解析")
                    st.markdown(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"深度解析调用失败，错误信息: {e}")
