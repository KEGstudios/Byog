# TEST v0.2.0 — İlk değer değiştirme denemesi

Bu sürüm oyundaki değerleri **gerçekten değiştirir** (sadece bellekte; oyun dosyalarına dokunmaz,
oyunu kapatınca her şey eski haline döner). Testi **tek başına ya da özel lobide** yap.

Dosya: `dist/HD2-Stat-Tuner-v0.2.0.zip`

## Kurulum

1. Arsenal'da **HD2 Stat Tuner Recon**'u kapat ya da sil (eski keşif sürümü; ikisi aynı anda açık olmasın).
2. `HD2-Stat-Tuner-v0.2.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. Oyunu bir kez aç, ana menüde **yarım dakika** bekle, sonra kapat. Bu, ayar dosyasını oluşturur.
4. `Win + R` → `%LOCALAPPDATA%\HD2StatTuner` klasörünü aç. İçinde `config.txt` olmalı.

Ayarı değiştirmek için `config.txt` dosyasını Not Defteri ile açıp içeriğini aşağıdaki
bloklardan biriyle **tamamen değiştir**, kaydet. Oyun açıkken değiştirdiysen oyunda **F10**'a bas.

## Deneme 1 — ortak hasar değeri

`config.txt` içeriği:

```ini
[weapon: assault_rifle]
damage = 5000
durable_damage = 5000
```

Liberator (AR-23) ile bir göreve in ve ateş et.

- Liberator küçük/orta düşmanları **tek mermide** öldürüyor mu?
- Aynı görevde Stalwart ile de dene: o da tek mermide öldürüyor mu? (Öldürmesi bekleniyor; ikisi aynı
  mermiyi kullanıyor.)

## Deneme 2 — sadece o silaha özel hasar

Oyunu kapatmadan `config.txt` içeriğini şununla değiştir, kaydet, oyunda **F10**'a bas:

```ini
[weapon: assault_rifle]
damage_bonus = +5000
durable_damage_bonus = +5000
```

- Liberator hâlâ tek mermide öldürüyor mu?
- Stalwart **normale döndü mü**? (Bu denemenin asıl sorusu bu.)

Fark görmezsen silahı yere bırakıp tekrar al ya da yeni bir göreve in ve tekrar bak; hangisinden sonra
değiştiğini not et.

## Deneme 3 — atış hızı

```ini
[weapon: assault_rifle]
rpm = 200%
```

Kaydet, **F10**. Liberator gözle görülür şekilde daha hızlı ateş ediyor mu?

## Deneme 4 — geri alma

`config.txt` içindeki her şeyi sil (boş dosya), kaydet, **F10**. Liberator normale döndü mü?

## Bana göndereceklerin

`%LOCALAPPDATA%\HD2StatTuner` klasöründen:

- `STATUS.txt`
- `tuner.log`

Her denemeden sonra `STATUS.txt` değişir; en kolayı **her denemenin sonunda dosyayı kopyalayıp adını
değiştirmek** (`STATUS-1.txt`, `STATUS-2.txt`, ...). Yapamazsan sadece en sondakini gönder.

Ve şu tabloyu doldur:

| Deneme | Sonuç (evet / hayır / emin değilim) | Not |
|---|---|---|
| 1: Liberator tek mermi | | |
| 1: Stalwart da tek mermi | | |
| 2: Liberator tek mermi | | |
| 2: Stalwart normale döndü | | |
| 3: Liberator daha hızlı | | |
| 4: Her şey normale döndü | | |
| Değişiklik hemen mi geçerli oldu, yoksa silahı yeniden alınca / yeni görevde mi? | | |
| Takılma ya da çökme oldu mu? Ne zaman? | | |

## Bir şey ters giderse

- `STATUS.txt` dosyasının **ilk satırı** ne olduğunu söyler. `REFUSED` yazıyorsa oyun güncellenmiş
  demektir; mod bu durumda bilerek hiçbir şey yazmaz. Dosyayı bana gönder.
- `PARTIAL ... waiting for their table` yazıyorsa bazı tablolar henüz yüklenmemiş; bir göreve inince
  yarım dakika içinde kendiliğinden uygulanır.
- Modu kapatmak için Arsenal'dan devre dışı bırakman yeterli.
