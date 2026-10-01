# TEST v0.2.1 — Atış hızı, silaha özel hasar, geri tepme

v0.2.0 testinde `damage` çalıştı, `damage_bonus` ve `rpm` çalışmadı. Sebebi bulundu: oyun bu
değerleri salt-okunur bellekte tutuyor ve önceki sürüm oraya yazmayı bilerek reddediyordu.
Bu sürüm oraya da yazabiliyor. Bu test onu deniyor.

Değişiklikler sadece bellekte; oyunu kapatınca her şey eski haline döner. Testi **tek başına ya da
özel lobide** yap.

Dosya: `dist/HD2-Stat-Tuner-v0.2.1.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı (v0.2.0) sil.
2. `HD2-Stat-Tuner-v0.2.1.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `Win + R` → `%LOCALAPPDATA%\HD2StatTuner` klasöründeki `config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini aşağıdaki blokla **tamamen değiştir**, kaydet, oyunda **F10**'a bas.
Denemeleri bir görevin içinde yap (bu değerlerin tabloları görevde yükleniyor).

## Deneme 1 — atış hızı

```ini
[weapon: assault_rifle]
rpm = 200%
```

Liberator gözle görülür şekilde daha hızlı ateş ediyor mu?

## Deneme 2 — sadece o silaha özel hasar

```ini
[weapon: assault_rifle]
damage_bonus = +5000
durable_damage_bonus = +5000
```

- Liberator küçük/orta düşmanları tek mermide öldürüyor mu?
- Stalwart **normal** mi kaldı? (Asıl soru bu: değişiklik sadece Liberator'da mı?)

## Deneme 3 — geri tepme

```ini
[weapon: assault_rifle]
recoil = 0
```

Liberator ateş ederken hiç tepmiyor mu?

## Deneme 4 — geri alma

`config.txt` içini tamamen boşalt, kaydet, **F10**. Atış hızı, hasar ve tepme normale döndü mü?

## Her denemede bak

Değişiklik **F10'a basar basmaz** mı geçerli oldu, yoksa silahı yere bırakıp tekrar alınca ya da
yeni görevde mi? Fark görmezsen önce silahı bırakıp al, olmazsa yeni göreve in; hangisinden sonra
değiştiğini yaz.

## Bana göndereceklerin

`%LOCALAPPDATA%\HD2StatTuner` klasöründen `STATUS.txt` ve `tuner.log` (bu sürümde log her denemenin
sonucunu ayrı ayrı tutuyor, o yüzden tek seferde göndermen yeterli).

| Deneme | Sonuç (evet / hayır / emin değilim) | Hemen mi, silahı yeniden alınca mı, yeni görevde mi? |
|---|---|---|
| 1: Liberator daha hızlı ateş ediyor | | |
| 2: Liberator tek mermide öldürüyor | | |
| 2: Stalwart normal kaldı | | |
| 3: Liberator tepmiyor | | |
| 4: Her şey normale döndü | | |
| Takılma ya da çökme oldu mu? Ne zaman? | | |
| Oyunu kapatınca Görev Yöneticisi'nde `helldivers2.exe` kaldı mı? | | |

## Bir şey ters giderse

- `STATUS.txt` dosyasının **ilk satırı** ne olduğunu söyler. `REFUSED` yazıyorsa oyun güncellenmiş
  demektir; mod bu durumda bilerek hiçbir şey yazmaz. Dosyayı bana gönder.
- `PARTIAL ... waiting for their table` yazıyorsa tablolar henüz yüklenmemiş; göreve inince yarım
  dakika içinde kendiliğinden uygulanır.
- Modu kapatmak için Arsenal'dan devre dışı bırakman yeterli.
