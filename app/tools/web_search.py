"""
Module: app/tools/web_search.py
Purpose: Academic-Focused Web Search for Exam Papers
Enhanced: Prioritizes university papers, research papers, and previous exam papers
"""
import time
from typing import Optional, Type, Dict, Tuple, List
from datetime import datetime, timedelta

from duckduckgo_search import DDGS
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from app.tools.utils import get_logger

logger = get_logger("WebSearchEngine")

class SearchCache:
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Dict, datetime]] = {}

    def get(self, query: str) -> Optional[Dict]:
        if query in self.cache:
            res, ts = self.cache[query]
            if datetime.now() - ts < timedelta(seconds=self.ttl_seconds):
                return res
        return None

    def set(self, query: str, result: Dict):
        self.cache[query] = (result, datetime.now())

class SearchInput(BaseModel):
    query: str = Field(description="Search query", min_length=2)

class EnterpriseWebSearch(BaseTool):
    name: str = "web_search_enterprise"
    description: str = "Deep search for university problems, academic papers, and previous exam papers."
    args_schema: Type[BaseModel] = SearchInput
    max_results: int = 15
    _cache: SearchCache = PrivateAttr(default_factory=SearchCache)

    def _calculate_priority(self, url: str, title: str, body: str) -> int:
        """Calculate priority score for academic relevance."""
        score = 0
        url_lower = url.lower()
        title_lower = title.lower()
        body_lower = body.lower()

        # Academic domains (highest priority)
        academic_domains = ['.edu', '.ac.uk', '.ac.in', 'scholar.google',
                           'arxiv.org', 'ieee.org', 'springer.com', 'sciencedirect.com',
                           'researchgate.net', 'jstor.org', 'mit.edu', 'stanford.edu',
                           'cambridge.org', 'oxford']
        for domain in academic_domains:
            if domain in url_lower:
                score += 100
                break

        # PDF documents (academic papers)
        if '.pdf' in url_lower or 'pdf' in url_lower:
            score += 50

        # Exam/question keywords
        exam_keywords = ['exam', 'question', 'paper', 'test', 'quiz', 'problem set',
                        'assignment', 'homework', 'practice', 'solved', 'solution']
        for keyword in exam_keywords:
            if keyword in title_lower:
                score += 30
            if keyword in body_lower:
                score += 10

        # Academic keywords
        academic_keywords = ['university', 'college', 'lecture', 'course', 'syllabus',
                            'professor', 'tutorial', 'study material', 'notes']
        for keyword in academic_keywords:
            if keyword in title_lower or keyword in url_lower:
                score += 20

        # Year patterns (recent papers)
        import re
        years = re.findall(r'20[12][0-9]', title + body)
        if years:
            score += 15

        return score

    def _run(self, query: str) -> str:
        cached = self._cache.get(query)
        if cached:
            return cached['text']

        logger.info(f"Searching Academic Sources: '{query}'")

        try:
            # Enhanced query with academic filters
            academic_queries = [
                f"{query} site:edu filetype:pdf",
                f"{query} previous exam papers site:edu",
                f"{query} solved problems university",
                f"{query} lecture notes site:ac.uk OR site:edu",
                f"{query} practice questions"
            ]

            all_results = []

            with DDGS() as ddgs:
                # Try academic-focused searches
                for aq in academic_queries[:3]:  # Limit to avoid rate limiting
                    try:
                        results = list(ddgs.text(
                            keywords=aq,
                            region="wt-wt",
                            safesearch="off",
                            max_results=5
                        ))
                        all_results.extend(results)
                        time.sleep(0.5)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Query '{aq}' failed: {e}")
                        continue

            if not all_results:
                logger.warning("No academic results found, trying general search...")
                with DDGS() as ddgs:
                    all_results = list(ddgs.text(
                        keywords=query,
                        region="wt-wt",
                        safesearch="off",
                        max_results=self.max_results
                    ))

            if not all_results:
                return "No results found."

            # Score and sort results by academic relevance
            scored_results = []
            for r in all_results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                priority = self._calculate_priority(href, title, body)

                if priority > 0:  # Only include relevant results
                    scored_results.append({
                        'title': title,
                        'url': href,
                        'body': body,
                        'priority': priority
                    })

            # Sort by priority and deduplicate
            scored_results.sort(key=lambda x: x['priority'], reverse=True)
            seen_urls = set()
            unique_results = []
            for r in scored_results:
                if r['url'] not in seen_urls:
                    seen_urls.add(r['url'])
                    unique_results.append(r)

            # Format top results
            formatted = []
            source_links = []

            for r in unique_results[:8]:  # Top 8 academic sources
                formatted.append(
                    f"[ACADEMIC SOURCE: {r['title']}]\n"
                    f"URL: {r['url']}\n"
                    f"RELEVANCE: {r['priority']}/100\n"
                    f"CONTENT: {r['body']}"
                )
                source_links.append(r['url'])

            final_text = "\n\n".join(formatted)

            # Cache both text and links
            cache_data = {
                'text': final_text,
                'links': source_links
            }
            self._cache.set(query, cache_data)

            logger.info(f"Found {len(unique_results)} academic sources (Top priority: {unique_results[0]['priority'] if unique_results else 0})")
            return final_text

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Search Error: {str(e)}"

    def get_source_links(self, query: str) -> List[str]:
        """Extract source links from cache or perform new search."""
        cached = self._cache.get(query)
        if cached and 'links' in cached:
            return cached['links']

        # Perform search to populate cache
        self._run(query)

        # Try cache again
        cached = self._cache.get(query)
        return cached.get('links', []) if cached else []

def get_search_tool():
    return EnterpriseWebSearch()