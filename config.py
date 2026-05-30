import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# 项目路径
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
CHROMA_DIR = DATA_DIR / "chroma_db"
DB_PATH = DATA_DIR / "ecommerce.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────
# LLM 配置 (SiliconFlow - OpenAI 兼容接口)
# ──────────────────────────────────────────────
siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY", "")
llm_base_url = "https://api.siliconflow.cn/v1"
llm_model_id = "Qwen/Qwen3-8B"
llm_temperature = 0.1

# ──────────────────────────────────────────────
# 数据库配置
# ──────────────────────────────────────────────
database_url = DATABASE_URL

# ──────────────────────────────────────────────
# Agent 配置
# ──────────────────────────────────────────────
agent_max_iterations = 15
agent_max_execution_time = 60

# ──────────────────────────────────────────────
# RFM 分析配置
# ──────────────────────────────────────────────
RFM_REFERENCE_DATE = "2018-09-03"  # Olist数据集的最后日期
RFM_QUANTILES = 5  # 评分分位数

# ──────────────────────────────────────────────
# RAG 配置
# ──────────────────────────────────────────────
EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
CHUNK_SIZE = 200
CHUNK_OVERLAP = 50
RAG_TOP_K = 6
