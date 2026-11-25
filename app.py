import streamlit as st
import json
import re
from openai import OpenAI

# ================= 页面基础配置 =================
st.set_page_config(page_title="考研真题透视", page_icon="📖")
st.title("📖 考研英语真题透视 (Gemini 双模式版)")
st.markdown("结合本地真题数据库与 Gemini 模型，精准解析单词及其**所有变形**在真题中的具体考法。")

# ================= 侧边栏：API 密钥与模型配置 =================
with st.sidebar:
    st.header("⚙️ 系统配置")
    
    # 安全读取 Streamlit Secrets（防止本地无 secrets.toml 时报错）
    try:
        default_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        default_key = ""
    
    if not default_key:
        api_key = st.text_input("请输入 Gemini API Key", type="password")
        st.warning("👈 未检测到内置密钥，请手动输入")
    else:
        api_key = default_key
        st.success("✅ Gemini 密钥已自动加载！")
        
    st.markdown("---")
    
    # 接口地址：默认为 Google AI Studio 的 OpenAI 兼容端点；用中转站直接改这里
    base_url = st.text_input(
        "API Base URL",
        value="https://generativelanguage.googleapis.com/v1beta/openai/",
        help="官方默认地址无需修改；如使用第三方中转站，请替换为对应 /v1 地址"
    )
    
    # 模型名称：请替换为后台实际的精确 Model ID
    model_name = st.text_input(
        "模型 ID (Model Name)",
        value="gemini-4-hydrogen",
        help="请核对 API 后台的模型列表，填入精确的模型字符串（区分格式且不能有空格）"
    )
    
    st.caption(f"当前调用模型: `{model_name}`")

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

def get_word_variants(word, client, model):
    prompt = f"""
    请给出英语单词 "{word}" 的所有常见屈折变化形式（包括复数、过去式、过去分词、现在分词、第三人称单数等）。
    要求：只输出单词本身，用竖线 "|" 分隔。绝对不要输出任何标点符号、解释或其他多余文字。
    示例：输入 "make"，输出 "make|makes|made|making"
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        raw_content = (response.choices[0].message.content or "").strip()
        cleaned = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL)
        cleaned = re.sub(r'</?think>', '', cleaned)
        cleaned = re.sub(r'[^a-zA-Z|]', '', cleaned)
        variants_list = [v.strip() for v in cleaned.split('|') if v.strip()]
        if word.lower() not in [v.lower() for v in variants_list]:
            variants_list.append(word.strip())
        return "|".join(list(dict.fromkeys(variants_list)))
    except Exception as e:
        st.warning(f"词形推演调用异常，已退回原词检索：{e}")
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
if "run_mode" not in st.session_state:
    st.session_state.run_mode = "模式一"

# ================= 主界面交互逻辑 =================
target_word = st.text_input("🔍 输入要查询的考研单词 (例如: seek)")

selected_mode = st.radio(
    "⚙️ 选择运行模式：",
    ("模式一：仅检索真题原句 (快速提取，可用于喂给其他AI)", "模式二：检索并进行 AI 深度解析 (完整打字机推演)"),
    horizontal=True
)

if st.button("透视真题考法"):
    if not target_word.strip():
        st.warning("请先输入需要查询的单词。")
    elif not api_key:
        st.warning("请先在侧边栏或 Secrets 中配置 Gemini API Key。")
    elif not model_name.strip():
        st.warning("请填写正确的模型 ID。")
    else:
        st.session_state.is_computing = True
        st.session_state.run_mode = selected_mode
        st.session_state.analysis_result = None

# ================= 执行运算并实时流式输出 =================
if st.session_state.is_computing:
    client = OpenAI(api_key=api_key, base_url=base_url.strip())
    current_model = model_name.strip()
    
    with st.spinner('🤖 正在推演单词变形...'):
        variants_str = get_word_variants(target_word.strip(), client, current_model)
        
    with st.spinner('⚡ 正在真题库中扫荡原句...'):
        matched_results = search_word_expanded(variants_str, exam_data)
    
    if not matched_results:
        st.info(f"在当前的题库中没有找到关于 '{target_word}' 及其变形的真题出处。")
        st.session_state.is_computing = False
    else:
        st.caption(f"🔍 实际检索词根簇: `{variants_str}`")
        st.success(f"检索完毕！共找到 {len(matched_results)} 条原句。")
        
        extracted_text = ""
        with st.expander("查看真题原句出处", expanded=True):
            for res in matched_results:
                line = f"[{res.get('year', '')} {res.get('source', '')}] {res.get('sentence', '')}"
                st.markdown(f"- {line}")
                extracted_text += line + "\n"

        if st.session_state.run_mode.startswith("模式一"):
            st.session_state.analysis_result = {
                "mode": "mode1",
                "target_word": target_word.strip(),
                "variants_str": variants_str,
                "matched_results": matched_results,
                "extracted_text": extracted_text,
                "ai_analysis": None
            }
            st.session_state.is_computing = False
            st.rerun()
            
        else:
            st.markdown("### 🎯 真题考法深度解析")
            ai_placeholder = st.empty()
            
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
                response = client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": "你是一个严谨的考研英语语料分析助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    stream=True
                )
                
                ai_analysis = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        ai_analysis += chunk.choices[0].delta.content
                        ai_placeholder.markdown(ai_analysis + "▌")
                        
                ai_placeholder.markdown(ai_analysis)
                
                st.session_state.analysis_result = {
                    "mode": "mode2",
                    "target_word": target_word.strip(),
                    "variants_str": variants_str,
                    "matched_results": matched_results,
                    "extracted_text": extracted_text,
                    "ai_analysis": ai_analysis
                }
                st.session_state.is_computing = False
                st.rerun()
                
            except Exception as e:
                st.error(f"深度解析调用失败，请检查模型 ID、Base URL 或 Key 是否正确。\n\n错误信息: {e}")
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
            
    sentences_note = f"【真题原句出处：{res['target_word']}】\n检索词根簇：{res['variants_str']}\n" + "="*40 + "\n\n" + res['extracted_text']
    st.download_button(
        label="💾 下载真题原句 (TXT)",
        data=sentences_note,
        file_name=f"{res['target_word']}_真题原句.txt",
        mime="text/plain",
        key="btn_dl_sentences"
    )
    
    if res.get("mode") == "mode2" and res.get("ai_analysis"):
        st.markdown("### 🎯 真题考法深度解析")
        st.markdown(res['ai_analysis'])
        
        analysis_note = f"【真题考法深度解析：{res['target_word']}】\n" + "="*40 + "\n\n" + res['ai_analysis']
        st.download_button(
            label="💾 下载AI深度解析 (TXT)",
            data=analysis_note,
            file_name=f"{res['target_word']}_考法解析.txt",
            mime="text/plain",
            key="btn_dl_analysis"
        )
