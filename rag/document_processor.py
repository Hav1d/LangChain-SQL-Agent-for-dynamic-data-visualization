"""
文档处理模块 - 负责文档加载、切分和预处理

增强版:
- Token感知分块 (from_tiktoken_encoder)
- 多表示索引: 摘要做检索，返回原文
"""
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import CHUNK_SIZE, CHUNK_OVERLAP, REPORTS_DIR


def _create_splitter(chunk_size: int, chunk_overlap: int, token_aware: bool = True):
    """创建文本分割器（优先使用token感知模式）"""
    if token_aware:
        try:
            return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", "。", ".", " ", ""],
            )
        except Exception:
            pass
    # 回退到字符计数模式
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )


class DocumentProcessor:
    """文档处理器（增强版）"""

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or CHUNK_OVERLAP
        self.splitter = _create_splitter(self.chunk_size, self.chunk_overlap)

    def load_markdown_files(self, directory: str = None) -> list:
        """加载目录下所有Markdown文件"""
        directory = Path(directory or REPORTS_DIR)
        documents = []

        if not directory.exists():
            return documents

        for md_file in directory.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if content.strip():
                    doc = Document(
                        page_content=content,
                        metadata={
                            "source": str(md_file),
                            "filename": md_file.name,
                            "file_type": "markdown",
                        }
                    )
                    documents.append(doc)
            except Exception as e:
                print(f"  [WARN] 无法读取 {md_file}: {e}")

        return documents

    def load_from_database(self, db_path: str) -> list:
        """从数据库加载分析报告"""
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT report_type, title, content, created_at FROM analysis_reports")
            rows = cursor.fetchall()
        except Exception:
            rows = []
        finally:
            conn.close()

        documents = []
        for report_type, title, content, created_at in rows:
            if content and content.strip():
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": f"database:{report_type}",
                        "title": title,
                        "report_type": report_type,
                        "created_at": created_at,
                    }
                )
                documents.append(doc)

        return documents

    def split_documents(self, documents: list) -> list:
        """切分文档为小块"""
        if not documents:
            return []
        chunks = self.splitter.split_documents(documents)
        return chunks

    @staticmethod
    def generate_summary(doc: Document) -> str:
        """生成文档摘要（无需LLM，基于规则提取）

        从报告中提取关键信息作为轻量级摘要:
        - 标题/报告类型
        - 包含的数字指标
        - 关键段落首句
        """
        content = doc.page_content
        title = doc.metadata.get("title", doc.metadata.get("report_type", ""))

        lines = content.strip().split("\n")
        summary_parts = []

        # 添加标题
        if title:
            summary_parts.append(title)

        # 提取包含数字的关键行（通常是指标数据）
        import re
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---"):
                continue
            # 包含数字的行通常是关键指标
            if re.search(r"\d+", line) and len(line) < 200:
                summary_parts.append(line)
            # 只取前5行关键数据
            if len(summary_parts) >= 6:
                break

        # 如果提取内容不足，取前3段
        if len(summary_parts) < 2:
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            for p in paragraphs[:3]:
                if len(p) < 300:
                    summary_parts.append(p)

        return "\n".join(summary_parts)

    def create_multi_representation(self, documents: list) -> tuple:
        """创建多表示索引: 摘要用于检索，原文用于返回

        Returns:
            (summary_docs, doc_store): 摘要文档列表 + 原文映射
        """
        summary_docs = []
        doc_store = {}

        for i, doc in enumerate(documents):
            doc_id = f"doc_{i}"
            summary = self.generate_summary(doc)
            summary_doc = Document(
                page_content=summary,
                metadata={**doc.metadata, "doc_id": doc_id},
            )
            summary_docs.append(summary_doc)
            doc_store[doc_id] = doc

        return summary_docs, doc_store

    def process(self, db_path: str = None, report_dir: str = None) -> list:
        """
        完整文档处理流程：加载 → 切分

        Returns:
            list: 切分后的文档块
        """
        print("📄 开始文档处理...")

        all_docs = []

        # 加载Markdown文件
        md_docs = self.load_markdown_files(report_dir)
        all_docs.extend(md_docs)
        print(f"  [OK] 从文件加载 {len(md_docs)} 篇文档")

        # 加载数据库报告
        if db_path:
            db_docs = self.load_from_database(db_path)
            all_docs.extend(db_docs)
            print(f"  [OK] 从数据库加载 {len(db_docs)} 篇文档")

        if not all_docs:
            print("  [WARN] 没有找到可处理的文档")
            return []

        # 切分
        chunks = self.split_documents(all_docs)
        print(f"  [OK] 切分为 {len(chunks)} 个文本块")

        return chunks
