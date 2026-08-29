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
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("找不到 data.json，请确保真题语料文件在同一目录下。")
        return []

exam_data = load_data()

def get_word_variants(word, client):
    """利用大模型获取单词的所有变形（带思维链标签过滤与去重）"""
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
        raw_content = response.choices[0].message.content.strip()
        
        # 过滤 <think> 标签及非字母字符
        cleaned = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL)
        cleaned = re.sub(r'</?think>', '', cleaned)
        cleaned = re.sub(r'[^a-zA-Z|]', '', cleaned)
        
        variants_list = [v.strip() for v in cleaned.split('|') if v.strip()]
        if word.lower() not in [v.lower() for v in variants_list]:
            variants_list.append(word.strip())
            
        return "|".join(list(dict.fromkeys(variants_list)))
    except Exception:
        return word

def search_word_expanded(word_variants_str, data):
    """使用多重匹配正则表达式在本地库中精确搜索"""
    results = []
    try:
        pattern = re.compile(rf'\b({word_variants_str})\b', re.IGNORECASE)
    except re.error:
        pattern = re.compile(rf'\b{word_variants_str}\b', re.IGNORECASE)
        
    for item in data:
        if pattern.search(item.get('sentence', '')):
            results.append(item)
    return results

# ================= 初始化 Session State =================
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

# ================= 主界面交互逻辑 =================
target_word = st.text_input("🔍 输入要查询的考研单词 (例如: seek)")

if st.button("透视真题考法"):
    if not target_word.strip():
        st.warning("请先输入需要查询的单词。")
    elif not api_key:
        st.warning("请配置 SiliconFlow API Key。")
    else:
        client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
        
        # --- 步骤 0：词形动态扩展 ---
        with st.spinner('🤖 正在智能推演单词变形...'):
            variants_str = get_word_variants(target_word.strip(), client)

        # --- 步骤 1：本地真题库检索 ---
        with st.spinner('⚡ 正在真题库中扫荡原句...'):
            matched_results = search_word_expanded(variants_str, exam_data)
        
        if not matched_results:
            st.session_state.analysis_result = {
                "has_data": False,
                "target_word": target_word.strip(),
                "variants_str": variants_str
            }
        else:
            extracted_text = ""
            for res in matched_results:
                line = f"[{res.get('year', '')} {res.get('source', '')}] {res.get('sentence', '')}"
                extracted_text += line + "\n"

            # --- 步骤 2：调用大模型深度分析 ---
            with st.spinner('🧠 AI 正在深度解析真题考法，请稍候...'):
                prompt = f"""
你是一个专业的考研英语分析专家。现在我要重点分析单词【{target_word}】及其变形【{variants_str}】。
以下是它们在历年考研真题中的出处原句：
{extracted_text}

【处理要求】：
1. 若提供的原句中存在考场指令或排版残片，请自动忽略，仅依据语义完整的原句进行分析。
2. **考察释义**：归纳该单词在真题中实际考察的核心含义（标注年份）。
3. **相关短语**：提炼原句中出现的固定搭配或高频词组。
4. **考察方式解析**：结合真题语境，分析出题人在长难句或选项中设置的考查逻辑。
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
                    
                    ai_analysis = response.choices[0].message.content
                    
                    # 将完整结果存入 session_state 避免被下载重置
                    st.session_state.analysis_result = {
                        "has_data": True,
                        "target_word": target_word.strip(),
                        "variants_str": variants_str,
                        "matched_results": matched_results,
                        "extracted_text": extracted_text,
                        "ai_analysis": ai_analysis
                    }
                except Exception as e:
                    st.error(f"深度解析调用失败，错误信息: {e}")
                    st.session_state.analysis_result = None

# ================= 渲染结果区域（状态持久化） =================
if st.session_state.analysis_result:
    res = st.session_state.analysis_result
    st.caption(f"🔍 实际检索词根簇: `{res['variants_str']}`")
    
    if not res.get("has_data"):
        st.info(f"在当前的题库中没有找到关于 '{res['target_word']}' 及其变形的真题出处。")
    else:
        st.success(f"检索完毕！共找到 {len(res['matched_results'])} 条原句。")
        
        # 1. 原句展示
        with st.expander("查看真题原句出处", expanded=False):
            for item in res['matched_results']:
                line = f"[{item.get('year', '')} {item.get('source', '')}] {item.get('sentence', '')}"
                st.markdown(f"- {line}")
        
        # 2. 仅下载原句按钮
        sentences_note = f"【真题原句出处：{res['target_word']}】\n检索词根簇：{res['variants_str']}\n" + "="*40 + "\n\n" + res['extracted_text']
        st.download_button(
            label="💾 仅下载真题原句 (TXT)",
            data=sentences_note,
            file_name=f"{res['target_word']}_真题原句.txt",
            mime="text/plain",
            key="btn_download_sentences"
        )
        
        # 3. AI 深度解析展示
        st.markdown("### 🎯 真题考法深度解析")
        st.markdown(res['ai_analysis'])
        
        # 4. 仅下载解析按钮
        st.markdown("---")
        analysis_note = f"【真题考法深度解析：{res['target_word']}】\n" + "="*40 + "\n\n" + res['ai_analysis']
        st.download_button(
            label="💾 仅下载AI深度解析 (TXT)",
            data=analysis_note,
            file_name=f"{res['target_word']}_考法解析.txt",
            mime="text/plain",
            key="btn_download_analysis"
        )
