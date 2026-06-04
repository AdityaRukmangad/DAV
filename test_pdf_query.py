from app.rag import get_rag_engine

engine = get_rag_engine()
db = engine.vector_store.get_database()

if db:
    docs = db.similarity_search('machine learning', k=5)
    print(f"Found {len(docs)} docs\n")
    
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get('source', 'NO SOURCE')
        print(f"{i}. Source: {source}")
        print(f"   Preview: {doc.page_content[:100]}...\n")
else:
    print("No database available")
