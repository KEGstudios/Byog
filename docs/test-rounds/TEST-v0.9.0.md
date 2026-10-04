# TEST v0.9.0 — silaha özel patlama + kanarya testi

Bu sürümde patlama değerleri de silah silah ayrılıyor. Bunun için mod, oyunda kullanılmadığını
düşündüğümüz 24 patlama kaydından birini "ödünç alıyor". Bu kayıtların gerçekten kullanılmadığını
kanıtlayamıyoruz; **kanarya testi** tam bunu ölçmek için.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.** Başkalarının lobisine bu modla girme.
>
> Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve `tuner.log` dosyalarını
> yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.9.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.9.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, oyunda **F10**'a bas.

## Deneme 1 — kanarya (en önemlisi)

```ini
[settings]
canary = true
```

Bu ayar 24 aday patlama kaydını **sis bombası patlamasına** çevirir: hasar vermez, beyaz duman çıkarır.
Oyunda bir şey bu kayıtlardan birini kullanıyorsa normal patlaması yerine **duman** görürsün.

`STATUS.txt` ilk satırı `OK - 0 values applied, canary rows marked` olmalı (göreve indikten sonra).

Mümkün olduğunca **farklı şey** dene; 2-3 görev, mümkünse farklı düşman türleri:

- İniş kapsülü, ikmal kapsülü, stratagem kapsülleri yere inerken
- Eagle ve orbital saldırılar, taret ve mayın stratagemleri
- Hellbomb, patlayan variller / yakıt tankları, böcek yuvaları, fabrikalar
- Patlayarak ölen ya da patlayıcı atan düşmanlar
- Roket, el bombası, bomba atar gibi kendi patlayıcı silahların

Aradığımız: **patlaması gereken bir şeyin patlamayıp beyaz duman çıkarması**, ya da hasar vermesi
gereken bir patlamanın hasar vermemesi. Gördüğün her birini not et: ne, nerede, ne yaparken.
Hiç görmediysen onu da yaz; bu iyi haber.

## Deneme 2 — patlamalar silaha özel

```ini
[weapon: grenade_launcher]
blast_damage = 5000
blast_inner_radius = 15
blast_outer_radius = 15

[throwable: frag_grenade]
blast_damage = 1
```

`STATUS.txt` ilk satırı
`OK - 4 values applied, 1 weapons on their own bullet, 2 explosions of their own` olmalı.

- GL-21 bomba atarın patlaması çok daha güçlü ve geniş mi?
- Parça tesirli el bombası (frag) neredeyse hiç hasar vermiyor mu?
- Diğer el bombaların (HE, termit vb.) normal mi?
- Başka patlayan şeyler (roketler, otomatik top, taretler) normal mi?

## Deneme 3 — yedek şarjör uyarısı

```ini
[weapon: assault_rifle]
mags_start = 10
```

`STATUS.txt` içinde bu satırın yanında `WARNING: mags_start 10 is above mags_max 8` yazmalı (oyun
başlangıç sayısını üst sınıra indiriyor). Sonra şunu dene:

```ini
[weapon: assault_rifle]
mags_start = 10
mags_max = 12
```

- Yeni görevde Liberator **10** yedek şarjörle başladı mı?

## Deneme 4 — geri alma

`STATUS.txt` ve `tuner.log` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini tamamen boşalt,
kaydet, **F10**, yeni bir göreve in. Her şey normal mi?

## Bana göndereceklerin

Deneme 4'ten **önce** alınmış `STATUS.txt` ve `tuner.log`, kanarya notların ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: Kaç görev, hangi düşmanlar? | |
| 1: Beklenmedik duman / patlamayan şey gördün mü? Ne? | |
| 2: STATUS ilk satırı beklendiği gibi | |
| 2: GL-21 patlaması güçlü ve geniş | |
| 2: Frag bombası neredeyse hasarsız | |
| 2: Diğer bombalar ve patlayıcılar normal | |
| 3: Uyarı yazdı; mags_max ile 10 yedek geldi | |
| 4: Her şey normale döndü | |
| Tuhaflık / çökme? Ne yaparken? | |
