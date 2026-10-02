# TEST v0.8.0 — sayım + silaha özel şarjör

Bu sürümde iki ayrı şey var:

1. **Sayım (salt okunur):** oyunun belleğindeki bütün tablolarda hangi patlama kaydına kimin baktığını
   sayar. Hiçbir şeyi değiştirmez. Patlamaları silah silah ayırabilmek için bu listeye ihtiyacım var.
2. **Silaha özel şarjör (deneysel):** aynı şarjörü kullanan silahlara artık farklı değer verilebiliyor.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.** Başkalarının lobisine bu modla girme.
>
> Deneme 2 deneysel. Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve
> `tuner.log` dosyalarını yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.8.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.8.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir** ve kaydet.

## Deneme 1 — sayım

```ini
[settings]
census = true
```

1. Config'i kaydet, oyunu aç, **bir göreve in** (sayım görev yüklenince başlar).
2. Görevde normal oyna. 3-5 dakika sonra `STATUS.txt` dosyasını aç: `census: done ... -> CENSUS.txt`
   yazana kadar bekle (`census: running` yazıyorsa sürüyor demektir).
3. `census: done` yazınca aynı klasördeki **`CENSUS.txt`** dosyasını kopyala.

- Sayım sırasında oyunda takılma oldu mu?

## Deneme 2 — aynı şarjörü kullanan iki silaha farklı değer

Silah özelleştirme ekranında **Liberator** ve **Liberator Penetrator** için fabrika şarjörü takılı olsun.
Gemideyken config'i kaydet, **F10**'a bas, sonra göreve in.

```ini
[weapon: assault_rifle]
capacity = 100
mags_start = 10

[weapon: assault_rifle_ap]
capacity = 20
```

`STATUS.txt` ilk satırı `OK - 3 values applied, 1 magazines switched to the weapons' own values`
olmalı.

- Liberator'ın şarjörü **100**, başlangıçta **10** yedek mi?
- Liberator Penetrator'ın şarjörü **20** mi? (Önceki sürümde ikisi aynı olmak zorundaydı.)
- İkisinin de yedek şarjör üst sınırı ve ikmali normal mi?
- Config'de olmayan başka bir silahın (örneğin Peacemaker) şarjörü normal mi?

## Deneme 3 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Liberator 45, Penetrator 45, hepsi normal mi?

## Bana göndereceklerin

`CENSUS.txt` (Deneme 1), Deneme 3'ten **önce** alınmış `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: `census: done` yazdı, CENSUS.txt oluştu | |
| 1: Sayım sırasında takılma oldu mu? | |
| 2: STATUS ilk satırı beklendiği gibi | |
| 2: Liberator şarjörü 100, 10 yedek | |
| 2: Penetrator şarjörü 20 | |
| 2: Başka silahların şarjörü normal | |
| 3: Her şey normale döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
