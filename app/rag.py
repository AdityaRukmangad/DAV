"""
Enhanced RAG Engine with Smart Chunking and Nuclear Metadata Sanitization
Fixed: 'KeyError: _type' by bypassing Document serialization completely.
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.tools.utils import get_logger, timed_execution

logger = get_logger("RAGEngine")

class ChunkStrategy(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    SEMANTIC = "semantic"

@dataclass
class ChunkConfig:
    chunk_size: int
    chunk_overlap: int
    separators: List[str]
    
    @staticmethod
    def from_strategy(strategy: ChunkStrategy) -> 'ChunkConfig':
        configs = {
            ChunkStrategy.SMALL: ChunkConfig(500, 50, ["\n\n", "\n", ". "]),
            ChunkStrategy.MEDIUM: ChunkConfig(1000, 100, ["\n\n", "\n", ". "]),
            ChunkStrategy.LARGE: ChunkConfig(2000, 200, ["\n\n", "\n"]),
            ChunkStrategy.SEMANTIC: ChunkConfig(1200, 150, ["\n\n", "\n"])
        }
        return configs[strategy]

@dataclass
class IngestionResult:
    file_path: str
    file_hash: str
    chunk_count: int
    total_pages: int
    success: bool
    avg_chunk_size: int = 0
    metadata_extracted: bool = True
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0

@dataclass
class RetrievalResult:
    context: str
    source_documents: List[Document]
    relevance_scores: List[float]
    query: str
    num_sources: int = 0
    avg_relevance: float = 0.0

class DocumentRegistry:
    def __init__(self, registry_path: str = "ingestion_registry.txt"):
        self.registry_path = registry_path
    
    def is_ingested(self, file_hash: str) -> bool:
        if not os.path.exists(self.registry_path): return False
        with open(self.registry_path, 'r') as f:
            return file_hash in f.read()
    
    def register_document(self, file_path: str, file_hash: str, chunk_count: int):
        with open(self.registry_path, 'a') as f:
            f.write(f"{file_hash}|{file_path}|{chunk_count}\n")
    
    def get_ingested_documents(self) -> List[Dict[str, str]]:
        if not os.path.exists(self.registry_path): return []
        docs = []
        with open(self.registry_path, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    docs.append({'hash': parts[0], 'path': parts[1], 'chunks': parts[2]})
        return docs

class PDFProcessor:
    def __init__(self):
        self.logger = get_logger("PDFProcessor")
    
    def validate_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        if not os.path.exists(file_path): return False, "File not found"
        if not file_path.lower().endswith('.pdf'): return False, "Not a PDF"
        if os.path.getsize(file_path) == 0: return False, "Empty file"
        return True, None
    
    def calculate_hash(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192): hasher.update(chunk)
        return hasher.hexdigest()
    
    def load_pdf(self, file_path: str) -> List[Document]:
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            clean_filename = os.path.basename(file_path)
            for doc in documents:
                # Basic metadata init
                doc.metadata = {
                    'source': clean_filename,
                    'filename': clean_filename,
                    'page': doc.metadata.get('page', 0)
                }
            return documents
        except Exception as e:
            self.logger.error(f"Load failed: {e}")
            raise

class VectorStore:
    def __init__(self, persist_directory: str = "chroma_db"):
        self.persist_directory = persist_directory
        self.logger = get_logger("VectorStore")
        try:
            self.embedding_function = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            # Initialize Chroma with explicit client settings to avoid tenant issues
            from chromadb.config import Settings
            self.db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embedding_function,
                client_settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize vector store: {e}")
            self.db = None
            self.embedding_function = None
    
    def store_chunks(self, chunks: List[Document]) -> int:
        if not chunks: return 0
        if not self.db:
            self.logger.warning("Vector store not available. Skipping chunk storage.")
            return 0
        batch_size = 50
        
        # Prepare pure Python lists (str and dict) to bypass Document object serialization issues
        texts = []
        metadatas = []
        
        for c in chunks:
            # 1. Force content to string
            content = str(c.page_content)
            
            # 2. Strict Metadata Whitelist
            safe_metadata = {}
            for k, v in c.metadata.items():
                if k.startswith('_'): continue # Skip internal keys
                if isinstance(v, (str, int, float, bool)):
                    safe_metadata[k] = v
                else:
                    safe_metadata[k] = str(v)
            
            texts.append(content)
            metadatas.append(safe_metadata)

        try:
            total_stored = 0
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_metas = metadatas[i:i + batch_size]
                
                # USE add_texts DIRECTLY (Bypasses 'Document' serialization)
                self.db.add_texts(texts=batch_texts, metadatas=batch_metas)
                total_stored += len(batch_texts)
                
            return total_stored
        except Exception as e:
            self.logger.error(f"Storage failed: {e}")
            raise

    def get_database(self):
        return self.db
    
    def get_collection_stats(self) -> Dict:
        if not self.db:
            return {"total_vectors": 0, "status": "not_initialized"}
        try:
            count = self.db._collection.count()
            return {"total_vectors": count, "status": "active"}
        except Exception as e:
            self.logger.warning(f"Could not get collection stats: {e}")
            return {"total_vectors": 0, "status": "error"}

class RAGEngine:
    def __init__(self, chunk_strategy: ChunkStrategy = ChunkStrategy.MEDIUM):
        self.chunk_config = ChunkConfig.from_strategy(chunk_strategy)
        self.registry = DocumentRegistry()
        self.pdf_processor = PDFProcessor()
        self.vector_store = VectorStore()
        self.logger = get_logger("RAGEngine")
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_config.chunk_size,
            chunk_overlap=self.chunk_config.chunk_overlap,
            separators=self.chunk_config.separators
        )

    def ingest_pdf(self, file_path: str, force: bool = False) -> IngestionResult:
        import time
        start = time.time()
        
        valid, err = self.pdf_processor.validate_file(file_path)
        if not valid: return IngestionResult(file_path, "", 0, 0, False, error_message=err)
        
        file_hash = self.pdf_processor.calculate_hash(file_path)
        if not force and self.registry.is_ingested(file_hash):
            return IngestionResult(file_path, file_hash, 0, 0, False, error_message="Duplicate")

        try:
            docs = self.pdf_processor.load_pdf(file_path)
            chunks = self.splitter.split_documents(docs)
            stored = self.vector_store.store_chunks(chunks)
            self.registry.register_document(file_path, file_hash, stored)
            
            return IngestionResult(
                file_path, file_hash, stored, len(docs), True,
                avg_chunk_size=sum(len(c.page_content) for c in chunks)//(len(chunks) or 1),
                processing_time_ms=(time.time()-start)*1000
            )
        except Exception as e:
            return IngestionResult(file_path, file_hash, 0, 0, False, error_message=str(e))

    def query_knowledge_base(self, topic: str, k: int = 3) -> RetrievalResult:
        try:
            db = self.vector_store.get_database()
            if not db:
                return RetrievalResult("", [], [], topic)
            results = db.similarity_search_with_score(topic, k=k)
            docs = [doc for doc, _ in results]
            scores = [score for _, score in results]
            context = "\n\n".join([d.page_content for d in docs])
            return RetrievalResult(context, docs, scores, topic)
        except Exception as e:
            self.logger.error(f"Query failed: {e}")
            return RetrievalResult("", [], [], topic)
    
    def query_by_pdf(self, pdf_filename: str, k: int = 20) -> RetrievalResult:
        """Query chunks specifically from a given PDF file"""
        try:
            db = self.vector_store.get_database()
            if not db:
                return RetrievalResult("", [], [], f"content from {pdf_filename}")
            
            # Query with generic terms to get a large set of documents
            # Then filter by source filename from metadata
            all_docs = db.similarity_search("artificial intelligence machine learning", k=150)
            
            # Filter to only docs from this PDF
            matching_docs = []
            for doc in all_docs:
                if 'source' in doc.metadata:
                    # Check if filename matches (handle both full paths and just filenames)
                    source = doc.metadata['source']
                    source_basename = os.path.basename(source)
                    if pdf_filename == source_basename or pdf_filename in source:
                        matching_docs.append(doc)
                        if len(matching_docs) >= k:
                            break
            
            if not matching_docs:
                self.logger.warning(f"No chunks found for PDF: {pdf_filename}")
                return RetrievalResult("", [], [], f"content from {pdf_filename}")
            
            context = "\n\n".join([d.page_content for d in matching_docs])
            self.logger.info(f"Retrieved {len(matching_docs)} chunks ({len(context)} chars) from {pdf_filename}")
            
            return RetrievalResult(context, matching_docs, [], f"content from {pdf_filename}", num_sources=len(matching_docs))
        except Exception as e:
            self.logger.error(f"Query by PDF failed for {pdf_filename}: {e}")
            return RetrievalResult("", [], [], f"content from {pdf_filename}")

    def get_statistics(self) -> Dict:
        return {
            "vector_store": self.vector_store.get_collection_stats(),
            "ingested_documents": len(self.registry.get_ingested_documents())
        }

_rag_singleton = None
def get_rag_engine() -> RAGEngine:
    global _rag_singleton
    if not _rag_singleton: _rag_singleton = RAGEngine()
    return _rag_singleton