import streamlit as st
import json
import re
from openai import OpenAI

# ================= 页面基础配置 =================
st.set_page_config(page_title="考研真题透视", page_icon="📖")
st.title("📖 考研英语真题透视 (流式终极版)")
st.markdown("结合本地真题数据库与 SiliconFlow 模型，精准解析单词及其**所有变形**在真题中的具体考法。")

# ================= 侧边栏：API 密钥与配置 =================
with st.sidebar:
    st.header("⚙️ 系统配置")
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
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("找不到 data.json，请确保真题语料文件在同一目录下。")
        return []

exam_data = load_data()

def get_word_variants(word, client):
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
    results = []
    try:
        pattern = re.compile(rf'\b({word_variants_str})\b', re.IGNORECASE)
    except re.error:
        pattern = re.compile(rf'\b{word_variants_str}\b', re.IGNORECASE)
        
    for item in data:
        if pattern.search(item.get('sentence', '')):
            results.append(item)
    return results

# ================= 初始化系统状态 =================
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "is_computing" not in st.session_state:
    st.session_state.is_computing = False

# ================= 主界面交互逻辑 =================
target_word = st.text_input("🔍 输入要查询的考研单词 (例如: seek)")

# 点击按钮后，触发运算状态
if st.button("透视真题考法"):
    if not target_word.strip():
        st.warning("请先输入需要查询的单词。")
    elif not api_key:
        st.warning("请配置 SiliconFlow API Key。")
    else:
        st.session_state.is_computing = True
        st.session_state.analysis_result = None # 清空上一轮的旧数据

# ================= 执行运算并实时流式输出 =================
if st.session_state.is_computing:
    client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
    
    with st.spinner('🤖 正在推演单词变形...'):
        variants_str = get_word_variants(target_word.strip(), client)
        
    with st.spinner('⚡ 正在真题库中扫荡原句...'):
        matched_results = search_word_expanded(variants_str, exam_data)
    
    if not matched_results:
        st.info(f"在当前的题库中没有找到关于 '{target_word}' 及其变形的真题出处。")
        st.session_state.is_computing = False
    else:
        st.caption(f"🔍 实际检索词根簇: `{variants_str}`")
        st.success(f"检索完毕！共找到 {len(matched_results)} 条原句。")
        
        # 【机制1】立马渲染原句出处，并且默认展开面板 (expanded=True)
        extracted_text = ""
        with st.expander("查看真题原句出处", expanded=True):
            for res in matched_results:
                line = f"[{res.get('year', '')} {res.get('source', '')}] {res.get('sentence', '')}"
                st.markdown(f"- {line}")
                extracted_text += line + "\n"

        st.markdown("### 🎯 真题考法深度解析")
        ai_placeholder = st.empty() # 创建空容器，准备渲染打字机特效
        
        prompt = f"""
你是一个专业的考研英语分析专家。现在我要重点分析单词【{target_word}】及其变形【{variants_str}】。
以下是它们在历年考研真题中的出处原句：
{extracted_text}

【处理要求】：
1. 若提供的原句中存在考场指令或排版残片，请自动忽略。
2. **考察释义**：归纳该单词在真题中实际考察的核心含义（标注年份）。
3. **相关短语**：提炼原句中出现的固定搭配或高频词组。
4. **考察方式解析**：结合真题语境，分析考查逻辑。
"""
        try:
            # 【机制2】stream=True 开启大模型实时流式推流
            response = client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V4-Flash",
                messages=[
                    {"role": "system", "content": "你是一个严谨的考研英语语料分析助手。"},
                    {"role": "user", "content": prompt}
                ],
                stream=True 
            )
            
            ai_analysis = ""
            for chunk in response:
                if len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                    ai_analysis += chunk.choices[0].delta.content
                    ai_placeholder.markdown(ai_analysis + "▌") # 追加光标闪烁效果
                    
            ai_placeholder.markdown(ai_analysis) # 生成完毕，去除光标
            
            # 【机制3】将完整内容锁进 session_state 记忆库，防止重置
            st.session_state.analysis_result = {
                "target_word": target_word.strip(),
                "variants_str": variants_str,
                "matched_results": matched_results,
                "extracted_text": extracted_text,
                "ai_analysis": ai_analysis
            }
            
            st.session_state.is_computing = False
            st.rerun() # 强制刷新页面一次，干净利落地展示下载按钮
            
        except Exception as e:
            st.error(f"深度解析调用失败，错误信息: {e}")
            st.session_state.is_computing = False

# ================= 渲染已锁定结果及下载按钮 =================
elif st.session_state.analysis_result:
    res = st.session_state.analysis_result
    
    st.caption(f"🔍 实际检索词根簇: `{res['variants_str']}`")
    st.success(f"检索完毕！共找到 {len(res['matched_results'])} 条原句。")
    
    with st.expander("查看真题原句出处", expanded=True):
        for res_item in res['matched_results']:
            line = f"[{res_item.get('year', '')} {res_item.get('source', '')}] {res_item.get('sentence', '')}"
            st.markdown(f"- {line}")
            
    # 【第一个下载按钮】
    sentences_note = f"【真题原句出处：{res['target_word']}】\n检索词根簇：{res['variants_str']}\n" + "="*40 + "\n\n" + res['extracted_text']
    st.download_button(
        label="💾 仅下载真题原句 (TXT)",
        data=sentences_note,
        file_name=f"{res['target_word']}_真题原句.txt",
        mime="text/plain",
        key="btn_dl_sentences"
    )
    
    st.markdown("### 🎯 真题考法深度解析")
    st.markdown(res['ai_analysis'])
    
    # 【第二个下载按钮】
    analysis_note = f"【真题考法深度解析：{res['target_word']}】\n" + "="*40 + "\n\n" + res['ai_analysis']
    st.download_button(
        label="💾 仅下载AI深度解析 (TXT)",
        data=analysis_note,
        file_name=f"{res['target_word']}_考法解析.txt",
        mime="text/plain",
        key="btn_dl_analysis"
    )
