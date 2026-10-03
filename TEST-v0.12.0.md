# TEST v0.12.0 — araç mantığı, kalkan değerleri isimlendi

Geçen testte öğrendiklerimiz bu sürüme işlendi:

- **Kalkan:** `shield_recharge_delay` (kırılmadan dolmaya başlama süresi), `shield_broken_delay`
  (kırıldıktan sonra bekleme), `shield_recharge_rate` (saniyede dolan can).
- **Araç:** parçaya gelen hasarın ne kadarının ana cana gittiği artık ayarlanabiliyor
  (`part_..._to_main`), ayrıca `durable_resistance`, `explosion_damage_multiplier`, `constitution`.
- **`all_health`:** ana canı ve bütün parçaları birlikte ölçekler; oyunun mantığı (parça araçtan önce
  kırılır) bozulmaz.
- Bir parçanın canı ana canın karşılayabileceğinden fazlaysa STATUS satırın yanına **WARNING** yazar.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.** Başkalarının lobisine bu modla girme.

Dosya: `dist/HD2-Stat-Tuner-v0.12.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.12.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, **gemideyken F10**'a
bas, sonra göreve in.

## Deneme 1 — her şeyi birlikte ölçekle

```ini
[vehicle: combat_walker]
all_health = 300%
```

`STATUS.txt` içinde WARNING olmamalı.

- Patriot belirgin şekilde daha dayanıklı mı?
- Bir bacağına ateş edince, exosuit ölmeden **önce** bacak kırılıyor mu? (normal oyundaki gibi)

## Deneme 2 — uyarı (oynamaya gerek yok)

```ini
[vehicle: combat_walker]
part_leg_right_health = 100000
```

- `STATUS.txt` içinde bu satırın yanında `WARNING: part leg_right has 100000 health ...` yazıyor mu?

## Deneme 3 — parçanın ana cana etkisi

```ini
[vehicle: combat_walker]
part_leg_left_health = 100
part_leg_left_armor = 0
part_leg_left_to_main = 0
```

Sol bacağa dışarıdan ateş et.

- Sol bacak çabuk kırıldı mı?
- Bacak kırılana kadar exosuit'in **ana canı azalmadı** mı? (kırıldıktan sonra exosuit ne oldu?)

## Deneme 4 — kalkan (kısa kontrol)

```ini
[shield: energy_shield_backpack]
shield_recharge_rate = 10
shield_broken_delay = 1
```

- Kalkan kırıldıktan ~1 saniye sonra geri geliyor ama çok **yavaş** mı doluyor?

## Deneme 5 — çağırma süresi (tekrar)

Geçen sefer değer görev sırasında yüklenmişti. Bu kez **gemideyken** kaydet + F10, sonra göreve in ve
Recoilless Rifle'ı **iki kez** çağır.

```ini
[stratagem: team_weapons_recoilless_rifle]
call_in_time = 20
```

- Kapsül ilk çağrıda kaç saniyede indi? İkincide?

## Deneme 6 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Her şey normal mi?

## Bana göndereceklerin

Deneme 6'dan **önce** alınmış `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: Patriot daha dayanıklı | |
| 1: Bacak, exosuit ölmeden önce kırıldı | |
| 2: WARNING yazdı | |
| 3: Sol bacak çabuk kırıldı | |
| 3: O sırada ana can azalmadı / sonra ne oldu? | |
| 4: Kalkan ~1 sn'de geri geldi, yavaş doldu | |
| 5: Kapsül kaç saniyede indi (1. / 2. çağrı)? | |
| 6: Her şey normale döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
