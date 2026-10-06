# TEST v1.1.17 — yeni menü

Menü baştan yazıldı: dört sayfa (Items, Presets, Keys, Language), atanabilir tuşlar, presetler, Çince,
status effect süresi. Çevrimdışı testlerin hepsi geçiyor, ama bu sürüm oyunda hiç çalıştırılmadı.
Üç şeyin çalışıp çalışmadığı ancak oyunda belli olur: **tuş engelleme**, **Çince yazı tipi**,
**status süresi**. Bunlar çalışmasa bile gerisi çalışmalı.

> Tuşlar değişti. Varsayılanlar: **F9** aç/kapat, **F6 / F7** sayfa, **oklar** gezin, **Tab** sütun,
> **Insert** seç / değer yaz / onayla, **End** vazgeç / aramayı temizle, **Delete** sıfırla,
> **F3** ara, **Shift** on kat. Menünün en alt satırı geçerli tuşları her zaman gösterir.

## Kurulum

1. Arsenal'da eski BYOG'u sil, `BYOG-v1.1.17.zip` dosyasını ekle, etkinleştir, **Deploy** et.
2. `%LOCALAPPDATA%\BYOG` klasörüne dokunma: eski `menu.txt` içindeki ayarlar "Default" presetine taşınmalı.

## 0. Silah adları

Silahlar sayfasındaki adlar tablodan işlendi. Menüde silah adları doğru mu? Aynı adı taşıyan çiftler
iç adlarıyla birlikte görünür: `SG-8 Punisher (pump_shotgun)`, `SMG-37 Defender (smg_defender)`,
`PLAS-45 Epoch (plasma_rifle)`. Hangisi hangisi, tabloya yazarsan düzeltirim.
Çıkarılanlar: `grenade_launcher_tactical`, `laser_rifle_charge`, `marksman_rifle_justice`.

## A. Menü ve eski ayarlar

1. F9 menüyü açıyor mu, başlıkta `v1.1.17` yazıyor mu? Üstte dört sayfa, sağ üstte `Preset: Default` var mı?
2. 1.0'da yaptığın değişiklikler duruyor mu (değerler sarı)? `presets\Default.txt` oluşmuş mu?
3. Stat adları okunur mu ("Armor penetration, direct hit", "Magazine size")? Listenin altında seçili
   değerin config.txt adı (`ap_direct`) yazıyor mu?
4. Bir değere gel, **Insert**'e bas, sayı yaz, **Insert**: değer yazdığın sayı oldu mu? Aralık dışı bir
   sayı (örn. rpm için 99999) sınıra çekiliyor mu? **End** ile vazgeçince değer aynı kalıyor mu?
5. Status değerlerinde numaranın yanında ad çıkıyor mu (`5  Fire`)?

## B. Yazı yazma

1. Items sayfasında hiçbir tuşa basmadan bir harfe bas: arama **başlamamalı**.
2. Arama kutusu artık listenin **üstünde**. Öğe listesindeyken **Insert** (ya da F3) kutuya giriyor mu?
   `sentry` yaz: liste süzülüyor mu? Kutudayken ok tuşları ve Tab menüde bir şeyi oynatmamalı.
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

## E. Tuş engelleme ve donma (en önemli kontrol)

Odağı değiştiren bütün yöntemler ya tuş kaçırdı ya oyunu dondurdu. Bu sürüm odağa dokunmuyor: oyunun
pencere iş parçacığına küçük bir mesaj süzgeci koyuyor ve menü açıkken tuş mesajlarını orada düşürüyor.

**Tuşlar engelleniyor mu?**
1. Menü açıkken W/A/S/D, Esc, Enter, Tab, M: oyunda bir şey oluyor mu? Ses çıkıyor mu?
2. Arama kutusuna yaz, Backspace'e bas: oyunun menüsü açılıyor mu?
3. Bir tuşu (örneğin W) basılı tutarken F9 ile menüyü aç, sonra bırak: karakter yürümeye devam ediyor mu? (Etmemeli.)

**Oyun normal mi?**
4. Menü açıkken görüntü akıyor mu, ses kesiliyor mu? Menüyü kapatınca tuşlar hemen dönüyor mu?
5. Oyunun sohbet kutusu ve kendi menüleri menü kapalıyken normal çalışıyor mu (yazı yazılabiliyor mu)?

**Donuyor mu?**
6. Menü açıkken Alt+Tab ile çık, 10 saniye bekle, dön. Beş kez tekrarla.
7. Menü açıkken oyun penceresine fareyle tıkla, menüde gezin.
8. Birkaç değeri hızlıca değiştir; bir değerin üstünde Insert ile sayı yaz.
9. Menü açıkken Alt+F4 oyunu kapatıyor mu? (Kapatmalı.)

Donarsa ya da oyun kapanırsa: **yeniden açmadan** haber ver (`watch.txt`, `byog.log`).

## F. Çince (deneme — oyun donabilir)

Oyunun dili Çince olmalı (oyun içi ayarlardan). Language sayfasında "Chinese (Simplified)" → Insert.

1. Oyun dondu ya da kapandı mı? Öyleyse oyunu kapatıp yeniden aç: mod Çinceyi kendisi kapatmış olmalı
   (Language sayfasında "Chinese is switched off..." yazar). Bunu yaz.
2. Donmadıysa: metinler Çince mi, okunuyor mu? Kutu, soru işareti ya da boşluk çıkıyor mu?
   İngilizce silah adları ve rakamlar düzgün mü? Yazılar sütunlara sığıyor mu?
3. Oyunun dili İngilizceyken "Chinese (Simplified)" seçilince ne oluyor? ("no font..." yazmalı.)

## G. Status süresi

1. Status effects kategorisi (Items sayfasında sola bas: son kategori). 71 etki var mı?
2. **Gas (6 s)** → Duration = 30. Gaz bombası at: düşmandaki gaz etkisi belirgin şekilde uzun sürüyor mu?
3. **Acid Storm** → Duration = 10; bir silaha `Status effect 1: type` = 55 ver (yorumcunun yaptığı gibi):
   etki daha uzun sürüyor mu? Zırh azaltma da uzuyor mu, yoksa yalnızca ekran efekti mi?

## Gönderilecekler

`%LOCALAPPDATA%\BYOG` içinden: `STATUS.txt`, `byog.log`, `settings.txt`, `presets` klasörü.
