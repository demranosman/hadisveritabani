"""
Hadis veritabanı temizleme scripti (v2).
Daha agresif kitap/konu eşleştirme, kalan çöpleri Genel Kitap'a taşıma.
"""
import re
import sqlite3
from db_connection import get_connection

# ── Ana kitap varyantları (genişletilmiş) ────────────────────────────
# Her ana kitap için match fonksiyonu: isimde bu kelime geçiyorsa eşleşir
ANA_KITAP_ESLESME = [
    ("Buhârî", ["buh", "büh"]),
    ("Müslim", ["müslim", "müslim", "müslüm", "müsli", "mislim", "müislim", "müsâfir"]),
    ("Ebu Dâvud", ["davud", "dâvud", "davûd", "dvud", "dâvd", "dâvut"]),
    ("Tirmizî", ["tirmiz", "tirmîz", "tirniz", "timiz", "tirmi"]),
    ("Nesâî", ["nesâ", "nesa", "nesâî", "nese"]),
    ("İbni Mâce", ["mâce", "mace", "mâce"]),
    ("Muvatta", ["muvatta", "muvattâ"]),
]

# Tek başına sayı+konu olarak kalmış, asıl kitabı belli olmayanlar
# Bunları tespit etmek için: adı "KonuAdı Sayı" formatında olanlar
KONU_NUMARA_KALIBI = re.compile(
    r"^(.+?)\s+\d{1,4}$"
)

# Açıklama metni içeren kitap adları
ACIKLAMA_ICEREN_KALIP = re.compile(
    r"rezin|tahric|ilavesidir|rivayet|kaydetmiştir|parçadır|alınmadır",
    re.IGNORECASE,
)


def normalize_text(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[.\s,;:()\[\]'\"«»‹›„“”'•·`\-]+", "", s)
    s = re.sub(r"[.\s,;:()\[\]'\"«»‹›„“”'•·`\-]+$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_main_book(raw: str) -> str:
    """Ham kitap adından asıl kitap adını çıkar (agresif eşleştirme)."""
    s = normalize_text(raw)
    if not s:
        return ""

    s_lower = s.lower()

    # Açıklama içeriyorsa asıl kitap adını çıkarmaya çalış
    if ACIKLAMA_ICEREN_KALIP.search(s_lower):
        # Son anlamlı kitap adını bul
        for ana_isim, varyantlar in ANA_KITAP_ESLESME:
            for v in varyantlar:
                if v in s_lower:
                    return ana_isim
        # Açıklamayı temizleyip dene
        # "Hazretlerinden ) rivayet etmiştir. İbnu Mâce" -> "İbnu Mâce"
        # Son bölümü al
        parts = re.split(r"[.\n]", s)
        for part in reversed(parts):
            part = normalize_text(part)
            if part and len(part) > 2:
                for ana_isim2, varyantlar2 in ANA_KITAP_ESLESME:
                    for v2 in varyantlar2:
                        if v2 in part.lower():
                            return ana_isim2
        return ""  # bulunamazsa çöp

    # Ana kitap eşleştirmesi
    for ana_isim, varyantlar in ANA_KITAP_ESLESME:
        for v in varyantlar:
            if v in s_lower:
                # "Büyü 17" gibi konu+sayı olanları kontrol et
                # Eğer ana kitap eşleşmesi yoksa (sadece konu adı kalmış)
                return ana_isim

    # "Büyü 17", "Cenaiz 54" gibi konu+sayı formatı - kitap bilgisi yok
    if KONU_NUMARA_KALIBI.match(s):
        return ""  # çöp olarak işaretle

    # Tamamen sayısal / noktalama
    if re.match(r"^[\d\(\)\[\]\s\.\,\;\:\-]+$", s):
        return ""

    # Hiçbir şey eşleşmedi, olduğu gibi bırak
    if s:
        s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
    return s


def is_junk_book_name(name: str) -> bool:
    return bool(re.match(r"^[\d\(\)\[\]\s\.\,\;\:\-]+$", name))


def normalize_topic(raw: str) -> str:
    """Konu adını temizle."""
    s = normalize_text(raw)
    if not s:
        return "Genel Konu"

    # Virgülle ayrılmış parçalar varsa son anlamlı olanı al
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        meaningful = []
        for p in parts:
            p_clean = normalize_text(p)
            if not p_clean or re.match(r"^\d+$", p_clean):
                continue
            # Kitap adı gibi görünenleri filtrele
            is_book = False
            for _, varyant_list in ANA_KITAP_ESLESME:
                for v in varyant_list:
                    if v in p_clean.lower():
                        is_book = True
                        break
                if is_book:
                    break
            if not is_book:
                meaningful.append(p_clean)
        if meaningful:
            s = meaningful[-1]

    # Sondaki sayıları temizle (örn: "İman 158" -> "İman")
    s = re.sub(r"\s+\d+$", "", s)

    if not s or len(s) <= 1:
        return "Genel Konu"

    if s:
        s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
    return s


def safe_update_hadis(cur, hadis_id, new_kitap_id, new_konu_id):
    """Hadisin kitap_id/konu_id'sini çakışma kontrolüyle güncelle."""
    cur.execute(
        "SELECT kitap_hadis_no FROM hadisler WHERE id = ?", (hadis_id,)
    )
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


def clean_database() -> None:
    conn = get_connection()
    cur = conn.cursor()

    # ── 1. Kitap adlarını normalize et ──────────────────────────────
    cur.execute("SELECT id, ad FROM kitaplar")
    kitap_rows = cur.fetchall()

    kitap_map: dict[int, str] = {}       # id -> normalize ad
    kitap_merge: dict[str, int] = {}     # normalize_ad -> hedef_id
    kitap_junk_ids: set[int] = set()

    for kid, ad in kitap_rows:
        clean = extract_main_book(ad)
        if not clean or is_junk_book_name(clean):
            kitap_junk_ids.add(kid)
            kitap_map[kid] = ""
        else:
            kitap_map[kid] = clean

    for kid, clean in kitap_map.items():
        if clean and clean not in kitap_merge:
            kitap_merge[clean] = kid

    print(f"Kitap: {len(kitap_rows)} -> {len(kitap_merge)} normalize")
    print(f"Çöp kitap: {len(kitap_junk_ids)}")

    # Kitap adı güncellemesini merge sonrasına ertele (UNIQUE constraint)
    # Şimdilik sadece hedef id'leri belirledik

    # ── 2. Genel Kitap oluştur ──────────────────────────────────────
    cur.execute("INSERT OR IGNORE INTO kitaplar (ad) VALUES (?)", ("Genel Kitap",))
    cur.execute("SELECT id FROM kitaplar WHERE ad = 'Genel Kitap'")
    genel_kitap_id = cur.fetchone()[0]

    # ── 3. Çöp kitapları Genel Kitap'a taşı ────────────────────────
    junk_konu_map: dict[int, int] = {}  # eski_konu_id -> yeni_konu_id (Genel Kitap altında)

    for junk_id in kitap_junk_ids:
        cur.execute("SELECT id, ad FROM konular WHERE kitap_id = ?", (junk_id,))
        for konu_id, konu_ad in cur.fetchall():
            if konu_id in junk_konu_map:
                continue
            norm_ad = normalize_topic(konu_ad)
            cur.execute(
                "SELECT id FROM konular WHERE kitap_id = ? AND ad = ?",
                (genel_kitap_id, norm_ad),
            )
            existing = cur.fetchone()
            if existing:
                junk_konu_map[konu_id] = existing[0]
            else:
                cur.execute(
                    "INSERT INTO konular (kitap_id, ad) VALUES (?, ?)",
                    (genel_kitap_id, norm_ad),
                )
                junk_konu_map[konu_id] = cur.lastrowid

        # Hadisleri taşı
        cur.execute("SELECT id, konu_id FROM hadisler WHERE kitap_id = ?", (junk_id,))
        for hid, konu_id in cur.fetchall():
            new_konu_id = junk_konu_map.get(konu_id, konu_id)
            safe_update_hadis(cur, hid, genel_kitap_id, new_konu_id)

    conn.commit()

    # ── 4. Benzer kitap isimlerini birleştir ────────────────────────
    for clean_name, target_id in kitap_merge.items():
        same_name_ids = [
            kid for kid, cname in kitap_map.items()
            if cname == clean_name and kid != target_id
        ]
        for old_id in same_name_ids:
            cur.execute("SELECT id, ad FROM konular WHERE kitap_id = ?", (old_id,))
            for konu_id, konu_ad in cur.fetchall():
                norm_ad = normalize_topic(konu_ad)
                cur.execute(
                    "SELECT id FROM konular WHERE kitap_id = ? AND ad = ?",
                    (target_id, norm_ad),
                )
                existing = cur.fetchone()
                if existing:
                    new_konu_id = existing[0]
                else:
                    cur.execute(
                        "INSERT INTO konular (kitap_id, ad) VALUES (?, ?)",
                        (target_id, norm_ad),
                    )
                    new_konu_id = cur.lastrowid

                cur.execute("SELECT id FROM hadisler WHERE konu_id = ?", (konu_id,))
                for (hid,) in cur.fetchall():
                    safe_update_hadis(cur, hid, target_id, new_konu_id)

    conn.commit()

    # Merge edilen kitapların adlarını geçici olarak değiştir (UNIQUE çakışmasını önle)
    for clean_name, target_id in kitap_merge.items():
        same_name_ids = [
            kid for kid, cname in kitap_map.items()
            if cname == clean_name and kid != target_id
        ]
        for old_id in same_name_ids:
            cur.execute(
                "UPDATE kitaplar SET ad = ? WHERE id = ?",
                (f"_merged_{old_id}", old_id),
            )

    # ── 4.5 Kitap adlarını güncelle ─
    for clean_name, target_id in kitap_merge.items():
        # Önce bu isimde başka bir kitap var mı kontrol et
        cur.execute(
            "SELECT id FROM kitaplar WHERE ad = ? AND id != ?",
            (clean_name, target_id),
        )
        conflict = cur.fetchone()
        if conflict:
            # Çakışan kitabı merge edilmiş olarak işaretle (adını değiştir)
            cur.execute(
                "UPDATE kitaplar SET ad = ? WHERE id = ?",
                (f"_merged_{conflict[0]}", conflict[0]),
            )
        cur.execute(
            "UPDATE kitaplar SET ad = ? WHERE id = ?",
            (clean_name, target_id),
        )
    conn.commit()

    # ── 5. Tüm konu adlarını normalize et ──────────────────────────
    cur.execute("SELECT id, ad FROM konular")
    for konu_id, ad in cur.fetchall():
        norm_ad = normalize_topic(ad)
        if norm_ad != ad:
            cur.execute("SELECT kitap_id FROM konular WHERE id = ?", (konu_id,))
            kitap_id = cur.fetchone()[0]
            cur.execute(
                "SELECT id FROM konular WHERE kitap_id = ? AND ad = ? AND id != ?",
                (kitap_id, norm_ad, konu_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("SELECT id FROM hadisler WHERE konu_id = ?", (konu_id,))
                for (hid,) in cur.fetchall():
                    safe_update_hadis(cur, hid, kitap_id, existing[0])
            else:
                cur.execute("UPDATE konular SET ad = ? WHERE id = ?", (norm_ad, konu_id))

    conn.commit()

    # ── 6. Kullanılmayanları sil ────────────────────────────────────
    cur.execute("""
        DELETE FROM konular
        WHERE id NOT IN (SELECT DISTINCT konu_id FROM hadisler WHERE konu_id IS NOT NULL)
    """)
    deleted_topics = cur.rowcount

    cur.execute("""
        DELETE FROM kitaplar
        WHERE id NOT IN (SELECT DISTINCT kitap_id FROM hadisler WHERE kitap_id IS NOT NULL)
    """)
    deleted_books = cur.rowcount

    print(f"Silinen kullanılmayan kitap: {deleted_books}, konu: {deleted_topics}")

    conn.commit()

    # ── 7. Son durum ────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM kitaplar")
    kitap_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM konular")
    konu_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hadisler")
    hadis_say = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hadisler WHERE ravi IS NULL OR ravi = ''")
    ravi_bos = cur.fetchone()[0]

    print(f"\n=== TEMİZLİK SONRASI ===")
    print(f"Kitap: {kitap_say}  |  Konu: {konu_say}  |  Hadis: {hadis_say}")
    print(f"Ravisi boş hadis: {ravi_bos}")

    print("\n=== KİTAPLAR (hadis sayısına göre) ===")
    cur.execute("""
        SELECT k.ad, COUNT(*) as cnt
        FROM kitaplar k JOIN hadisler h ON h.kitap_id = k.id
        GROUP BY k.ad ORDER BY cnt DESC
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]} hadis")

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    clean_database()