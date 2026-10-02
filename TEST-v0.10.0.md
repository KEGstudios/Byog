# TEST v0.10.0 — yeni kategoriler: stratagem, sırt çantası, kalkan, araç

Bu sürümde config'e dört yeni bölüm türü geldi. Hepsi ilk kez oyunda deneniyor.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.** Başkalarının lobisine bu modla girme.
>
> Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve `tuner.log` dosyalarını
> yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.10.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.10.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Bütün isimler aynı klasördeki `catalog.txt` içinde (`[stratagem: ...]`, `[backpack: ...]`,
`[shield: ...]`, `[vehicle: ...]`).

## Deneme 1 — dört kategori birden

Config'i **gemideyken** kaydet, **F10**'a bas, sonra göreve in. Yanına al: Orbital Precision Strike,
Eagle 500kg Bomb, Orbital Laser, Recoilless Rifle, Shield Generator Pack ya da Patriot Exosuit
(hepsi sığmazsa iki göreve böl).

```ini
[stratagem: orbital_precision_strike]
cooldown = 10

[stratagem: eagle_500kg_bomb]
uses = 4

[stratagem: orbital_laser]
uses = 10

[backpack: recoilless_rifle_backpack]
charges = 12
charges_refill = 12

[shield: energy_shield_backpack]
shield_health = 5000

[vehicle: combat_walker]
health = 500%
```

Görevde `STATUS.txt` ilk satırı `OK - 7 values applied` olmalı.

- Orbital Precision Strike'ın bekleme süresi **10 saniye** mi? (normali 80)
- Eagle 500kg, yeniden silahlanmadan önce **4 kez** çağrılabiliyor mu? (normali 1)
- Orbital Laser **10 kullanım** gösteriyor mu? (normali 3)
- Recoilless Rifle çağırınca sırt çantasında **12 roket** var mı? (normali 5)
- Kalkan sırt çantası çok daha fazla hasar kaldırıyor mu? (normali 150, şimdi 5000)
- Patriot exosuit çok daha dayanıklı mı? (normali 1800, şimdi 9000)

## Deneme 2 — görevdeyken değiştirmek

Görevdeyken `cooldown = 10` satırını `cooldown = 30` yap, kaydet, F10.

- Bekleme süresi hemen 30'a döndü mü, bir sonraki çağrıda mı, yoksa ancak yeni görevde mi?

## Deneme 3 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Her şey normal mi?

## Bana göndereceklerin

Deneme 3'ten **önce** alınmış `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: STATUS ilk satırı `OK - 7 values applied` | |
| 1: Precision Strike bekleme süresi 10 sn | |
| 1: 500kg 4 kullanım | |
| 1: Orbital Laser 10 kullanım | |
| 1: Recoilless sırt çantası 12 roket | |
| 1: Kalkan çok daha dayanıklı | |
| 1: Exosuit çok daha dayanıklı | |
| 2: Görevdeyken değişiklik ne zaman etkili oldu? | |
| 3: Her şey normale döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
