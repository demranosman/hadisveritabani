import os
import re
import json
from bs4 import BeautifulSoup

KLASOR = "hadis_html_dosya"   # chm extract edilen klasör
CIKTI = "hadisler.json"

KAYNAK_KITAP_IPUCLARI = [
    "buhari",
    "muslim",
    "tirmizi",
    "ebu davud",
    "ebu dâvud",
    "nesai",
    "muvatta",
    "ibnu mace",
    "ibn mace",
    "darimi",
    "ahmed",
]


def normalize_metin(metin):
    ceviri = str.maketrans({
        "â": "a", "Â": "A", "î": "i", "Î": "I", "û": "u", "Û": "U",
        "ı": "i", "İ": "I", "ö": "o", "Ö": "O", "ü": "u", "Ü": "U",
        "ş": "s", "Ş": "S", "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G",
    })
    metin = metin.translate(ceviri)
    metin = metin.replace("’", "'").replace("`", "'")
    return metin.lower()


def kaynak_satiri_bul(icerik):
    satirlar = [s.strip() for s in icerik.splitlines() if s.strip()]
    adaylar = []

    for satir in satirlar:
        if "," not in satir or not re.search(r"\d", satir):
            continue

        norm = normalize_metin(satir)
        if ";" in satir or any(ipucu in norm for ipucu in KAYNAK_KITAP_IPUCLARI):
            adaylar.append(satir)

    if not adaylar:
        return None

    return " ; ".join(adaylar)


def ravi_cek(metin):
    satir = metin.strip().replace("\n", " ")
    satir = re.sub(r"\s+", " ", satir)
    satir = re.sub(r"^Yine\s+", "", satir, flags=re.IGNORECASE)

    fiiller = [
        "anlattığına göre",
        "rivayetine göre",
        "rivayete göre",
        "anlatıyor",
        "anlattı",
        "haber veriyor",
        "haber verdi",
        "rivayet etti",
        "rivayet ediyor",
        "rivayet olunur",
        "naklen",
        "naklediyor",
        "diyor ki",
        "dedi ki",
        "demiştir ki",
        "demiştir",
        "der ki",
        "söyledi",
        "söylemiştir",
    ]

    satir_kucuk = satir.lower()
    en_erken_indeks = None

    for fiil in fiiller:
        eslesme = re.search(rf"\b{re.escape(fiil)}\b", satir_kucuk)
        if eslesme:
            idx = eslesme.start()
            if en_erken_indeks is None or idx < en_erken_indeks:
                en_erken_indeks = idx

    if en_erken_indeks is None or en_erken_indeks <= 0:
        return None

    on_parca = satir[:en_erken_indeks].strip(" \"'.,:-")
    on_parca = re.sub(r"\s+", " ", on_parca)
    on_parca = re.sub(r"\bhazretleri\b", "", on_parca, flags=re.IGNORECASE).strip(" \"'.,:-")
    on_parca = re.sub(r"'?[ıiuü]n$", "", on_parca, flags=re.IGNORECASE).strip()

    zevce_eslesme = re.search(r"zevcelerinden\s+([^,:\"“”]+)", on_parca, flags=re.IGNORECASE)
    if zevce_eslesme:
        on_parca = zevce_eslesme.group(1).strip()

    on_parca = re.split(
        r"\s+(?:babas[ıiuü](?:n[ıiuü])?|tarikiyle|ceddi|dedesinden|ashab[ıiuü]ndan|"
        r"zevcelerinden|bir\s+başka\s+rivayette|birinden|naklen|şunu|şöyle|d[ae]n|d[ae])\b",
        on_parca,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    if not on_parca:
        return None

    zincir_bol = re.split(r"\s+ve\s+|\s*,\s*", on_parca, maxsplit=1, flags=re.IGNORECASE)
    ravi = zincir_bol[0].strip(" \"'.,:-") if zincir_bol else on_parca
    ravi = re.sub(r"\b(?:d|de|dem|deme|an|anl)\b$", "", ravi, flags=re.IGNORECASE).strip()
    ravi = re.split(
        r"\s+(?:babas[ıiuü](?:n[ıiuü])?|tarikiyle|ceddi|dedesinden|ashab[ıiuü]ndan|"
        r"zevcelerinden|bir\s+başka\s+rivayette|birinden|naklen|şunu|şöyle|"
        r"demektedir|demekte|rivayet|resulullah|resûlullah|d[ae]n|d[ae])\b",
        ravi,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    ravi = re.split(r"\s+res.?lullah\b", ravi, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    ravi = re.split(r"\s+Hz\.\s*", ravi, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    ravi = re.split(r"(?:'|’)d[ae]n\b", ravi, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    ravi = re.split(r"\s+'?d[ae]\b", ravi, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    ravi = re.sub(r"\b(?:anla|anlat|riv|rivayet|deme|demek|s[öo]yle)\w*$", "", ravi, flags=re.IGNORECASE).strip()
    ravi = re.sub(r"\s+anla.?$", "", ravi, flags=re.IGNORECASE).strip()
    ravi = re.sub(r"\s+[a-zçğıöşü]$", "", ravi, flags=re.IGNORECASE)
    ravi = re.sub(r"(?:['’`])(?:[ıiuü]n|[ıiuü]m[ae]?|[dt][ae]n|[dt][ae]|n[ıiuü]n)$", "", ravi, flags=re.IGNORECASE).strip()
    ravi = re.sub(r"(?:nın|nin|nun|nün|dan|den|tan|ten)$", "", ravi, flags=re.IGNORECASE).strip()
    ravi = re.sub(
        r"\(?\s*(?:"
        r"rad.?yallahu\s+anh(?:a|u|uma|üm[ae]?)?"
        r"|kerremallahu\s+vechehu"
        r"|rah(?:i|î)?mehullah"
        r"|aleyhissel[âa]m"
        r")\s*\)?",
        "",
        ravi,
        flags=re.IGNORECASE,
    ).strip()
    ravi = re.sub(r"\(\s*\)", "", ravi)
    ravi = re.sub(r"\s{2,}", " ", ravi).strip(" ,;:-")
    ravi = re.sub(r"\s+", " ", ravi)

    if re.search(r"[:\"“”]", ravi):
        return None

    if re.search(r"\b(diyor|demektedir|riv[aâ]yeti|anlat[ıi]ld[ıi][ğg][ıi]na|iken|g[öo]re|ş[öo]yle|taraf[ıi]ndan|hutbe|minberden)\b", ravi, flags=re.IGNORECASE):
        return None

    if re.search(r"res.?lullah", ravi, flags=re.IGNORECASE):
        return None

    norm_ravi = normalize_metin(ravi)

    if re.search(r"\b(bir\s+di.?er|rivayetinde|rivayette|muellif|kaydettigi|yukaridaki\s+rivayet)\b", norm_ravi, flags=re.IGNORECASE):
        return None

    if norm_ravi.startswith("bir ") or " bir di" in norm_ravi:
        return None

    kelime_sayisi = len(ravi.split())
    if kelime_sayisi < 1 or kelime_sayisi > 14:
        return None

    if len(ravi) > 60:
        return None

    if "Hz. Peygamber" in ravi or "Resulullah" in ravi or "Resûlullah" in ravi:
        return None

    return ravi or None

def kitap_konu_parcala(kaynak_satiri):
    """
    Örnek:
    Buhârî, Enbiya 47; Müslim, İman 46, (28)
    """
    kayitlar = []

    parcalar = kaynak_satiri.split(";")

    for parca in parcalar:
        parca = parca.strip()

        # Parantez içi gereksiz sayıları sil
        parca = re.sub(r"\(.*?\)", "", parca)

        eslesme = re.search(r"([^,;:\n]{2,80}),\s*([^\d;:\n]{1,100}?)\s*(\d{1,4})\b", parca)
        if eslesme:
            kitap = eslesme.group(1).strip()
            konu = eslesme.group(2).strip()
            hadis_no = int(eslesme.group(3))

            kayitlar.append({
                "kitap": kitap,
                "konu": konu,
                "hadis_no": hadis_no
            })

    return kayitlar


tum_kayitlar = []
genel_sayac = 1

for dosya in os.listdir(KLASOR):
    if not dosya.endswith(".htm") and not dosya.endswith(".html"):
        continue

    yol = os.path.join(KLASOR, dosya)

    with open(yol, encoding="windows-1254", errors="ignore") as f:
        soup = BeautifulSoup(f, "html.parser")
        metin = soup.get_text("\n")

    # Hadis bloklarını böl
    hadis_bloklari = re.split(r"\n\s*(\d+)\s*-\s*", metin)

    for i in range(1, len(hadis_bloklari), 2):
        sira_no = hadis_bloklari[i]
        icerik = hadis_bloklari[i+1]

        # Kaynak satırını bul
        kaynak_satiri = kaynak_satiri_bul(icerik)
        if not kaynak_satiri:
            continue

        # Metinden kaynak kısmını çıkar
        metin_temiz = icerik.replace(kaynak_satiri, "").strip()
        ravi = ravi_cek(metin_temiz)

        kaynaklar = kitap_konu_parcala(kaynak_satiri)

        for k in kaynaklar:
            tum_kayitlar.append({
                "genel_no": genel_sayac,
                "kitap": k["kitap"],
                "konu": k["konu"],
                "hadis_no": k["hadis_no"],
                "kitap_hadis_no": int(sira_no),
                "kitap_ad": k["kitap"],
                "konu_ad": k["konu"],
                "ravi": ravi,
                "metin": metin_temiz.strip(),
                "ham_metin": icerik.strip()
            })
            genel_sayac += 1

with open(CIKTI, "w", encoding="utf-8") as f:
    json.dump(tum_kayitlar, f, ensure_ascii=False, indent=2)

print("JSON üretildi:", CIKTI)