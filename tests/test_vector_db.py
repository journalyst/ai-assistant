from src.vector_db.journal_store import JournalStore

def test_journal_search():
    results = JournalStore.search_journals(user_id=1, query_text="", limit=3)
    assert len(results) > 0
    print(f"✓ Found {len(results)} relevant journals")
    for r in results:
        print(f"  - Score: {r['score']:.3f} | {r['text'][:60]}...")