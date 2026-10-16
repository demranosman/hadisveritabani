import sqlite3
import re

def get_connection():
    return sqlite3.connect("hadisler.db")

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT id, metin FROM hadisler WHERE ravi IS NULL OR ravi = ''")
rows = cur.fetchall()

updated_count = 0
skipped_count = 0

skip_phrases = [
    "bir ", "yine ", "aynı ", "bunun ", "bu ", "şu ", "o ", "diğer ", "başka ", 
    "buhari'de ", "buhari", "müslim", "sünen", "bize ", "bana ", "dedi ki",
    "rivayet "
]

def should_skip(ravi_text):
    lower_ravi = ravi_text.lower().strip()
    if not lower_ravi:
        return True
    
    # Fazla uzunsa muhtemelen paragraftır, atla
    if len(ravi_text) > 80:
        return True
        
    for phrase in skip_phrases:
        if lower_ravi.startswith(phrase):
            return True
            
    # Eğer ravi kısmında : veya " varsa muhtemelen bir konuşmadır
    if ":" in ravi_text or '"' in ravi_text:
        return True
        
    return False

for row_id, metin in rows:
    if metin:
        # Metnin başından ilk '(' paranteze kadar olan kısmı al
        first_paren_idx = metin.find("(")
        if first_paren_idx != -1:
            potential_ravi = metin[:first_paren_idx].strip()
            
            # "\n" falan varsa atalım
            potential_ravi = " ".join(potential_ravi.split())
            
            if not should_skip(potential_ravi):
                cur.execute("UPDATE hadisler SET ravi = ? WHERE id = ?", (potential_ravi, row_id))
                updated_count += 1
            else:
                skipped_count += 1
        else:
            skipped_count += 1

conn.commit()
conn.close()

print(f"Toplam güncellenen kayıt sayısı: {updated_count}")
print(f"Atlanan (veya şartı sağlamayan) boş kayıt sayısı: {skipped_count}")
