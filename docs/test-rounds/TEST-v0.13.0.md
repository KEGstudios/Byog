# TEST v0.13.0 — büyük paket: stratagem silahları, "şunun gibi patla", durum etkileri

Bu sürümde birkaç yeni özellik birden var; tek bir test turunda hepsine bakıyoruz.

- **`[stratagem_weapon: ...]`**: taretlerin, mevzilerin, drone'ların, exosuit silahlarının ve Eagle'ın
  silahları; orbital ve Eagle saldırılarının mermileri. 53 yeni eşya, isimleri `catalog.txt` içinde.
- **`blast_from = <eşya>`**: bir silah ya da bomba, başka bir eşyanın patlamasını kullanır.
- **Durum etkileri**: bir merminin ya da patlamanın uyguladığı etki (ateş, gaz, sersemletme...).
  Numaralar `docs/STATUS-EFFECTS.md` içinde.
- **`dump_globals`** (araştırma): oyun içi menü için oyunun bize neler sunduğunu listeler.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.**
>
> Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve `tuner.log` dosyalarını
> yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.13.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.13.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

## Tek config, hepsi birden

`config.txt` içini **tamamen sil**, aşağıdakini yapıştır, kaydet. Oyunu aç, **gemideyken F10**, sonra
göreve in. Yanına al: Machine Gun Sentry, Orbital Precision Strike, Grenade Launcher, frag el bombası,
Liberator, MG-43.

```ini
[settings]
dump_globals = true

[stratagem_weapon: turret_machinegun_gpmg]
damage = 2000

[stratagem_weapon: orbital_precision_strike]
blast_inner_radius = 40
blast_outer_radius = 40

[weapon: grenade_launcher]
blast_from = gas_grenade

[throwable: frag_grenade]
blast_from = incendiary_grenade

[weapon: assault_rifle]
status1_type = 5
status1_value = 50
```

`STATUS.txt` içinde REJECTED olmamalı.

Bakılacaklar:

1. **Makineli taret** düşmanları tek mermide öldürüyor mu? (normali 90 hasar)
2. Aynı mermiyi atan **MG-43** (elde) **normal** hasar mı veriyor?
3. **Orbital Precision Strike** çok daha geniş bir alanı mı yok ediyor? (normali 4 / 12 metre)
4. **Grenade Launcher** patlayınca **gaz bulutu** mu bırakıyor? Normal patlama hasarı kaldı mı, gitti mi?
5. **Frag bombası** patlayınca **ateş** mi bırakıyor?
6. **Liberator** mermileri düşmanları **tutuşturuyor** mu? (`status1_type = 5` ateş demek)
7. Aynı klasörde **`GLOBALS.txt`** oluştu mu? (oluştuysa gönder; bununla oyun içi menüyü araştıracağım)

## Geri alma

`STATUS.txt`, `tuner.log` ve `GLOBALS.txt` dosyalarını **şimdi** kopyala. Sonra `config.txt` içini
tamamen boşalt, kaydet, **F10**, yeni bir göreve in. Her şey normal mi?

## Bana göndereceklerin

Geri almadan **önce** alınmış `STATUS.txt`, `tuner.log`, `GLOBALS.txt`, ve şu tablo:

| Soru | Cevap |
|---|---|
| STATUS'ta REJECTED yok | |
| 1: Taret tek mermide öldürüyor | |
| 2: MG-43 normal | |
| 3: Precision Strike çok daha geniş | |
| 4: GL gaz bırakıyor (patlama hasarı ne oldu?) | |
| 5: Frag ateş bırakıyor | |
| 6: Liberator tutuşturuyor | |
| 7: GLOBALS.txt oluştu | |
| Geri alınca her şey normal | |
| Tuhaflık / çökme? Ne yaparken? | |
