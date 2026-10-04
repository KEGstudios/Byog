# TEST v1.0.0 — yayından önce son kontrol

1.0.0'da üç şey değişti: modun adı her yerde **BYOG** oldu (ayar klasörü de), araştırma ayarları
(census, canary, probe) koddan çıkarıldı, pakete logo eklendi. Kodun geri kalanı v0.16.0 ile aynı, ama
bu haliyle oyunda hiç çalıştırılmadı. Nexus'a yüklemeden önce bir kez deneyin.

> Ayar klasörü değişti: artık `%LOCALAPPDATA%\BYOG`. Eski `HD2StatTuner` klasöründeki `menu.txt` ve
> `config.txt` okunmaz; isterseniz yeni klasöre kopyalayın.

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `BYOG-v1.0.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
   Arsenal bu dosyayı kabul etmezse `BYOG-v1.0.0-no-icon.zip` dosyasını dene ve hangisinin çalıştığını yaz.

## Kontrol

1. Arsenal'da modun adı **BYOG - Balance Your Own Game** olarak, logosuyla görünüyor mu?
2. Oyunda **F9** menüyü açıyor mu? Başlıkta `v1.0.0` yazıyor mu? Bir silahın değerleri başlıklar altında
   gruplanmış mı (DAMAGE, STATUS EFFECTS, EXPLOSION, PROJECTILE, FIRE, AMMO, HANDLING)? Başlıklar okunuyor mu,
   aşağı inerken liste düzgün kayıyor mu?
3. Menüden bir değer değiştir (örnek: AR-23 Liberator `rpm`), göreve in: etkili mi?
4. `sentry` yazarak ara, **Machine Gun Sentry (gun)** → `lifetime_seconds` = 30: taret ~30 saniyede
   yok oluyor mu?
5. **MG-43 Machine Gun** → `damage` = 5: neredeyse hasarsız mı?
5b. **Taret menzili (doğrulanmadı, bu kontrol önemli):** **Machine Gun Sentry (gun)** → `sight_range` = 10
   (normali 75). Taret artık yalnızca çok yakındaki (~10 m) düşmanlara mı ateş ediyor? Değişmiyorsa bu
   değer menzil değil demektir; söyle, yayından önce çıkarayım.
6. Oyunu kapat-aç: ayarlar duruyor mu? (`%LOCALAPPDATA%\BYOG\menu.txt`)
7. `%LOCALAPPDATA%\BYOG\STATUS.txt` ilk satırı `OK - ...` mi?

| Soru | Cevap |
|---|---|
| Hangi zip kuruldu (logolu / logosuz)? | |
| 1: Ad ve logo doğru | |
| 2: Menü açılıyor, v1.0.0, değerler gruplu | |
| 3: Değişiklik oyunda etkili | |
| 4: Taret ~30 sn'de yok oldu | |
| 5: MG-43 neredeyse hasarsız | |
| 5b: `sight_range = 10` ile taret sadece yakına ateş ediyor | |
| 6: Yeniden açınca ayarlar duruyor | |
| 7: STATUS `OK` | |
| Tuhaflık / çökme? | |
