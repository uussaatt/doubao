import streamlit as st
import os
import daft
from daft import col
try:
    from daft.las.functions.ark_llm.ark_llm_vision_understanding import ArkLLMVisionUnderstanding
    from daft.las.functions.udf import las_udf
except ImportError:
    st.error("请确保已安装包含火山引擎 LAS 支持的 getdaft 扩展包。")

# --- 页面配置 ---
st.set_page_config(
    page_title="豆包 1.5 Vision 视频理解助手",
    page_icon="🎬",
    layout="wide"
)

# --- 样式美化 ---
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
    </style>
    """, unsafe_allow_stdio=True)

# --- 侧边栏：配置与参数 ---
with st.sidebar:
    st.title("⚙️ 配置中心")
    
    # 优先从 Streamlit Secrets 读取，如果没有则留空
    default_key = st.secrets.get("LAS_API_KEY", "")
    api_key = st.text_input("火山引擎 LAS API KEY", value=default_key, type="password", 
                            help="在火山引擎控制台获取。如果在 Secrets 中配置了，会自动填充。")
    
    st.divider()
    
    model_name = st.selectbox(
        "选择大模型版本",
        ["doubao-1.5-vision-pro", "doubao-1.5-vision-lite"],
        index=0
    )
    
    system_text = st.text_area(
        "系统提示词 (System Text)",
        value="你是一个专业的视频理解助手，能够分析视频中的内容并提供详细的描述。",
        height=100
    )
    
    st.info("💡 提示：本应用使用 Daft 框架分布式处理视频数据。")

# --- 主界面 ---
st.title("🎬 豆包 1.5 Vision 视频分析助手")
st.markdown("上传一个视频 URL，并告诉 AI 你想了解什么。")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. 输入数据")
    video_url = st.text_input(
        "视频直链 URL (支持 MP4 等格式)", 
        value="https://las-cn-beijing-public-online.tos-cn-beijing.volces.com/public/shared_video_dataset/eating_56.mp4"
    )
    
    prompt_text = st.text_area(
        "你的问题 (Prompt)",
        value="视频里有什么？",
        height=100
    )
    
    # 视频预览
    if video_url:
        try:
            st.video(video_url)
        except:
            st.warning("无法加载视频预览，请检查 URL 是否正确。")

    run_btn = st.button("🚀 开始 AI 分析", type="primary", use_container_width=True)

with col2:
    st.subheader("2. 分析结果")
    
    if run_btn:
        if not api_key:
            st.error("❌ 错误：请在侧边栏输入您的 LAS_API_KEY")
        else:
            # 动态设置环境变量供 Daft UDF 使用
            os.environ["LAS_API_KEY"] = api_key
            
            with st.spinner("🔍 豆包大模型正在分析视频，请稍候..."):
                try:
                    # 1. 构建 Daft DataFrame
                    samples = {
                        "videos": [video_url],
                        "prompts": [prompt_text],
                    }
                    df = daft.from_pydict(samples)
                    
                    # 2. 调用视觉理解 UDF
                    df = df.with_column(
                        "llm_result",
                        las_udf(
                            ArkLLMVisionUnderstanding,
                            construct_args={
                                "model": model_name,
                                "system_text": system_text,
                                "inference_type": "online",
                            },
                        )(videos=col("videos"), texts=col("prompts")),
                    )
                    
                    # 3. 执行并获取数据
                    # to_pandas() 会触发实际的计算任务
                    results = df.to_pandas()
                    llm_output = results.iloc[0]["llm_result"]
                    
                    # 4. 展示结果
                    st.success("✅ 分析完成！")
                    st.markdown("---")
                    st.markdown(f"**AI 回复：**\n\n{llm_output}")
                    
                except Exception as e:
                    st.error(f"❌ 运行过程中出错：\n\n`{str(e)}`")
                    st.info("请检查 API Key 是否有效，以及模型名称是否在您的服务权限内。")
    else:
        st.write("点击左侧按钮开始分析...")

# 页脚
st.markdown("---")
st.caption("Powered by [Daft](https://www.getdaft.io/) & Volcengine Ark LLM")