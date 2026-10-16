import sqlite3

def get_connection():
    return sqlite3.connect("hadisler.db")

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT id, metin, ravi FROM hadisler WHERE ravi IS NULL OR ravi = ''")
rows = cur.fetchall()

to_update = []
to_skip = []

skip_phrases = ["bir diğer", "yine", "aynı", "bunun", "bu", "şu", "o", "diğer", "başka", "bir"]

for row_id, metin, ravi in rows:
    if metin:
        # metnin başından ilk paranteze kadar olan kısmı al
        first_paren_idx = metin.find("(")
        if first_paren_idx != -1:
            potential_ravi = metin[:first_paren_idx].strip()
            
            # Bazı basit temizlik ve kontroller
            lower_ravi = potential_ravi.lower()
            
            # Eğer ravi çok uzunsa muhtemelen isim değildir
            if len(potential_ravi) > 100:
                to_skip.append((row_id, potential_ravi, "Çok uzun"))
                continue
                
            # Belirli kelimelerle başlıyorsa atla
            should_skip = False
            for phrase in skip_phrases:
                if lower_ravi.startswith(phrase):
                    should_skip = True
                    break
            
            if should_skip:
                to_skip.append((row_id, potential_ravi, "Yasaklı kelime"))
            else:
                to_update.append((row_id, potential_ravi, metin))
        else:
            to_skip.append((row_id, "PARANTEZ YOK", metin[:50]))

print(f"Toplam boş ravi sayısı: {len(rows)}")
print(f"Güncellenebilecek ravi sayısı: {len(to_update)}")
print(f"Atlanan ravi sayısı: {len(to_skip)}")

print("\n--- GÜNCELLENECEK BAZI ÖRNEKLER ---")
for r in to_update[:15]:
    print(f"ID {r[0]}: {r[1]}")

print("\n--- ATLANAN BAZI ÖRNEKLER ---")
for r in to_skip[:15]:
    print(f"ID {r[0]} Neden: {r[2]} -> {r[1]}")
