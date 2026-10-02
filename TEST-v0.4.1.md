# TEST v0.4.1 — Liberator'a yepyeni bir mermi kaydı

Önceki sürüm Liberator'a oyunda **kullanılmayan** bir mermi kaydını veriyordu. Bu sürüm oyunda
**hiç olmayan** yeni bir mermi kaydı üretiyor. Çalışırsa "boş kayıt sayısı" sınırı kalkar.

> **Mutlaka tek başına oyna** (özel lobi, yanında kimse olmasın). Bu yeni mermi sadece modu kuran
> oyunda var; başkasının oyunu bu mermiyi tanımaz ve çökebilir.

Bu deneysel bir sürüm: oyunun çökmesi mümkün. Çökerse **ne yaparken çöktüğünü** yaz, bu da bir sonuç.
Değişiklikler sadece bellekte; oyunu kapatınca her şey eski haline döner.

Dosya: `dist/HD2-Stat-Tuner-v0.4.1.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.4.1.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, oyunda **F10**'a bas.

## Deneme 1 — sadece yeni mermi

```ini
[weapon: assault_rifle]
own_bullet = new
```

1. Gemide kaydet, F10. Liberator'ı kuşan, kolay bir göreve in.
2. `STATUS.txt` içinde `OWN BULLET ACTIVE: projectile row 276 -> NEW ID ...` yazmalı
   (göreve indikten sonra yarım dakika içinde; `WAITING` yazıyorsa 2 dakika bekle ya da F10'a bas).
3. Liberator ile ateş et. Her şey **tamamen normal** olmalı:
   - mermi çıkıyor mu, izi ve sesi normal mi?
   - düşmana hasar veriyor mu, isabet efekti (kan, kıvılcım) normal mi?
   - zemine / duvara ateş edince iz ve sekme normal mi?
   - şarjör değiştirince hâlâ normal mi?

## Deneme 2 — sadece Liberator'ın hasarı

```ini
[weapon: assault_rifle]
own_bullet = new
damage = 5000
durable_damage = 5000
```

1. Görevdeyken kaydet, F10.
2. Liberator küçük/orta düşmanları tek mermide öldürüyor mu?
3. **Stalwart normal mi?** (Aynı mermiyi paylaşıyordu; değişmemesi lazım.)

## Deneme 3 — dayanıklılık

Deneme 2 açıkken görevi **sonuna kadar oyna ve çıkış yap**. Sonra **ikinci bir göreve** in.
İkinci görevde Liberator hâlâ tek mermide öldürüyor mu? (`STATUS.txt` yine `ACTIVE` olmalı.)

## Deneme 4 — geri alma

`config.txt` içini tamamen boşalt, kaydet, **F10**. Liberator normale döndü mü?

## Bana göndereceklerin

`%LOCALAPPDATA%\HD2StatTuner` klasöründen `STATUS.txt` ve `tuner.log` (Deneme 4'ten **önce** birer
kopyasını al, sonra bir de en sondakini gönder), ve şu tablo:

| Soru | Cevap (evet / hayır / emin değilim) |
|---|---|
| 1: `OWN BULLET ACTIVE ... NEW ID` yazdı | |
| 1: Liberator tamamen normal (mermi, ses, iz, hasar, efekt) | |
| 2: Liberator tek mermide öldürüyor | |
| 2: Stalwart normal | |
| 3: İkinci görevde de çalışıyor | |
| 4: Her şey normale döndü | |
| Tuhaflık gördün mü? (görünmeyen mermi, yanlış ses, hasar vermeyen mermi...) | |
| Çökme / takılma oldu mu? Tam olarak ne yaparken? | |
