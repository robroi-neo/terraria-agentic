import sqlite3
from typing import List, Dict, Any

DB_PATH = "cleaned_articles.db"
TABLE_NAME = "articles"


# SQLITE LOADER, CHROMA DB LOADER CAN BE FOUND IN INDEXER
def load_articles_from_db(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT pageid, title, category, source_url, cleaned_text
        FROM {TABLE_NAME}
    """)

    rows = cursor.fetchall()
    conn.close()

    articles = []
    for row in rows:
        articles.append({
            "pageid": row["pageid"],
            "title": row["title"],
            "category": row["category"],
            "source_url": row["source_url"],
            "cleaned_text": row["cleaned_text"],
        })

    return articles

if __name__ == "__main__":
    db = load_articles_from_db()

    if db:
        print("Database Loaded Succesfully!")
