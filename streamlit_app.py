import streamlit as st
from db_connection import get_connection


st.set_page_config(page_title="Hadis Analiz", layout="wide")
st.title("Hadis Analiz ve Kontrol")


@st.cache_data(ttl=60)
def get_books():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT ad FROM kitaplar ORDER BY ad")
    kitaplar = [r[0] for r in cur.fetchall()]

    cur.close()
    conn.close()
    return kitaplar


@st.cache_data(ttl=60)
def get_topics_for_book(kitap):
    conn = get_connection()
    cur = conn.cursor()

    if kitap == "Tümü":
        cur.execute(
            """
            SELECT DISTINCT ko.ad
            FROM konular ko
            JOIN hadisler h ON h.konu_id = ko.id
            ORDER BY ko.ad
            """
        )
    else:
        cur.execute(
            """
            SELECT DISTINCT ko.ad
            FROM konular ko
            JOIN hadisler h ON h.konu_id = ko.id
            JOIN kitaplar k ON h.kitap_id = k.id
            WHERE k.ad = %s
            ORDER BY ko.ad
            """,
            (kitap,),
        )

    konular = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return konular


@st.cache_data(ttl=60)
def get_books_for_topic(konu):
    conn = get_connection()
    cur = conn.cursor()

    if konu == "Tümü":
        cur.execute(
            """
            SELECT DISTINCT k.ad
            FROM kitaplar k
            JOIN hadisler h ON h.kitap_id = k.id
            ORDER BY k.ad
            """
        )
    else:
        cur.execute(
            """
            SELECT DISTINCT k.ad
            FROM kitaplar k
            JOIN hadisler h ON h.kitap_id = k.id
            JOIN konular ko ON h.konu_id = ko.id
            WHERE ko.ad = %s
            ORDER BY k.ad
            """,
            (konu,),
        )

    kitaplar = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return kitaplar


def run_query(kitap, konu, arama, limit):
    conn = get_connection()
    cur = conn.cursor()

    where_clauses = []
    params = []

    if kitap != "Tümü":
        where_clauses.append("k.ad = %s")
        params.append(kitap)

    if konu != "Tümü":
        where_clauses.append("ko.ad = %s")
        params.append(konu)

    if arama:
        where_clauses.append("(h.metin ILIKE %s OR h.ravi ILIKE %s)")
        like = f"%{arama}%"
        params.extend([like, like])

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    query = f"""
        SELECT
            h.id,
            h.genel_no,
            k.ad AS kitap,
            ko.ad AS konu,
            h.kitap_hadis_no,
            h.ravi,
            h.metin
        FROM hadisler h
        LEFT JOIN kitaplar k ON h.kitap_id = k.id
        LEFT JOIN konular ko ON h.konu_id = ko.id
        {where_sql}
        ORDER BY h.genel_no
        LIMIT %s
    """
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    cur.close()
    conn.close()

    return columns, rows


def get_summary_stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM hadisler")
    toplam_hadis = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM kitaplar")
    toplam_kitap = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM konular")
    toplam_konu = cur.fetchone()[0]

    cur.close()
    conn.close()

    return toplam_hadis, toplam_kitap, toplam_konu


kitaplar = get_books()
toplam_hadis, toplam_kitap, toplam_konu = get_summary_stats()

col1, col2, col3 = st.columns(3)
col1.metric("Toplam Hadis", toplam_hadis)
col2.metric("Toplam Kitap", toplam_kitap)
col3.metric("Toplam Konu", toplam_konu)

with st.sidebar:
    st.header("Filtreler")
    if "secili_kitap" not in st.session_state:
        st.session_state.secili_kitap = "Tümü"
    if "secili_konu" not in st.session_state:
        st.session_state.secili_konu = "Tümü"

    kitap_ops = ["Tümü", *get_books_for_topic(st.session_state.secili_konu)]
    if st.session_state.secili_kitap not in kitap_ops:
        st.session_state.secili_kitap = "Tümü"

    secili_kitap = st.selectbox("Kitap", kitap_ops, key="secili_kitap")

    konu_ops = ["Tümü", *get_topics_for_book(secili_kitap)]
    if st.session_state.secili_konu not in konu_ops:
        st.session_state.secili_konu = "Tümü"

    secili_konu = st.selectbox("Konu", konu_ops, key="secili_konu")
    arama = st.text_input("Metin / Ravi Ara")
    limit = st.slider("Gösterilecek kayıt", min_value=50, max_value=5000, value=500, step=50)

columns, rows = run_query(secili_kitap, secili_konu, arama, limit)

st.subheader(f"Kayıtlar ({len(rows)})")

if not rows:
    st.info("Bu filtreye uygun kayıt bulunamadı.")
else:
    view_data = []
    for row in rows:
        d = dict(zip(columns, row))
        view_data.append(
            {
                "genel_no": d["genel_no"],
                "kitap": d["kitap"],
                "konu": d["konu"],
                "kitap_hadis_no": d["kitap_hadis_no"],
                "ravi": d["ravi"],
                "metin_ozet": (d["metin"][:160] + "...") if d["metin"] and len(d["metin"]) > 160 else d["metin"],
            }
        )

    st.dataframe(view_data, use_container_width=True, hide_index=True)

    st.markdown("### Hadis Detay")
    secili_satir_index = st.selectbox(
        "Detay için hadis seçin",
        options=list(range(len(rows))),
        format_func=lambda i: f"genel_no={rows[i][1]} | {rows[i][2]} | {rows[i][3]} | no={rows[i][4]}",
    )
    detay = rows[secili_satir_index] if rows else None

    if detay:
        detay_dict = dict(zip(columns, detay))
        st.write(f"**Kitap:** {detay_dict['kitap']}  ")
        st.write(f"**Konu:** {detay_dict['konu']}  ")
        st.write(f"**Kitap Hadis No:** {detay_dict['kitap_hadis_no']}  ")
        st.write(f"**Ravi:** {detay_dict['ravi']}  ")
        st.text_area("Hadis Metni", value=detay_dict["metin"] or "", height=280)