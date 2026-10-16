import json
import re
import os
from db_connection import get_connection

conn = get_connection()

cur = conn.cursor()


def get_or_create_kitap_id(kitap_ad):
    cur.execute(
        "INSERT OR IGNORE INTO kitaplar (ad) VALUES (?)",
        (kitap_ad,),
    )
    cur.execute("SELECT id FROM kitaplar WHERE ad = ?", (kitap_ad,))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Kitap ID alınamadı: {kitap_ad}")
    return row[0]


def get_or_create_konu_id(kitap_id, konu_ad):
    cur.execute(
        "INSERT OR IGNORE INTO konular (kitap_id, ad) VALUES (?, ?)",
        (kitap_id, konu_ad),
    )
    cur.execute(
        "SELECT id FROM konular WHERE kitap_id = ? AND ad = ?",
        (kitap_id, konu_ad),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Konu ID alınamadı: {konu_ad}")
    return row[0]


input_json = os.getenv("INPUT_JSON", "hadisler.json")

with open(input_json, encoding="utf-8") as f:
    veriler = json.load(f)


def ravi_kalite_kontrol(kayitlar):
    if os.getenv("SKIP_RAVI_QUALITY") == "1":
        return

    supheli = []
    kalip = r"(?:'|’)(?:ın|in|un|ün|dan|den|tan|ten)$|(?:'|’)[^\s]{1,4}$|\b(diyor|demektedir|şöyle|rivayet|anlatıldı|tarafından|minberden|hutbe)\b"

    for kayit in kayitlar:
        ravi = (kayit.get("ravi") or "").strip()
        if not ravi:
            continue

        if len(ravi) > 60 or re.search(kalip, ravi, flags=re.IGNORECASE):
            supheli.append((kayit.get("genel_no"), ravi))
            if len(supheli) >= 10:
                break

    if supheli:
        ornekler = "\n".join([f"- genel_no={no}, ravi={r}" for no, r in supheli])
        raise RuntimeError(
            "Ravi kalite kontrolü başarısız. JSON netleşmeden SQL aktarımı durduruldu.\n"
            "Şüpheli ravi örnekleri:\n"
            f"{ornekler}"
        )


ravi_kalite_kontrol(veriler)

for index, kayit in enumerate(veriler, start=1):
    genel_no = kayit.get("genel_no") or index
    kitap_ad = kayit.get("kitap_ad") or kayit.get("kitap") or "Genel Kitap"
    konu_ad = kayit.get("konu_ad") or kayit.get("konu") or "Genel Konu"
    kitap_hadis_no = kayit.get("kitap_hadis_no") or kayit.get("hadis_no") or genel_no
    metin = kayit.get("metin") or kayit.get("ham_metin") or ""
    ham_metin = kayit.get("ham_metin") or metin
    ravi = kayit.get("ravi")

    kitap_id = get_or_create_kitap_id(kitap_ad)
    konu_id = get_or_create_konu_id(kitap_id, konu_ad)

    cur.execute(
        """
        INSERT INTO hadisler (genel_no, kitap_id, konu_id, kitap_hadis_no, ravi, metin, ham_metin)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (kitap_id, konu_id, kitap_hadis_no) DO UPDATE SET
            genel_no = EXCLUDED.genel_no,
            ravi = EXCLUDED.ravi,
            metin = EXCLUDED.metin,
            ham_metin = EXCLUDED.ham_metin
        """,
        (
            genel_no,
            kitap_id,
            konu_id,
            kitap_hadis_no,
            ravi,
            metin,
            ham_metin,
        ),
    )

conn.commit()
cur.close()
conn.close()