"""
Son rötuş v2: Küçük kitapları büyük kitaplara fuzzy-match ile bağla,
eşleşemeyenleri Genel Kitap'a taşı.
"""
import unicodedata
from db_connection import get_connection


BIG_BOOKS = [
    "Buhârî", "Müslim", "Ebu Dâvud", "Tirmizî", "Nesâî",
    "İbni Mâce", "Muvatta", "Genel Kitap", "Tefsir",
]


def normalize_unicode(s: str) -> str:
    """Tüm Unicode karakterleri NFC formuna normalize et."""
    return unicodedata.normalize("NFC", s)


def fuzzy_key(s: str) -> str:
    """Türkçe karakterleri latin eşdeğerine çevir, küçük harf yap, boşlukları sil."""
    s = normalize_unicode(s).lower()
    # Türkçe -> ASCII dönüşümü
    tr_to_ascii = {
        "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u",
        "ş": "s", "Ş": "s",
        "ı": "i", "İ": "i",
        "ö": "o", "Ö": "o",
        "ç": "c", "Ç": "c",
        "â": "a", "Â": "a",
        "û": "u", "Û": "u",
        "î": "i", "Î": "i",
        "ê": "e",
    }
    for tr_char, asc in tr_to_ascii.items():
        s = s.replace(tr_char, asc)
    # Sadece alfanümerik karakterleri tut
    s = "".join(c for c in s if c.isalnum())
    return s


def safe_update_hadis(cur, hadis_id, new_kitap_id, new_konu_id):
    cur.execute("SELECT kitap_hadis_no FROM hadisler WHERE id = ?", (hadis_id,))
    row = cur.fetchone()
    if not row:
        return
    hadis_no = row[0]

    cur.execute(
        """SELECT id FROM hadisler
        WHERE kitap_id = ? AND konu_id = ? AND kitap_hadis_no = ? AND id != ?""",
        (new_kitap_id, new_konu_id, hadis_no, hadis_id),
    )
    conflict = cur.fetchone()

    if conflict:
        new_no = hadis_no + 1000000
        cur.execute(
            """SELECT id FROM hadisler
            WHERE kitap_id = ? AND konu_id = ? AND kitap_hadis_no = ? AND id != ?""",
            (new_kitap_id, new_konu_id, new_no, hadis_id),
        )
        while cur.fetchone():
            new_no += 1000000
            cur.execute(
                """SELECT id FROM hadisler
                WHERE kitap_id = ? AND konu_id = ? AND kitap_hadis_no = ? AND id != ?""",
                (new_kitap_id, new_konu_id, new_no, hadis_id),
            )
        cur.execute(
            "UPDATE hadisler SET kitap_id = ?, konu_id = ?, kitap_hadis_no = ? WHERE id = ?",
            (new_kitap_id, new_konu_id, new_no, hadis_id),
        )
    else:
        cur.execute(
            "UPDATE hadisler SET kitap_id = ?, konu_id = ? WHERE id = ?",
            (new_kitap_id, new_konu_id, hadis_id),
        )


def final_cleanup_v2():
    conn = get_connection()
    cur = conn.cursor()

    # Büyük kitapların fuzzy key'lerini oluştur
    big_book_map = {}  # fuzzy_key -> (id, gerçek_ad)
    for book_name in BIG_BOOKS:
        cur.execute("SELECT id FROM kitaplar WHERE ad = ?", (book_name,))
        row = cur.fetchone()
        if row:
            big_book_map[fuzzy_key(book_name)] = (row[0], book_name)

    # Genel Kitap id'si
    cur.execute("SELECT id FROM kitaplar WHERE ad = 'Genel Kitap'")
    genel_kitap_id = cur.fetchone()[0]

    # Tüm küçük kitapları tara (büyük kitaplar listesinde olmayanlar)
    cur.execute("SELECT id, ad FROM kitaplar")
    all_books = cur.fetchall()

    book_to_target: dict[int, int] = {}

    for book_id, book_name in all_books:
        norm_name = normalize_unicode(book_name)

        # Büyük kitaplardan biri mi?
        if norm_name in BIG_BOOKS:
            continue
        if book_id == genel_kitap_id:
            continue

        fkey = fuzzy_key(book_name)

        # Büyük kitaplarla fuzzy eşleştirme dene
        best_match = None
        for bk_fkey, (bk_id, bk_name) in big_book_map.items():
            if bk_id == book_id:
                continue
            # En az 2 karakterlik ortak substring ara
            if len(fkey) >= 3 and len(bk_fkey) >= 3:
                # En uzun ortak substring
                common = 0
                for i in range(len(fkey)):
                    for j in range(i + 2, len(fkey) + 1):
                        if fkey[i:j] in bk_fkey:
                            common = max(common, j - i)
                if common >= 3:
                    book_to_target[book_id] = bk_id
                    print(f"  '{book_name}' -> '{bk_name}' (ortak: {common} kar.)")
                    break

        # Eşleşme yoksa ve küçükse Genel Kitap'a taşı
        if book_id not in book_to_target:
            # Bu kitaba bağlı hadis sayısını kontrol et
            cur.execute("SELECT COUNT(*) FROM hadisler WHERE kitap_id = ?", (book_id,))
            hadis_count = cur.fetchone()[0]
            if hadis_count <= 10:
                book_to_target[book_id] = genel_kitap_id
                print(f"  '{book_name}' ({hadis_count} hadis) -> Genel Kitap")
            else:
                print(f"  '{book_name}' ({hadis_count} hadis) -> EŞLEŞME BULUNAMADI (korunuyor)")

    print(f"\nToplam taşınacak: {len(book_to_target)} kitap")

    # ── Birleştirme ──────────────────────────────────────────────────
    for old_id, target_id in book_to_target.items():
        cur.execute("SELECT id, ad FROM konular WHERE kitap_id = ?", (old_id,))
        for konu_id, konu_ad in cur.fetchall():
            cur.execute(
                "SELECT id FROM konular WHERE kitap_id = ? AND ad = ?",
                (target_id, konu_ad),
            )
            existing = cur.fetchone()
            if existing:
                new_konu_id = existing[0]
            else:
                cur.execute(
                    "INSERT INTO konular (kitap_id, ad) VALUES (?, ?)",
                    (target_id, konu_ad),
                )
                new_konu_id = cur.lastrowid

            cur.execute("SELECT id FROM hadisler WHERE konu_id = ?", (konu_id,))
            for (hid,) in cur.fetchall():
                safe_update_hadis(cur, hid, target_id, new_konu_id)

    conn.commit()

    # ── Temizlik ─────────────────────────────────────────────────────
    cur.execute("""
        DELETE FROM konular
        WHERE id NOT IN (SELECT DISTINCT konu_id FROM hadisler WHERE konu_id IS NOT NULL)
    """)
    cur.execute("""
        DELETE FROM kitaplar
        WHERE id NOT IN (SELECT DISTINCT kitap_id FROM hadisler WHERE kitap_id IS NOT NULL)
    """)
    conn.commit()

    # ── Son durum ────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM kitaplar")
    kitap_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM konular")
    konu_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hadisler")
    hadis_say = cur.fetchone()[0]

    print(f"\n=== SON DURUM ===")
    print(f"Kitap: {kitap_say}  |  Konu: {konu_say}  |  Hadis: {hadis_say}")

    print("\n=== KİTAPLAR ===")
    cur.execute("""
        SELECT k.ad, COUNT(*) as cnt
        FROM kitaplar k JOIN hadisler h ON h.kitap_id = k.id
        GROUP BY k.ad ORDER BY cnt DESC
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]} hadis")

    cur.close()
    conn.close()


if __name__ == "__main__":
    final_cleanup_v2()