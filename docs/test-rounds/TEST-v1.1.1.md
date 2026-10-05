# TEST v1.1.1 — yeni menü + araştırma

Menü baştan yazıldı: dört sayfa (Items, Presets, Keys, Language), atanabilir tuşlar, presetler, Çince,
status effect süresi. Çevrimdışı testlerin hepsi geçiyor, ama bu sürüm oyunda hiç çalıştırılmadı.
Üç şeyin çalışıp çalışmadığı ancak oyunda belli olur: **tuş engelleme**, **Çince yazı tipi**,
**status süresi**. Bunlar çalışmasa bile gerisi çalışmalı.

> Tuşlar değişti. Varsayılanlar: **F9** aç/kapat, **F6 / F7** sayfa, **oklar** gezin, **Tab** sütun,
> **Insert** seç / değer yaz / onayla, **End** vazgeç / aramayı temizle, **Delete** sıfırla,
> **F3** ara, **Shift** on kat. Menünün en alt satırı geçerli tuşları her zaman gösterir.

## Kurulum

1. Arsenal'da eski BYOG'u sil, `BYOG-v1.1.1.zip` dosyasını ekle, etkinleştir, **Deploy** et.
2. `%LOCALAPPDATA%\BYOG` klasörüne dokunma: eski `menu.txt` içindeki ayarlar "Default" presetine taşınmalı.

## A. Menü ve eski ayarlar

1. F9 menüyü açıyor mu, başlıkta `v1.1.1` yazıyor mu? Üstte dört sayfa, sağ üstte `Preset: Default` var mı?
2. 1.0'da yaptığın değişiklikler duruyor mu (değerler sarı)? `presets\Default.txt` oluşmuş mu?
3. Stat adları okunur mu ("Armor penetration, direct hit", "Magazine size")? Listenin altında seçili
   değerin config.txt adı (`ap_direct`) yazıyor mu?
4. Bir değere gel, **Insert**'e bas, sayı yaz, **Insert**: değer yazdığın sayı oldu mu? Aralık dışı bir
   sayı (örn. rpm için 99999) sınıra çekiliyor mu? **End** ile vazgeçince değer aynı kalıyor mu?
5. Status değerlerinde numaranın yanında ad çıkıyor mu (`5  Fire`)?

## B. Yazı yazma

1. Items sayfasında F3'e basmadan bir harfe bas: arama **başlamamalı**.
2. F3, `sentry` yaz: liste süzülüyor mu? Kutudayken ok tuşları ve Tab menüde bir şeyi oynatmamalı.
   Backspace harf siliyor mu? Insert kutudan çıkıp sonuçları koruyor, End aramayı temizliyor mu?

## C. Presetler

1. F7 ile Presets sayfası. "+ New preset (empty)" → Insert → `fun` yaz → Insert. Sağ üstte `Preset: fun`
   oldu mu, Default'taki bütün değişiklikler oyunda geri alındı mı?
2. `fun` içinde bir iki değer değiştir. Presets sayfasında Default satırında `[Activate]` → Insert:
   Default'un değerleri geri geldi mi, `fun`'ınkiler gitti mi?
3. Sol/sağ ile `Rename`, `Duplicate`, `Delete` dene. Delete önce soruyor mu?
4. Oyunu kapat-aç: son etkin preset ve değerleri duruyor mu?
5. `presets` klasörüne bir preset dosyasını başka adla kopyala: listede çıkıyor mu?

## D. Tuş atama

1. Keys sayfasında bir eyleme gel, Insert, yeni bir tuşa bas: atandı mı, alt satırdaki ipuçları değişti mi?
2. İki eyleme aynı tuşu ver: uyarı çıkıyor mu?
3. "Reset the keys" varsayılanlara döndürüyor mu? Oyunu kapat-aç: atadığın tuşlar duruyor mu?

## E. Tuş engelleme (deneysel — en önemli kontrol)

Önce gemide dene. Keys sayfasında "Block game input while the menu is open" → Insert (`on`).

1. Oyun çöktü mü? Çöktüyse `byog.log` dosyasının son satırlarını gönder.
2. Menü açıkken W/A/S/D'ye bas: karakter **duruyor mu**? Esc, Enter, Tab oyunda bir şey açıyor mu?
3. Menü yine tuşlara tepki veriyor mu?
4. F9 ile kapat: oyun tuşları **yeniden** alıyor mu? (Almıyorsa oyunu yeniden başlat ve bunu yaz.)
5. Fare: menü açıkken fareyle bakmak ve ateş etmek hâlâ oyuna gidiyor olmalı; bu beklenen durum.

## F. Çince

1. Language sayfasında "Chinese (Simplified)" → Insert. Sağında "no font of the game can draw Chinese"
   yazıyorsa bunu yaz ve `byog.log` içindeki `menu: font ...` satırlarını gönder.
2. Seçilebildiyse: metinler Çince mi, yoksa kutu/boşluk mu çıkıyor? İngilizce silah adları okunuyor mu?
   "Font for Chinese" satırı varsa Insert ile diğer yazı tiplerini de dene; hangisi düzgün?
3. English'e dön: her şey eski haline geldi mi?

## G. Status süresi

1. Status effects kategorisi (Items sayfasında sola bas: son kategori). 8 etki var mı?
2. **Gas (6 s)** → Duration = 30. Gaz bombası at: düşmandaki gaz etkisi belirgin şekilde uzun sürüyor mu?
3. **Acid Storm** → Duration = 10; bir silaha `Status effect 1: type` = 55 ver (yorumcunun yaptığı gibi):
   etki daha uzun sürüyor mu? Zırh azaltma da uzuyor mu, yoksa yalnızca ekran efekti mi?

## H. Araştırma dosyası

Bu sürüm her açılışta, hiçbir şey yazmadan, `RESEARCH.txt` dosyasını üretir: oyunun status tablosunun
bütün satırları, motorun yazı tipi ve girdi işlevlerinden hangilerinin var olduğu, hangi yazı tiplerinin
yüklü olduğu. Yapman gereken tek şey bir göreve inip çıkmak ve dosyayı göndermek.

1. `RESEARCH.txt` oluştu mu? `[status effects] 71 rows` gibi bir satırla başlıyor mu?
   "the table was not found" yazıyorsa bir göreve in, sonra oyunu kapat-aç ve tekrar bak.

## Gönderilecekler

`%LOCALAPPDATA%\BYOG` içinden: `RESEARCH.txt`, `STATUS.txt`, `byog.log`, `settings.txt`, `presets` klasörü.
