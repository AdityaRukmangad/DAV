"""
Module: app/services/rag_service.py
Purpose: RAG Service with lazy loading and caching for fast repeated queries.
EXTENDED: Bloom-Adaptive RAG (Step 2) - Dynamically adjust k based on Bloom level
"""
import os
import re
import time
import hashlib
from typing import List, Tuple, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from flashrank import Ranker, RerankRequest

from app.rag import get_rag_engine
from app.tools.utils import get_logger

logger = get_logger("EnhancedRAGService")

# ========== BLOOM-ADAPTIVE RAG (STEP 2) ==========

def bloom_to_k(bloom_level: int) -> int:
    """
    Map Bloom's taxonomy level to number of chunks to retrieve.

    Bloom Level    Chunks (k)   Rationale
    -----------    ----------   ---------
    1-2            3-5          Simple recall/understanding needs fewer sources
    3-4            6-10         Application/analysis needs moderate context
    5-6            12-15        Evaluation/creation needs comprehensive context

    Can be overridden via env vars:
    - BLOOM_K_LOW (default: 4)
    - BLOOM_K_MED (default: 8)
    - BLOOM_K_HIGH (default: 13)
    """
    # Get config from environment with defaults
    k_low = int(os.getenv("BLOOM_K_LOW", "4"))    # 3-5 range, use middle
    k_med = int(os.getenv("BLOOM_K_MED", "8"))    # 6-10 range, use middle
    k_high = int(os.getenv("BLOOM_K_HIGH", "13"))  # 12-15 range, use middle

    if bloom_level is None:
        logger.warning("[Bloom RAG] bloom_level is None, using medium k")
        return k_med

    if bloom_level <= 2:
        logger.info(f"[Bloom RAG] Level {bloom_level} (Remember/Understand) → k={k_low}")
        return k_low
    elif bloom_level <= 4:
        logger.info(f"[Bloom RAG] Level {bloom_level} (Apply/Analyze) → k={k_med}")
        return k_med
    else:  # 5-6
        logger.info(f"[Bloom RAG] Level {bloom_level} (Evaluate/Create) → k={k_high}")
        return k_high


# ========== RAG CACHE ==========

class RAGCache:
    """TTL-based cache for vector search results"""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 100):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, Tuple[float, Any]] = {}  # key -> (timestamp, value)
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str, k: int) -> str:
        """Create cache key from query and k"""
        return hashlib.md5(f"{query}:{k}".encode()).hexdigest()

    def get(self, query: str, k: int) -> Optional[List]:
        """Get cached result if exists and not expired"""
        key = self._make_key(query, k)
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.ttl:
                self._hits += 1
                logger.debug(f"Cache HIT for query: {query[:50]}...")
                return value
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, query: str, k: int, value: List):
        """Store result in cache"""
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        key = self._make_key(query, k)
        self._cache[key] = (time.time(), value)

    def _evict_oldest(self):
        """Remove oldest entries when cache is full"""
        if not self._cache:
            return
        sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])
        for key in sorted_keys[:len(sorted_keys) // 4]:  # Remove oldest 25%
            del self._cache[key]

    def clear(self):
        """Clear the cache"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0,
            "ttl_seconds": self.ttl
        }


# Global cache instance
_rag_cache = RAGCache(ttl_seconds=300, max_size=100)


# Query expansion for common CS/ML acronyms
ACRONYM_EXPANSIONS = {
    "dfs": "depth first search DFS",
    "bfs": "breadth first search BFS",
    "dp": "dynamic programming DP",
    "ml": "machine learning ML",
    "nn": "neural network NN",
    "cnn": "convolutional neural network CNN",
    "rnn": "recurrent neural network RNN",
    "svm": "support vector machine SVM",
    "knn": "k nearest neighbors KNN",
    "pca": "principal component analysis PCA",
    "nlp": "natural language processing NLP",
    "ai": "artificial intelligence AI",
    "id3": "ID3 decision tree algorithm",
    "cart": "classification and regression tree CART",
}

# Keywords that indicate what TYPE of content the user wants
# Maps user keywords -> search terms to find that content in PDFs
CONTENT_TYPE_KEYWORDS = {
    # Algorithm representation types
    "pseudo-code": ["pseudo-code", "pseudocode", "algorithm", "procedure", "function"],
    "pseudocode": ["pseudo-code", "pseudocode", "algorithm", "procedure", "function"],
    "algorithm": ["algorithm", "pseudo-code", "pseudocode", "procedure", "steps"],
    "code": ["code", "implementation", "pseudo-code", "algorithm"],

    # Execution/trace types
    "trace": ["trace", "execution", "step by step", "example", "walk through"],
    "example": ["example", "trace", "sample", "demonstration", "worked"],
    "step": ["step", "trace", "execution", "procedure"],

    # Analysis types
    "complexity": ["complexity", "time complexity", "space complexity", "big O", "O(n)"],
    "time": ["time complexity", "running time", "efficiency"],
    "space": ["space complexity", "memory", "storage"],

    # Theory types
    "definition": ["definition", "defined", "is a", "refers to"],
    "theorem": ["theorem", "proof", "lemma", "property"],
    "formula": ["formula", "equation", "calculate", "computation"],

    # Comparison types
    "comparison": ["comparison", "compare", "versus", "vs", "difference"],
    "advantage": ["advantage", "benefit", "pros", "strength"],
    "disadvantage": ["disadvantage", "drawback", "cons", "weakness"],
}

def expand_query(query: str) -> str:
    """Expand acronyms in query for better retrieval"""
    words = query.lower().split()
    expanded = []
    for word in words:
        if word in ACRONYM_EXPANSIONS:
            expanded.append(ACRONYM_EXPANSIONS[word])
        else:
            expanded.append(word)
    return " ".join(expanded)

def extract_keywords(query: str) -> Dict[str, List[str]]:
    """
    Extract content-type keywords from the user query.
    Returns dict mapping detected keyword type -> search terms to use.
    """
    query_lower = query.lower()
    detected = {}

    for keyword, search_terms in CONTENT_TYPE_KEYWORDS.items():
        # Check if keyword appears in query (as whole word)
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, query_lower):
            detected[keyword] = search_terms
            logger.info(f"Detected content keyword: '{keyword}' -> will search for: {search_terms}")

    return detected

def extract_topic_terms(query: str) -> List[str]:
    """
    Extract the main topic/algorithm terms from the query.
    These are the subject matter (DFS, Gini, etc), not the content type.
    """
    query_lower = query.lower()
    topics = []

    # First expand any acronyms
    for acronym, expansion in ACRONYM_EXPANSIONS.items():
        if re.search(r'\b' + re.escape(acronym) + r'\b', query_lower):
            topics.append(expansion)

    # Common algorithm/topic patterns
    topic_patterns = [
        # ML/Decision Trees
        r'\b(decision tree|id3|cart|c4\.5)\b',
        r'\b(gini|entropy|information gain)\b',
        r'\b(naive bayes|bayes|bayesian)\b',
        r'\b(k-?means|clustering|kmeans)\b',
        r'\b(neural network|perceptron|backpropagation)\b',
        r'\b(gradient descent|optimization)\b',
        r'\b(svm|support vector)\b',
        r'\b(regression|linear|logistic)\b',
        r'\b(random forest|ensemble|boosting)\b',
        r'\b(cross.?validation|validation)\b',
        # AI Theory/Agents
        r'\b(rational agent|rationality|intelligent agent)\b',
        r'\b(peas|performance measure|environment|actuators|sensors)\b',
        r'\b(task environment|observable|deterministic|episodic|static|discrete)\b',
        r'\b(reflex agent|model.?based|goal.?based|utility.?based)\b',
        r'\b(learning agent|problem solving|search)\b',
        r'\b(state space|uninformed search|informed search)\b',
        r'\b(heuristic|admissible|a.?star|greedy)\b',
        # Search Algorithms
        r'\b(minimax|alpha.?beta|game tree|adversarial)\b',
        r'\b(constraint satisfaction|csp|backtracking)\b',
    ]

    for pattern in topic_patterns:
        match = re.search(pattern, query_lower)
        if match:
            topics.append(match.group(0))

    return topics

@dataclass
class RetrievalConfig:
    initial_k: int = 20
    final_k: int = 10
    use_reranking: bool = True

class HybridRetriever:
    def __init__(self, config: RetrievalConfig):
        self.config = config
        self._engine = None # Lazy load
        self._ranker = None # Lazy load
        self.logger = get_logger("HybridRetriever")

    @property
    def engine(self):
        if not self._engine:
            self._engine = get_rag_engine()
        return self._engine

    @property
    def ranker(self):
        if not self._ranker and self.config.use_reranking:
            # Fix for Windows: Set cache directory to a valid location
            import tempfile
            cache_dir = os.path.join(tempfile.gettempdir(), "flashrank_cache")
            os.makedirs(cache_dir, exist_ok=True)
            self._ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir=cache_dir)
            logger.info(f"[Ranker] Initialized with cache dir: {cache_dir}")
        return self._ranker

    def _search_single(self, query: str, k: int = 10) -> List:
        """Perform a single vector search with caching"""
        # Check cache first
        cached = _rag_cache.get(query, k)
        if cached is not None:
            return cached

        try:
            result = self.engine.query_knowledge_base(query, k=k)
            docs = result.source_documents
            # Cache the result
            _rag_cache.set(query, k, docs)
            return docs
        except Exception as e:
            self.logger.error(f"Vector search failed for '{query}': {e}")
            return []

    def _rerank_docs(self, query: str, docs: List, top_k: int) -> List:
        """Rerank documents and return top_k"""
        if not docs or not self.config.use_reranking or not self.ranker:
            return docs[:top_k]

        try:
            passages = [{"id": i, "text": d.page_content, "meta": d.metadata} for i, d in enumerate(docs)]
            results = self.ranker.rerank(RerankRequest(query=query, passages=passages))
            return [docs[r["id"]] for r in results][:top_k]
        except Exception as e:
            self.logger.error(f"Reranking failed: {e}")
            return docs[:top_k]

    def retrieve_with_keywords(self, query: str, bloom_level: int = None) -> Tuple[str, List[int], str, Dict[str, str]]:
        """
        Keyword-aware retrieval that searches for specific content types.
        EXTENDED: Now uses Bloom level to adaptively set k (Step 2)

        Args:
            query: The search query
            bloom_level: Bloom's taxonomy level (1-6) to determine k

        Returns (context, page_numbers, filename, keyword_contexts)
        keyword_contexts maps detected keywords to their specific context snippets
        """
        # BLOOM-ADAPTIVE RAG: Determine k based on bloom level
        if bloom_level is not None:
            adaptive_k = bloom_to_k(bloom_level)
            self.logger.info(f"[Bloom RAG] Using adaptive k={adaptive_k} for bloom_level={bloom_level}")
        else:
            adaptive_k = 10  # Default if no bloom level
            self.logger.info(f"[Bloom RAG] No bloom_level provided, using default k={adaptive_k}")

        # Extract content-type keywords and topic terms
        content_keywords = extract_keywords(query)
        topic_terms = extract_topic_terms(query)

        self.logger.info(f"Query: '{query}'")
        self.logger.info(f"Detected content keywords: {list(content_keywords.keys())}")
        self.logger.info(f"Detected topic terms: {topic_terms}")

        all_docs = []
        keyword_contexts = {}
        seen_content: Set[int] = set()  # Avoid duplicates

        # 1. Primary search with expanded query (topic + acronyms)
        expanded_query = expand_query(query)

        # Build all search queries upfront
        search_queries = [("primary", expanded_query)]

        # Add keyword-specific queries (limit to 1 search term per keyword for speed)
        for keyword, search_terms in content_keywords.items():
            topic = topic_terms[0] if topic_terms else expanded_query
            combined_query = f"{topic} {search_terms[0]}"  # Just first search term
            search_queries.append((keyword, combined_query))

        # 2. Run all searches in PARALLEL - use adaptive_k for primary search
        search_results = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_key = {
                executor.submit(self._search_single, q, adaptive_k if key == "primary" else 5): key
                for key, q in search_queries
            }
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    search_results[key] = future.result()
                except Exception as e:
                    self.logger.error(f"Search failed for {key}: {e}")
                    search_results[key] = []

        # 3. Process primary results
        for doc in search_results.get("primary", []):
            content_hash = hash(doc.page_content[:200])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                all_docs.append(("primary", doc))

        # 4. Process keyword results
        for keyword in content_keywords.keys():
            keyword_docs = []
            for doc in search_results.get(keyword, []):
                content_hash = hash(doc.page_content[:200])
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    keyword_docs.append(doc)
                    all_docs.append((keyword, doc))

            # Store best keyword-specific context (skip rerank for speed)
            if keyword_docs:
                keyword_contexts[keyword] = "\n".join([d.page_content[:800] for d in keyword_docs[:2]])
                self.logger.info(f"Found {len(keyword_docs)} docs for keyword '{keyword}'")

        if not all_docs:
            return "", [], "", {}

        # 3. Rerank all collected docs against original query - use adaptive final_k
        just_docs = [d for _, d in all_docs]
        final_k = adaptive_k if bloom_level is not None else self.config.final_k
        reranked = self._rerank_docs(query, just_docs, top_k=final_k)

        # 4. Extract metadata
        pages: Set[int] = set()
        filename = ""
        for d in reranked:
            page = d.metadata.get('page')
            if page is not None:
                try:
                    pages.add(int(page) + 1)
                except (ValueError, TypeError):
                    pass
            if not filename:
                filename = d.metadata.get('filename', '')

        # 5. Format output with keyword labels
        context_parts = []

        # Add keyword-specific contexts first (highlighted)
        if keyword_contexts:
            for keyword, kw_context in keyword_contexts.items():
                context_parts.append(f"--- RELEVANT {keyword.upper()} CONTENT ---\n{kw_context}")

        # Add general context
        context_parts.append("--- GENERAL TOPIC CONTEXT ---")
        for d in reranked:
            context_parts.append(f"[Source: {d.metadata.get('filename')}]\n{d.page_content[:1500]}")

        context = "\n\n".join(context_parts)
        return context, sorted(list(pages)), filename, keyword_contexts

    def retrieve(self, query: str) -> Tuple[str, List[int], str]:
        """Returns (context, page_numbers, filename) - backwards compatible"""
        context, pages, filename, _ = self.retrieve_with_keywords(query)
        return context, pages, filename

class EnterpriseRAGService:
    def __init__(self):
        self.retriever = HybridRetriever(RetrievalConfig())
        self._engine = None

    @property
    def engine(self):
        if not self._engine:
            self._engine = get_rag_engine()
        return self._engine

    def search(self, query: str, k: int = 5) -> str:
        """Simple search that returns context text"""
        try:
            # Direct call to engine for simple queries
            result = self.engine.query_knowledge_base(query, k=k)
            if result and result.context:
                logger.debug(f"[RAG Search] Found {len(result.context)} chars for '{query}'")
                return result.context
            else:
                logger.warning(f"[RAG Search] Empty result for '{query}'")
                return ""
        except Exception as e:
            logger.error(f"[RAG Search] Failed for '{query}': {e}")
            return ""

    def search_with_metadata(self, query: str, k: int = 5) -> Tuple[str, List[int], str]:
        """Returns (context, page_numbers, filename)"""
        return self.retriever.retrieve(query)

    def search_with_keywords(self, query: str, k: int = 5, bloom_level: int = None) -> Tuple[str, List[int], str, Dict[str, str]]:
        """
        Returns (context, page_numbers, filename, keyword_contexts)
        keyword_contexts maps detected keywords (e.g., "pseudo-code") to relevant content

        EXTENDED (Step 2): Now accepts bloom_level for adaptive k
        """
        return self.retriever.retrieve_with_keywords(query, bloom_level=bloom_level)

    def ingest_file(self, file_path: str):
        # Clear cache when new content is added
        _rag_cache.clear()
        logger.info("Cache cleared due to new file ingestion")
        return self.engine.ingest_pdf(file_path, force=True)

    def get_statistics(self):
        return self.engine.get_statistics()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get RAG cache statistics"""
        return _rag_cache.stats()

    def clear_cache(self):
        """Manually clear the RAG cache"""
        _rag_cache.clear()
        logger.info("Cache manually cleared")

# Singleton Instance (Lazy)
_service = None

def get_rag_service():
    global _service
    if not _service: 
        _service = EnterpriseRAGService()
    return _service