"""
文档处理模块 - 负责文档加载、切分和预处理
"""
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import CHUNK_SIZE, CHUNK_OVERLAP, REPORTS_DIR


class DocumentProcessor:
    """文档处理器"""

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or CHUNK_OVERLAP
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", ".", " ", ""]
        )

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
