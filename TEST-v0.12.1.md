# TEST v0.12.1 — araç canı: araba (FRV) üzerinde, can gösteren modla

Geçen testte config'de birkaç denemenin satırları birlikte duruyordu; `all_health` ile
`part_..._health` satırları birbirini reddetti ve `all_health` hiç uygulanmadı. Bu sürümde tek bir değeri
yazan satır kısayolu o değer için geçersiz kılıyor; artık birlikte yazılabilirler.

Bu kez exosuit yerine **arabayı (FRV)** kullanıyoruz: arabanın canını gösteren modla sayıları doğrudan
okuyabilirsin.

> **Her denemede `config.txt` içini tamamen sil, sadece o denemenin bloğunu yapıştır.** Eski satırlar
> kalırsa sonuçlar karışıyor.
>
> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.**

Dosya: `dist/HD2-Stat-Tuner-v0.12.1.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.12.1.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Config'i **gemideyken** kaydet, **F10**'a bas, sonra göreve in ve arabayı **o görevde** çağır.

Arabanın normal değerleri: ana can **2400**, kaput (`bonnet`) **150** can, zırh 2, hasarının **%100**'ü
ana cana gider.

Not: config'deki isim `frv`. Hiçbir şey değişmezse aynı blokları `frv_superearth` adıyla da dene ve
hangisinin tuttuğunu yaz.

## Deneme 1 — ana can tek başına

```ini
[vehicle: frv]
health = 5000
```

- Can modu arabanın canını **5000** gösteriyor mu?

## Deneme 2 — her şeyi birlikte ölçekle

```ini
[vehicle: frv]
all_health = 300%
```

`STATUS.txt` ilk satırı `OK - 30 values applied` olmalı (REJECTED olmamalı).

- Can modu **7200** gösteriyor mu?
- Kaputa ateş edince kaput, araba yok olmadan **önce** kırılıyor mu?

## Deneme 3 — kısayol + tek satır + uyarı (oynamaya gerek yok)

```ini
[vehicle: frv]
all_health = 300%
part_bonnet_health = 100000
```

`STATUS.txt` içinde:

- REJECTED **yok** mu?
- `part_bonnet_health` satırının yanında `WARNING: part bonnet has 100000 health ...` yazıyor mu?

## Deneme 4 — parçanın hasarı ana cana gitmesin

```ini
[vehicle: frv]
part_bonnet_health = 100000
part_bonnet_armor = 0
part_bonnet_to_main = 0
```

Yeni bir araba çağır. **Yalnızca kaputa** bir şarjör ateş et, can moduna bak.

- Ana can **hiç düşmüyor** mu? (düşmüyorsa `to_main` çalışıyor)

## Deneme 5 — karşılaştırma: hasarın yarısı ana cana gitsin

```ini
[vehicle: frv]
part_bonnet_health = 100000
part_bonnet_armor = 0
part_bonnet_to_main = 0.5
```

Yeni araba, yine yalnızca kaputa **aynı silahla bir şarjör**.

- Ana can ne kadar düştü? (sayıyı yaz)

Sonra config'i boşaltıp (**normal araba**) aynı şeyi bir kez daha yap ve kaput kırılana kadar ana canın
ne kadar düştüğünü yaz. Bu üç sayı `to_main`'in gerçekten oran olarak çalışıp çalışmadığını gösterir.

## Deneme 6 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Araba 2400 can mı?

## Bana göndereceklerin

Deneme 6'dan **önce** alınmış `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap |
|---|---|
| Hangi isim tuttu: `frv` / `frv_superearth`? | |
| 1: Can 5000 gösterdi | |
| 2: STATUS `OK - 30 values applied`, can 7200 | |
| 2: Kaput, araba yok olmadan önce kırıldı | |
| 3: REJECTED yok, WARNING var | |
| 4: Kaputa ateş edince ana can düşmedi | |
| 5: `to_main = 0.5` ile ana can ne kadar düştü? | |
| 5: Normal arabada ne kadar düştü? | |
| 6: Araba 2400 cana döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
