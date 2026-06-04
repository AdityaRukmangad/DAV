#!/usr/bin/env python3
"""
PDF Usage Evidence Display
Shows which PDF pages were used for RAG retrieval with full context
Uses actual vector similarity search (same as question generation)
"""
import sys
from pathlib import Path

def show_pdf_usage(topic: str = "information gain", limit: int = 5):
    """
    Display PDF chunks retrieved for a given topic with metadata
    Uses the EXACT SAME RAG retrieval as the question generation system

    Args:
        topic: Search term to find in PDF content
        limit: Maximum number of chunks to display
    """
    try:
        # Import the RAG engine to access Document objects with metadata
        from app.rag import get_rag_engine

        # Get the RAG engine directly to access Document objects with metadata
        rag_engine = get_rag_engine()
        result = rag_engine.query_knowledge_base(topic, k=limit)

        if not result or not result.source_documents:
            print(f"\n[WARNING] No PDF context found for topic: '{topic}'")
            print("The vector database did not return any relevant chunks.\n")
            return

        # Extract chunks data with full metadata
        chunks_data = []
        pages_used = set()

        for doc in result.source_documents:
            page_num = doc.metadata.get('page', 'Unknown')
            filename = doc.metadata.get('filename', 'Unknown')

            if page_num != 'Unknown' and page_num is not None:
                try:
                    pages_used.add(int(page_num))
                except (ValueError, TypeError):
                    pass

            chunks_data.append({
                'content': doc.page_content,
                'page': page_num if page_num != 'Unknown' else 'N/A',
                'filename': filename
            })

        if not chunks_data:
            print(f"\n[WARNING] No chunks retrieved for topic: '{topic}'\n")
            return

        # Display results
        _display_chunks(topic, chunks_data, pages_used)

    except ImportError as e:
        print(f"[ERROR] Could not load RAG service: {e}")
        print("Ensure all dependencies are installed and you're running from the correct environment.")
    except Exception as e:
        print(f"[ERROR] Failed to retrieve PDF context: {e}")
        import traceback
        traceback.print_exc()

def _display_chunks(topic, chunks_data, pages_used):
    """Display chunks with nice formatting"""

    if not chunks_data:
        print(f"\n[WARNING] No chunks found for topic: '{topic}'")
        print("No PDF context available for this topic.\n")
        return

    # Header
    print("\n" + "=" * 120)
    print(f"PDF CONTEXT RETRIEVED FOR: '{topic}'".center(120))
    print("=" * 120)
    print(f"\nSource: {chunks_data[0]['filename']}")
    print(f"Pages Referenced: {sorted(pages_used) if pages_used else 'N/A'}")
    print(f"Total Chunks: {len(chunks_data)}")
    print("\n" + "=" * 120)

    # Display chunks with better formatting
    for i, chunk in enumerate(chunks_data, 1):
        print(f"\n[CHUNK {i}/{len(chunks_data)}] Page {chunk['page']}")
        print("-" * 120)

        # Clean and format content
        content = chunk['content'].strip()

        # Show first 600 characters for better readability
        if len(content) > 600:
            print(content[:600] + "...")
            print(f"\n[Truncated - {len(content) - 600} more characters available]")
        else:
            print(content)

        print("-" * 120)

    # Summary footer
    print("\n" + "=" * 120)
    print("CONTEXT SUMMARY".center(120))
    print("=" * 120)
    print(f"This context was retrieved from the uploaded PDF: {chunks_data[0]['filename']}")
    if pages_used:
        print(f"Referenced pages: {', '.join(map(str, sorted(pages_used)))}")
    print(f"Total text chunks used: {len(chunks_data)}")
    print("\nNOTE: This is the EXACT same context that the LLM sees during question generation.")
    print("=" * 120 + "\n")

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "information gain"
    show_pdf_usage(topic)
