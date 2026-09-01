from db_connection import get_connection


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS kitaplar (
    id SERIAL PRIMARY KEY,
    ad VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS konular (
    id SERIAL PRIMARY KEY,
    kitap_id INTEGER NOT NULL REFERENCES kitaplar(id) ON DELETE CASCADE,
    ad VARCHAR(200) NOT NULL,
    UNIQUE (kitap_id, ad)
);

CREATE TABLE IF NOT EXISTS hadisler (
    id BIGSERIAL PRIMARY KEY,
    genel_no INTEGER UNIQUE,
    kitap_id INTEGER REFERENCES kitaplar(id) ON DELETE CASCADE,
    konu_id INTEGER REFERENCES konular(id) ON DELETE CASCADE,
    kitap_hadis_no INTEGER,
    ravi TEXT,
    metin TEXT NOT NULL,
    ham_metin TEXT NOT NULL
);

ALTER TABLE hadisler ADD COLUMN IF NOT EXISTS genel_no INTEGER;
ALTER TABLE hadisler ADD COLUMN IF NOT EXISTS kitap_id INTEGER;
ALTER TABLE hadisler ADD COLUMN IF NOT EXISTS konu_id INTEGER;
ALTER TABLE hadisler ADD COLUMN IF NOT EXISTS kitap_hadis_no INTEGER;
ALTER TABLE hadisler ADD COLUMN IF NOT EXISTS ravi TEXT;
ALTER TABLE hadisler ALTER COLUMN ravi TYPE TEXT;
ALTER TABLE hadisler ADD COLUMN IF NOT EXISTS metin TEXT;
ALTER TABLE hadisler ADD COLUMN IF NOT EXISTS ham_metin TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hadisler_kitap_id_fkey'
    ) THEN
        ALTER TABLE hadisler
        ADD CONSTRAINT hadisler_kitap_id_fkey
        FOREIGN KEY (kitap_id) REFERENCES kitaplar(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hadisler_konu_id_fkey'
    ) THEN
        ALTER TABLE hadisler
        ADD CONSTRAINT hadisler_konu_id_fkey
        FOREIGN KEY (konu_id) REFERENCES konular(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hadisler_genel_no_key'
    ) THEN
        ALTER TABLE hadisler
        ADD CONSTRAINT hadisler_genel_no_key UNIQUE (genel_no);
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hadisler_kitap_hadis_no_key'
    ) THEN
        ALTER TABLE hadisler DROP CONSTRAINT hadisler_kitap_hadis_no_key;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hadisler_kitap_konu_hadis_no_key'
    ) THEN
        ALTER TABLE hadisler
        ADD CONSTRAINT hadisler_kitap_konu_hadis_no_key
        UNIQUE (kitap_id, konu_id, kitap_hadis_no);
    END IF;
END $$;
"""


def create_schema() -> None:
    conn = get_connection()

    cur = conn.cursor()
    cur.execute(CREATE_TABLES_SQL)
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    create_schema()
    print("Veritabanı şeması oluşturuldu.")