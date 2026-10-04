# TEST v0.7.0 — şarjör değerleri

Bu sürümde şarjör kapasitesi ve yedek şarjör sayısı ilk kez değiştirilebiliyor. Oyunda bazı silahların
şarjör değerleri silahın kendisinde değil, **takılı şarjör eklentisinde** duruyor; mod artık oraya yazıyor.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.** Başkalarının lobisine bu modla girme.

Dosya: `dist/HD2-Stat-Tuner-v0.7.0.zip`

## Önce: silahlarda fabrika şarjörü takılı olsun

Gemideki silah özelleştirme ekranında **Liberator** ve **Peacemaker** için şarjörü değiştirdiysen
varsayılana geri al (Liberator: 45'lik şarjör). Başka şarjör takılıysa mod onu değiştirmez; o zaman
hangisinin takılı olduğunu bana yaz.

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.7.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, oyunda **F10**'a bas.

## Deneme 1 — şarjör değerleri

Göreve **inmeden önce** (gemideyken) config'i kaydet ve F10'a bas, sonra göreve in.

```ini
[weapon: assault_rifle]
capacity = 100
mags_start = 10
mags_max = 12

[weapon: standard_pistol]
capacity = 150%

[weapon: machinegun]
capacity = 300
```

Yanına al: Liberator, Peacemaker, MG-43. Bakılacaklar:

- Liberator'ın şarjöründe **100** mermi var mı? (normali 45)
- Liberator **10** yedek şarjörle mi başladı? (normali 6)
- Peacemaker'ın şarjörü **23** mü? (normali 15)
- MG-43'ün şarjörü **300** mü? (normali 175)
- İkmal kutusundan sonra Liberator'ın yedek şarjörü 8'i geçip **12**'ye kadar çıkıyor mu?

## Deneme 2 — görevdeyken değiştirmek

Görevdeyken `capacity = 100` satırını `capacity = 60` yap, kaydet, F10.

- Elindeki Liberator hemen 60'a döndü mü, yoksa şarjör değiştirince / ölüp yeniden inince mi değişti,
  yoksa hiç değişmedi mi?

## Deneme 3 — aynı şarjörü kullanan başka silah

Liberator'ın şarjörünü oyunda iki silah daha kullanıyor. Deneme 1'in config'i açıkken yanına
**Liberator Penetrator** (AR-23P) al.

- Onun şarjörü de 100 mü olmuş? (Bu sürümde olması bekleniyor; `STATUS.txt` içinde `also affects`
  diye yazıyor.)

## Deneme 4 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Hepsi normale döndü mü?

## Bana göndereceklerin

Deneme 4'ten **önce** alınmış `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: Liberator şarjörü 100 | |
| 1: Liberator 10 yedek şarjörle başladı | |
| 1: Peacemaker şarjörü 23 | |
| 1: MG-43 şarjörü 300 | |
| 1: İkmalden sonra yedek şarjör 12'ye çıkıyor | |
| 2: Görevdeyken 60 yapınca ne zaman değişti? | |
| 3: Liberator Penetrator da 100 oldu mu? | |
| 4: Her şey normale döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
