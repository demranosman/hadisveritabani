import streamlit as st
from db_connection import get_connection


st.set_page_config(page_title="Hadis Analiz", layout="wide", initial_sidebar_state="expanded")

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

toplam_hadis, toplam_kitap, toplam_konu = get_summary_stats()

# Üst başlık tek satırda
st.markdown(f"""
<div style='background-color: #1e1e1e; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #333;'>
    <h3 style='margin: 0; color: #fff; text-align: center;'>
        📚 Hadis Analiz ve Kontrol &nbsp;|&nbsp; 
        <span style='color: #4CAF50;'>Toplam Hadis: {toplam_hadis}</span> &nbsp;|&nbsp; 
        <span style='color: #2196F3;'>Kitap: {toplam_kitap}</span> &nbsp;|&nbsp; 
        <span style='color: #FFC107;'>Konu: {toplam_konu}</span>
    </h3>
</div>
""", unsafe_allow_html=True)

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
            WHERE k.ad = ?
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
            WHERE ko.ad = ?
            ORDER BY k.ad
            """,
            (konu,),
        )

    kitaplar = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return kitaplar


@st.cache_data(ttl=60)
def get_all_books_dict():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, ad FROM kitaplar ORDER BY ad")
    res = {r[1]: r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()
    return res

@st.cache_data(ttl=60)
def get_topics_dict_for_book_id(kitap_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, ad FROM konular WHERE kitap_id = ? ORDER BY ad", (kitap_id,))
    res = {r[1]: r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()
    return res

def update_hadis(hadis_id, genel_no, kitap_id, konu_id, kitap_hadis_no, ravi):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hadisler 
            SET genel_no = ?, kitap_id = ?, konu_id = ?, kitap_hadis_no = ?, ravi = ?
            WHERE id = ?
        """, (genel_no, kitap_id, konu_id, kitap_hadis_no, ravi, hadis_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
    
    # Cache'leri temizle ki liste güncel gelsin
    st.cache_data.clear()

def run_query(kitap, konu, arama_metin, arama_ravi, limit):
    conn = get_connection()
    cur = conn.cursor()

    where_clauses = []
    params = []

    if kitap != "Tümü":
        where_clauses.append("k.ad = ?")
        params.append(kitap)

    if konu != "Tümü":
        where_clauses.append("ko.ad = ?")
        params.append(konu)

    if arama_metin:
        where_clauses.append("h.metin LIKE ?")
        params.append(f"%{arama_metin}%")

    if arama_ravi:
        where_clauses.append("h.ravi LIKE ?")
        params.append(f"%{arama_ravi}%")

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
            h.metin,
            k.id AS kitap_id,
            ko.id AS konu_id
        FROM hadisler h
        LEFT JOIN kitaplar k ON h.kitap_id = k.id
        LEFT JOIN konular ko ON h.konu_id = ko.id
        {where_sql}
        ORDER BY h.genel_no
        LIMIT ?
    """
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    cur.close()
    conn.close()

    return columns, rows


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
    arama_metin = st.text_input("Metinde Ara")
    arama_ravi = st.text_input("Ravide Ara")
    limit = st.slider("Gösterilecek kayıt", min_value=50, max_value=5000, value=500, step=50)

columns, rows = run_query(secili_kitap, secili_konu, arama_metin, arama_ravi, limit)

st.subheader(f"Kayıtlar ({len(rows)})")

if not rows:
    st.info("Bu filtreye uygun kayıt bulunamadı.")
else:
    view_data = []
    for row in rows:
        d = dict(zip(columns, row))
        view_data.append(
            {
                "id": d["id"],
                "konu_id": d["konu_id"],
                "genel_no": d["genel_no"],
                "kitap": d["kitap"],
                "konu": d["konu"],
                "kitap_hadis_no": d["kitap_hadis_no"],
                "ravi": d["ravi"],
                "metin": d["metin"],
            }
        )

    edited_df = st.data_editor(
        view_data,
        width='stretch',
        hide_index=True,
        column_config={
            "id": None, 
            "konu_id": None,
            "genel_no": st.column_config.NumberColumn("Genel No", step=1, width="small"),
            "kitap": st.column_config.TextColumn("Kitap", disabled=True),
            "konu": st.column_config.TextColumn("Konu (İsmini Değiştir)"),
            "kitap_hadis_no": st.column_config.NumberColumn("Kitap Hadis No", step=1, width="small"),
            "ravi": st.column_config.TextColumn("Ravi"),
            "metin": st.column_config.TextColumn("Metin (Çift tıklayıp okuyun)", disabled=True),
        },
        disabled=["id", "konu_id", "kitap", "metin"],
        key="hadis_table",
    )

    if "hadis_table" in st.session_state and st.session_state.hadis_table.get("edited_rows"):
        st.warning("Tabloda değişiklikler yaptınız. Kaydetmek için aşağıdaki butona basın.")
        if st.button("Hücre İçi Değişiklikleri Kaydet", type="primary"):
            conn = get_connection()
            cur = conn.cursor()
            try:
                for row_idx, updates in st.session_state.hadis_table["edited_rows"].items():
                    row_id = view_data[row_idx]["id"]
                    row_konu_id = view_data[row_idx]["konu_id"]
                    
                    # Update fields based on what changed
                    set_clauses = []
                    params = []
                    if "genel_no" in updates:
                        set_clauses.append("genel_no = ?")
                        params.append(updates["genel_no"])
                    if "kitap_hadis_no" in updates:
                        set_clauses.append("kitap_hadis_no = ?")
                        params.append(updates["kitap_hadis_no"])
                    if "ravi" in updates:
                        set_clauses.append("ravi = ?")
                        params.append(updates["ravi"])
                        
                    if set_clauses:
                        params.append(row_id)
                        sql = f"UPDATE hadisler SET {', '.join(set_clauses)} WHERE id = ?"
                        cur.execute(sql, params)
                        
                    # Konu yazısı düzeltildiyse konular tablosunu güncelle
                    if "konu" in updates and row_konu_id is not None:
                        cur.execute("UPDATE konular SET ad = ? WHERE id = ?", (updates["konu"], row_konu_id))
                
                conn.commit()
                st.cache_data.clear()
                st.success("Değişiklikler başarıyla kaydedildi!")
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"Güncelleme hatası: {e}")
            finally:
                cur.close()
                conn.close()

    # Eğer Kitap ve Konu değiştirmek istenirse detaylı düzenleme butonu koyalım
    # data_editor selection doesn't return full info easily unless we use on_select, but wait
    # In data_editor, row selection is enabled if we pass selection_mode, but data_editor doesn't fully support selection + editing in the same way in older versions. 
    # Let's just use data_editor without row selection for now, since inline editing is much faster!
