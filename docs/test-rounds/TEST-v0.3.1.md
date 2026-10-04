# TEST v0.3.1 — Liberator'a kendi mermisi + bellek sondası

Bu sürüm iki şeyi deniyor:

1. **Kendi mermisi ("own bullet"):** Liberator, Stalwart ile aynı mermiyi kullandığı için birinin
   hasarını değiştirmek ikisini de değiştiriyordu. Bu sürüm Liberator'a oyunda kullanılmayan bir
   mermi kaydını veriyor; böylece sadece Liberator değişmeli.
2. **Sonda ("probe"):** sadece okuyan bir tarama. Oyunun mermi tablolarını nasıl kullandığını
   öğrenmek için; ileride her şeye ayrı mermi verebilmenin yolunu buna göre seçeceğiz.

Değişiklikler sadece bellekte; oyunu kapatınca her şey eski haline döner. **Tek başına ya da özel
lobide** yap.

Dosya: `dist/HD2-Stat-Tuner-v0.3.1.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.3.1.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, oyunda **F10**'a bas.

## Deneme 1 — sonda + sadece kendi mermisi

```ini
[settings]
probe = true

[weapon: assault_rifle]
own_bullet = true
```

1. Kaydet, F10. **Gemide 4 dakika bekle** (sonda bu sırada belleği tarıyor; hafif bir yük olabilir).
   Klasörde `PROBE.txt` dosyası belirince tarama bitmiş demektir.
2. Göreve in, Liberator ile ateş et. Bu denemede Liberator **tamamen normal** olmalı:
   hasarı, sesi, mermi izi, isabeti ve tepmesi her zamanki gibi mi?

## Deneme 2 — sadece Liberator'ın hasarı

```ini
[weapon: assault_rifle]
own_bullet = true
damage = 5000
durable_damage = 5000
```

1. Gemide stat kartlarına bak: Liberator'ın hasarı değişti mi? **Stalwart'ınki aynı mı kaldı?**
2. Göreve in. Liberator küçük/orta düşmanları tek mermide öldürüyor mu?
3. **Stalwart normal mi?** (Asıl soru bu.)

Fark görmezsen yeni bir göreve inip tekrar dene ve bunu not et.

## Deneme 3 — geri alma

`config.txt` içini tamamen boşalt, kaydet, **F10**. Liberator normale döndü mü?

## Test boyunca dikkat et

Bu yöntem oyunda kullanılmadığını düşündüğümüz iki kaydı devralıyor. Yanılıyorsak, o kayıtları
kullanan başka bir şey (bir silah, bir düşman, bir taret) mod açıkken **Liberator mermisi atar**.
Böyle bir tuhaflık görürsen (yanlış ses, yanlış hasar, garip mermi) neyin yaptığını yaz.

## Bana göndereceklerin

`%LOCALAPPDATA%\HD2StatTuner` klasöründen **üç dosya**: `STATUS.txt`, `tuner.log`, `PROBE.txt`.
Ve şu tablo:

| Soru | Cevap (evet / hayır / emin değilim) |
|---|---|
| 1: `PROBE.txt` oluştu | |
| 1: Liberator tamamen normal | |
| 2: Stat kartında Liberator hasarı değişti | |
| 2: Stat kartında Stalwart aynı kaldı | |
| 2: Liberator tek mermide öldürüyor | |
| 2: Stalwart normal | |
| 3: Her şey normale döndü | |
| Başka bir silahta / düşmanda tuhaflık gördün mü? Hangisinde? | |
| Takılma ya da çökme oldu mu? Ne zaman? | |

`STATUS.txt` içinde `OWN BULLET ACTIVE` yazmalı. `OWN BULLET WAITING` yazıyorsa tablolar henüz
yüklenmemiştir; göreve inince yarım dakika içinde kendiliğinden `ACTIVE` olur. `OWN BULLET FAILED`
yazıyorsa mod hiçbir şeyi değiştirmemiştir; dosyayı bana gönder.
