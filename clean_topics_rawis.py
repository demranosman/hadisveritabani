"""
Konu ve ravi temizleme scripti v2 - Daha agresif normalizasyon.
"""
import re
import unicodedata
from collections import defaultdict
from db_connection import get_connection


def normalize_unicode(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# Türkçe/Arapça karakter -> ASCII
TR_TO_ASCII = str.maketrans({
    "â": "a", "Â": "A", "î": "i", "Î": "I",
    "û": "u", "Û": "U", "ê": "e", "Ê": "E",
    "ğ": "g", "Ğ": "G", "ü": "u", "Ü": "U",
    "ş": "s", "Ş": "S", "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
})


def topic_comparison_key(s: str) -> str:
    """
    Agresif konu normalizasyonu: tüm noktalama/boşlukları kaldır,
    Türkçe karakterleri ASCII'ye çevir, küçük harf.
    """
    s = normalize_unicode(s).lower().strip()
    s = s.translate(TR_TO_ASCII)
    # Sadece alfanümerik karakterleri tut (harf ve rakam)
    s = "".join(c for c in s if c.isalnum())
    return s


def ravi_comparison_key(s: str) -> str:
    """
    Agresif ravi normalizasyonu: baştaki 'Hz.' / 'Hazreti' gibi
    saygı ifadelerini kaldır, tüm noktalama/boşlukları kaldır,
    Türkçe karakterleri ASCII'ye çevir.
    """
    s = normalize_unicode(s).lower().strip()

    # Saygı ifadelerini kaldır
    s = re.sub(r"\bhz\.?\s*", "", s)
    s = re.sub(r"\bhazret(leri|i)?\s*", "", s)
    s = re.sub(r"\brad[iı]yall[aâ]hu\s*anh\s*", "", s)
    s = re.sub(r"\baleyhissal[aâ]tu\s*vessel[aâ]m\s*", "", s)
    s = re.sub(r"\bsallallahu\s*aleyhi\s*vesellem\s*", "", s)

    # Parantez içindekileri kaldır
    s = re.sub(r"\([^)]*\)", "", s)

    # Türkçe karakterleri ASCII'ye çevir
    s = s.translate(TR_TO_ASCII)

    # Sondaki noktalama ve tek harf kalıntıları
    s = re.sub(r"[\s\)\]\.\,\;\:\-]+$", "", s)
    s = re.sub(r"['\"]+$", "", s)
    s = re.sub(r"^[\s\(\[\.\,\;\:\-]+", "", s)
    # "anh", "anhuma" kalıntısı
    s = re.sub(r"anh[uma]?$", "", s)

    # Sadece alfanümerik karakterleri tut
    s = "".join(c for c in s if c.isalnum())

    return s


def ravi_display_name(raw: str) -> str:
    """
    Ravi adını temizle (gösterim için).
    """
    s = normalize_unicode(raw).strip()

    # Açıklama içeren parantezleri kaldır
    s = re.sub(
        r"\s*\([^)]*(?:rad[iı]yall[aâ]hu|aleyhi|azadl[ıi]s[ıi]|rivayet|vak[ae]|hadis|metin|par[çc]a|a[çc][ıi]klama|yukar[ıi]daki|buyurdu|hazret|sallallahu|peygamberimiz|kaydetmi[şs]|farkl[ıi]|taraf[ıi]ndan|validemiz)[^)]*\)",
        "", s, flags=re.IGNORECASE)

    # Eşleşmeyen parantezleri temizle
    s = re.sub(r"^\s*\(\s*", "", s)
    s = re.sub(r"\s*\)\s*$", "", s)

    # "radıyallâhu anhâ" kalıntıları
    s = re.sub(r"\s*anh[aâü]m?[aâ]?\s*$", "", s, flags=re.IGNORECASE)
    # Sondaki tek başına â (bitişik veya boşluklu)
    s = re.sub(r"[âü]\s*$", "", s)
    # "â)'n" kalıntısı
    s = re.sub(r"\s+[aâ]\)'n?\s*$", "", s)

    # Baş/son noktalama
    s = re.sub(r"^[\.\,\;\:\- ]+", "", s)
    s = re.sub(r"[\.\,\;\:\- ]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip()

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
    if not conflict:
        cur.execute(
            "UPDATE hadisler SET kitap_id = ?, konu_id = ? WHERE id = ?",
            (new_kitap_id, new_konu_id, hadis_id),
        )
        return

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


def clean_topics_and_rawis_v2():
    conn = get_connection()
    cur = conn.cursor()

    # ── 1. Konuları temizle ─────────────────────────────────────────
    print("=== KONU TEMİZLİĞİ ===")

    # Önce konu adlarındaki açıklamaları temizle
    cur.execute("SELECT id, ad FROM konular")
    topic_rows = cur.fetchall()
    for konu_id, ad in topic_rows:
        # "Bab başlığı olarak kaydetmiştir. Ahkâm" -> "Ahkâm"
        cleaned = re.sub(
            r"^.*(?:bab\s+ba[şs]l[ıi][ğg][ıi]\s+olarak\s+).*?\.?\s*",
            "", ad, flags=re.IGNORECASE
        )
        # Baştaki gereksiz karakterleri temizle
        cleaned = re.sub(r"^[\.\,\;\:\- ]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned and cleaned != ad:
            cur.execute("UPDATE konular SET ad = ? WHERE id = ?", (cleaned, konu_id))
    conn.commit()

    cur.execute("""
        SELECT ko.id, ko.ad, ko.kitap_id
        FROM konular ko
    """)
    all_topics = cur.fetchall()

    # Kitap bazında grupla
    topics_by_book: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for konu_id, konu_ad, kitap_id in all_topics:
        topics_by_book[kitap_id].append((konu_id, konu_ad))

    merge_count = 0
    for kitap_id, topics in topics_by_book.items():
        # comparison_key -> [(konu_id, display_name)]
        key_groups: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for konu_id, konu_ad in topics:
            display = konu_ad.strip()
            key = topic_comparison_key(display)
            if key:
                key_groups[key].append((konu_id, display))

        for key, group in key_groups.items():
            if len(group) <= 1:
                continue

            # En çok hadis olanı hedef seç
            best_id = None
            best_count = -1
            best_name = ""
            for konu_id, display in group:
                cur.execute("SELECT COUNT(*) FROM hadisler WHERE konu_id = ?", (konu_id,))
                cnt = cur.fetchone()[0]
                if cnt > best_count:
                    best_count = cnt
                    best_id = konu_id
                    best_name = display

            if best_id is None:
                continue

            # Diğerlerini hedefe taşı
            for konu_id, display in group:
                if konu_id == best_id:
                    continue
                cur.execute("SELECT id FROM hadisler WHERE konu_id = ?", (konu_id,))
                for (hid,) in cur.fetchall():
                    safe_update_hadis(cur, hid, kitap_id, best_id)
                merge_count += 1

    conn.commit()
    print(f"Birleştirilen konu grubu: {merge_count}")

    # Kullanılmayan konuları sil
    cur.execute("""
        DELETE FROM konular
        WHERE id NOT IN (SELECT DISTINCT konu_id FROM hadisler WHERE konu_id IS NOT NULL)
    """)
    print(f"Silinen kullanılmayan konu: {cur.rowcount}")

    # ── 2. Ravileri temizle ─────────────────────────────────────────
    print("\n=== RAVİ TEMİZLİĞİ ===")

    # Önce tüm ravileri temizle (display name)
    cur.execute("SELECT id, ravi FROM hadisler WHERE ravi IS NOT NULL AND ravi != ''")
    ravi_rows = cur.fetchall()

    cleaned_display = 0
    for hadis_id, ravi in ravi_rows:
        cleaned = ravi_display_name(ravi)
        if cleaned != ravi:
            cur.execute("UPDATE hadisler SET ravi = ? WHERE id = ?", (cleaned, hadis_id))
            cleaned_display += 1

    print(f"Temizlenen ravi (display): {cleaned_display}")

    # Şimdi aynı ravileri birleştir (comparison key ile)
    # Bu adımda hadisleri taşımıyoruz, sadece ravi adlarını standardize ediyoruz
    cur.execute("SELECT DISTINCT ravi FROM hadisler WHERE ravi IS NOT NULL AND ravi != ''")
    distinct_rawis = [r[0] for r in cur.fetchall()]

    # comparison_key -> en iyi display name
    ravi_groups: dict[str, list[str]] = defaultdict(list)
    for ravi in distinct_rawis:
        key = ravi_comparison_key(ravi)
        if key:
            ravi_groups[key].append(ravi)

    ravi_standard = {}
    for key, variants in ravi_groups.items():
        # En çok kullanılan variant'ı standart olarak seç
        best_variant = None
        best_count = -1
        for v in variants:
            cur.execute("SELECT COUNT(*) FROM hadisler WHERE ravi = ?", (v,))
            cnt = cur.fetchone()[0]
            if cnt > best_count:
                best_count = cnt
                best_variant = v
        if best_variant:
            for v in variants:
                if v != best_variant:
                    ravi_standard[v] = best_variant

    ravi_merge_count = 0
    for old_name, new_name in ravi_standard.items():
        cur.execute("UPDATE hadisler SET ravi = ? WHERE ravi = ?", (new_name, old_name))
        ravi_merge_count += 1

    print(f"Birleştirilen ravi varyantı: {ravi_merge_count}")

    conn.commit()

    # ── 3. Son durum ────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM konular")
    konu_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kitaplar")
    kitap_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hadisler")
    hadis_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hadisler WHERE ravi IS NULL OR ravi = ''")
    ravi_bos = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT ravi) FROM hadisler WHERE ravi IS NOT NULL AND ravi != ''")
    ravi_tekil = cur.fetchone()[0]

    print(f"\n=== SON DURUM ===")
    print(f"Kitap: {kitap_say}  |  Konu: {konu_say}  |  Hadis: {hadis_say}")
    print(f"Tekil ravi: {ravi_tekil}  |  Ravisi boş: {ravi_bos}")

    print("\n=== ÖRNEK RAVİLER (en çok hadis) ===")
    cur.execute("""
        SELECT ravi, COUNT(*) as cnt FROM hadisler
        WHERE ravi IS NOT NULL AND ravi != ''
        GROUP BY ravi ORDER BY cnt DESC LIMIT 25
    """)
    for r in cur.fetchall():
        print(f"  [{r[1]} hadis] {r[0][:80]}")

    print("\n=== ÖRNEK KONULAR (Buhârî) ===")
    cur.execute("""
        SELECT ko.ad FROM konular ko
        JOIN kitaplar k ON ko.kitap_id = k.id
        WHERE k.ad = 'Buhârî'
        ORDER BY ko.ad LIMIT 25
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}")

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    clean_topics_and_rawis_v2()