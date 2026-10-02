# TEST v0.6.0 — silahlar kendiliğinden ayrılıyor

Artık `own_bullet` yazmaya gerek yok. Bir silahın hasarını (ya da mermiyle ilgili başka bir değerini)
değiştirdiğinde mod o silaha kendiliğinden ayrı bir kayıt veriyor; aynı mermiyi kullanan diğer silahlar
etkilenmiyor.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.** Başkalarının lobisine bu modla girme.

Dosya: `dist/HD2-Stat-Tuner-v0.6.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.6.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, oyunda **F10**'a bas.

## Deneme 1 — aynı mermiyi kullanan iki silaha farklı hasar

```ini
[weapon: assault_rifle]
damage = 5000
durable_damage = 5000

[weapon: lmg_stalwart]
damage = 1

[weapon: machinegun]
rpm = 200%
```

Göreve in. `STATUS.txt` içinde Liberator ve Stalwart için
`rows of its own (automatic) -> OWN BULLET ACTIVE` yazmalı (MG-43 için yazmamalı: atış hızı zaten
silaha özel bir değer).

- Liberator tek mermide öldürüyor mu?
- Stalwart neredeyse hiç hasar vermiyor mu?
- MG-43 iki kat hızlı atıyor, hasarı normal mi?
- F10'a bastığın anda oyunda takılma oldu mu?

## Deneme 2 — eski davranış (isteyerek paylaşmak)

```ini
[weapon: assault_rifle]
own_bullet = false
damage = 5000
durable_damage = 5000
```

Burada Liberator ayrılmıyor; değişiklik aynı mermiyi kullanan herkese gitmeli.

- Liberator tek atıyor mu?
- **Stalwart da tek atıyor mu?** (Bu sefer atması lazım.)

## Deneme 3 — geri alma

`config.txt` içini tamamen boşalt, kaydet, **F10**. Hepsi normale döndü mü?

## Bana göndereceklerin

Deneme 3'ten **önce** `STATUS.txt` ve `tuner.log` dosyalarının birer kopyası, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: Liberator ve Stalwart için `automatic` yazdı | |
| 1: Liberator tek atıyor | |
| 1: Stalwart neredeyse hasar vermiyor | |
| 1: MG-43 hızlı atıyor, hasarı normal | |
| 1: F10'da takılma oldu mu? | |
| 2: Liberator da Stalwart da tek atıyor | |
| 3: Her şey normale döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
