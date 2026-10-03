# TEST v0.12.1 — araç canı: temiz tekrar

Geçen testte config'de birkaç denemenin satırları birlikte duruyordu. `all_health` ile
`part_leg_..._health` satırları birbirini reddetti; yani `all_health` hiç uygulanmadı ve exosuit
aslında normal canındaydı. Bu sürümde tek bir değeri yazan satır, kısayolu (`all_health`) o değer için
geçersiz kılıyor; artık birlikte yazılabilirler.

> **Her denemede `config.txt` içini tamamen sil, sadece o denemenin bloğunu yapıştır.** Eski satırlar
> kalırsa sonuçlar karışıyor.
>
> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.**

Dosya: `dist/HD2-Stat-Tuner-v0.12.1.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.12.1.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Config'i **gemideyken** kaydet, **F10**'a bas, sonra göreve in ve exosuit'i **o görevde** çağır.

## Deneme 1 — her şeyi birlikte ölçekle

```ini
[vehicle: combat_walker]
all_health = 300%
```

`STATUS.txt` ilk satırı `OK - 9 values applied` olmalı (REJECTED olmamalı).

- Patriot, normalde onu öldüren hasarın yaklaşık **üç katına** dayanıyor mu?
- Bir bacağına ateş edince, exosuit ölmeden **önce** bacak kırılıyor mu?

## Deneme 2 — kısayol + tek satır + uyarı (oynamaya gerek yok)

```ini
[vehicle: combat_walker]
all_health = 300%
part_leg_right_health = 100000
```

`STATUS.txt` içinde:

- REJECTED **yok** mu?
- `part_leg_right_health` satırının yanında `WARNING: part leg_right has 100000 health ...` yazıyor mu?

## Deneme 3 — parçanın ana cana etkisi

```ini
[vehicle: combat_walker]
part_leg_left_health = 100000
part_leg_left_armor = 0
part_leg_left_to_main = 0
```

Yeni bir exosuit çağır. Dışarıdan **yalnızca sol bacağına**, birkaç şarjör boyunca ateş et.

- Exosuit bu hasardan **ölmüyor** mu? (ölmüyorsa `to_main` çalışıyor; birkaç şarjörde ölüyorsa
  çalışmıyor)

## Deneme 4 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Her şey normal mi?

## Bana göndereceklerin

Deneme 4'ten **önce** alınmış `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: STATUS `OK - 9 values applied` | |
| 1: Patriot yaklaşık üç kat dayanıklı | |
| 1: Bacak, exosuit ölmeden önce kırıldı | |
| 2: REJECTED yok, WARNING var | |
| 3: Sadece sol bacağa ateş edince exosuit ölmedi | |
| 4: Her şey normale döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
