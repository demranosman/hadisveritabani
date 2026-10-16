from db_connection import get_connection


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS kitaplar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS konular (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kitap_id INTEGER NOT NULL REFERENCES kitaplar(id) ON DELETE CASCADE,
    ad TEXT NOT NULL,
    UNIQUE (kitap_id, ad)
);

CREATE TABLE IF NOT EXISTS hadisler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    genel_no INTEGER UNIQUE,
    kitap_id INTEGER REFERENCES kitaplar(id) ON DELETE CASCADE,
    konu_id INTEGER REFERENCES konular(id) ON DELETE CASCADE,
    kitap_hadis_no INTEGER,
    ravi TEXT,
    metin TEXT NOT NULL,
    ham_metin TEXT NOT NULL,
    UNIQUE (kitap_id, konu_id, kitap_hadis_no)
);

CREATE INDEX IF NOT EXISTS idx_hadisler_genel_no ON hadisler(genel_no);
CREATE INDEX IF NOT EXISTS idx_hadisler_kitap_id ON hadisler(kitap_id);
CREATE INDEX IF NOT EXISTS idx_hadisler_konu_id ON hadisler(konu_id);
CREATE INDEX IF NOT EXISTS idx_konular_kitap_id ON konular(kitap_id);
"""


def create_schema() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(CREATE_TABLES_SQL)
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    create_schema()
    print("Veritabanı şeması oluşturuldu.")