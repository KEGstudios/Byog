# TEST v0.11.0 — araç parçaları, çağırma süresi, kalkan dolma değerleri

Yeni olanlar:

- **Araç parçaları:** her parçanın kendi canı ve zırhı ayarlanabiliyor (`part_..._health`, `part_..._armor`).
- **Araç ana zırhı** (`armor`) ve **stratagem çağırma süresi** (`call_in_time`).
- **Kalkan dolma değerleri:** dört değerin hangisinin ne olduğunu oyunda ayırt etmemiz gerekiyor
  (Deneme 3). Bu bir keşif testi; senden gözlem istiyorum.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.** Başkalarının lobisine bu modla girme.
>
> Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve `tuner.log` dosyalarını
> yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.11.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.11.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, **F10**'a bas
(gemideyken), sonra göreve in.

## Deneme 1 — exosuit parçaları ve zırh

```ini
[vehicle: combat_walker]
part_leg_left_health = 10
part_leg_left_armor = 0
part_leg_right_health = 100000
```

Patriot exosuit çağır, **dışarıdan** kendi silahınla bacaklarına ateş et.

- **Sol bacak** birkaç mermide kırılıyor mu? (normali 550 can, zırh 3)
- **Sağ bacak** şarjörler dolusu mermiye rağmen kırılmıyor mu?
- Sol bacak kırılınca exosuit'e ne oldu? (yürüyemedi / patladı / bir şey olmadı)

Parça isimleri `catalog.txt` içinde `[vehicle: ...]` altında. İsmi çözemediğimiz parçalar
`part_fed0a478_health` gibi kodla görünüyor; hangisinin ne olduğunu biliyorsan yazman işimize yarar.

## Deneme 2 — çağırma süresi

```ini
[stratagem: team_weapons_recoilless_rifle]
call_in_time = 20
```

- Recoilless Rifle kapsülü işaretten sonra yaklaşık **20 saniyede** mi indi? (normali 3)

## Deneme 3 — kalkan dolma değerleri (keşif)

Shield Generator Pack tak. Önce **config boşken** normal davranışı ölç, sonra her satırı **tek tek**
dene (her seferinde config'de yalnızca o satır olsun). Her denemede kalkanı düşmana kırdır ve şunlara bak:

- **a)** Kalkan kırıldıktan kaç saniye sonra geri geldi?
- **b)** Geri geldiğinde dolu muydu, zayıf mıydı?
- **c)** Kırılmadan hasar alıp durunca kaç saniyede dolmaya başladı, ne hızla doldu?

```ini
[shield: energy_shield_backpack]
shield_value_88 = 1
```

```ini
[shield: energy_shield_backpack]
shield_value_92 = 1
```

```ini
[shield: energy_shield_backpack]
shield_value_96 = 10
```

```ini
[shield: energy_shield_backpack]
shield_value_100 = 10
```

Normal değerler: 88 → 60, 92 → 12, 96 → 150, 100 → 150. Kaba gözlem yeter; hangi satırın a, b ya da
c'yi değiştirdiğini anlamamız lazım.

## Deneme 4 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Her şey normal mi?

## Bana göndereceklerin

Deneme 4'ten **önce** alınmış `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: Sol bacak birkaç mermide kırıldı | |
| 1: Sağ bacak kırılmadı | |
| 1: Sol bacak kırılınca ne oldu? | |
| 2: Recoilless kapsülü ~20 sn'de indi | |
| 3: Normal: a / b / c | |
| 3: `shield_value_88 = 1` neyi değiştirdi? | |
| 3: `shield_value_92 = 1` neyi değiştirdi? | |
| 3: `shield_value_96 = 10` neyi değiştirdi? | |
| 3: `shield_value_100 = 10` neyi değiştirdi? | |
| 4: Her şey normale döndü | |
| Başlangıçta takılma oldu mu? | |
| Tuhaflık / çökme? Ne yaparken? | |
