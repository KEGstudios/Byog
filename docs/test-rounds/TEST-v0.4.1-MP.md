# TEST v0.4.1 — çok oyunculu deneme (2 kişi)

Soru: modu olan biri yeni mermisiyle ateş ederken, **modu olmayan** oyuncunun oyununda ne oluyor?

İki kişi gerekiyor:

- **M** = modu kuran oyuncu (`dist/HD2-Stat-Tuner-v0.4.1.zip`, Arsenal'da etkin)
- **N** = modu **olmayan** oyuncu (Stat Tuner kurulu değil)

> **N'nin oyunu çökebilir.** Bu denemenin amacı zaten bunu öğrenmek. Özel lobide, sadece ikiniz
> oynayın; rastgele oyuncu almayın.

Her turda M, `%LOCALAPPDATA%\HD2StatTuner\config.txt` içeriğini bloktakiyle **tamamen değiştirir**,
kaydeder ve oyunda **F10**'a basar. M, Liberator kuşanır. Kolay bir görev yeter.

## Tur 1 — var olan kayıt (kontrol turu)

M'nin config'i:

```ini
[weapon: assault_rifle]
own_bullet = true
damage = 5000
durable_damage = 5000
```

Lobiyi **M kursun**, N katılsın. Göreve inin. M'nin `STATUS.txt` dosyasında `OWN BULLET ACTIVE` yazmalı.
M birkaç şarjör ateş etsin (düşmana, yere, duvara). N yanında durup izlesin.

## Tur 2 — yeni kayıt, lobiyi M kuruyor

M'nin config'i:

```ini
[weapon: assault_rifle]
own_bullet = new
damage = 5000
durable_damage = 5000
```

Lobiyi **M kursun**, N katılsın. `STATUS.txt` içinde `OWN BULLET ACTIVE ... NEW ID` yazmalı.
Yine M ateş etsin, N izlesin. Sonra M Liberator'ı **yere bıraksın**, N alıp ateş etsin.

## Tur 3 — yeni kayıt, lobiyi N kuruyor

Config Tur 2 ile aynı. Bu sefer lobiyi **N kursun**, M katılsın. Aynı şeyleri yapın.

Bir turda N'nin oyunu çökerse o turu bırakın, sonrakine geçin ve **tam ne olurken** çöktüğünü yazın
(M ilk ateş ettiğinde mi, göreve inerken mi, silahı alınca mı).

## Bana göndereceklerin

M'nin klasöründen `STATUS.txt` ve `tuner.log` (en sonda bir kez yeter) ve şu tablo:

| Soru | Tur 1 | Tur 2 | Tur 3 |
|---|---|---|---|
| M'de `OWN BULLET ACTIVE` yazdı mı? | | | |
| M ateş edince N'nin oyunu çöktü / dondu mu? | | | |
| N, M'nin mermi izini ve sesini görüp duydu mu? | | | |
| M'nin vurduğu düşman N'nin ekranında da tek mermide öldü mü? | | | |
| M'nin oyununda tuhaflık oldu mu? (hasar vermeyen mermi, çökme...) | | | |
| N, M'nin Liberator'ını alıp ateş edebildi mi? Ne oldu? | — | | |
| Bağlantı kopması / "senkron" hatası oldu mu? | | | |
