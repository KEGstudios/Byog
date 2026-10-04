# TEST v0.14.0 — taret düzeltmesi, orbital mermileri ayrı, ekrana çizim denemesi

Bu sürümde:

- **Taret düzeltmesi.** Geçen testte taret değişmedi çünkü oyun taretin (ve MG-43'ün) mermisini silah
  kaydından değil, şarjörün "kemer düzeninden" alıyormuş. Artık oradaki her giriş de değiştiriliyor;
  izli mermiler dahil.
- **Orbital ve Eagle mermileri** artık kendi kayıtlarına ayrılıyor (başka bir şeyle paylaşmıyorlar).
- **Araştırma:** oyunun Lua tarafının daha ayrıntılı dökümü, ve oyun içi menü için ilk çizim denemesi.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.**
>
> Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve `tuner.log` dosyalarını
> yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.14.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.14.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

## Bölüm 1 — tek config, hepsi birden

`config.txt` içini **tamamen sil**, aşağıdakini yapıştır, kaydet. Oyunu aç, **gemideyken F10**, sonra
göreve in. Yanına al: Machine Gun Sentry, Gatling Sentry, Orbital Precision Strike, MG-43.

```ini
[settings]
dump_globals = true

[stratagem_weapon: turret_machinegun_gpmg]
damage = 2000

[weapon: machinegun]
damage = 5

[stratagem_weapon: gatling_turret]
rpm = 25%

[stratagem_weapon: orbital_precision_strike]
blast_inner_radius = 40
blast_outer_radius = 40
```

`STATUS.txt` içinde REJECTED olmamalı.

1. **Makineli taret** düşmanları tek mermide öldürüyor mu? (izli mermiler dahil, her mermi)
2. **MG-43** (elde) neredeyse **hiç hasar vermiyor** mu? (aynı mermiyi atıyorlar; artık ters yönde ayrı)
3. **Gatling taret** belirgin şekilde **yavaş** mı ateş ediyor, hasarı normal mi?
4. **Orbital Precision Strike** yine çok geniş bir alanı mı yok ediyor?
5. `GLOBALS.txt` oluştu mu? (geçen seferkinden çok daha uzun olmalı)

`STATUS.txt`, `tuner.log`, `GLOBALS.txt` dosyalarını kopyala.

## Bölüm 2 — ekrana çizim denemesi (en sonda)

Bu, oyun içi menünün mümkün olup olmadığını gösterecek. **Oyunu kapatabilir**; o yüzden en sona
bıraktık. `config.txt` içini tamamen sil, şunu yapıştır, kaydet, oyunu **yeniden başlat**:

```ini
[settings]
ui_probe = text
```

- Ana menüde, gemide ya da görevde ekranın **sol üst köşesinde sarı bir dikdörtgen** görünüyor mu?
- İçinde **"BYOG"** yazısı var mı?
- Oyun kapandı mı / hata verdi mi? Ne zaman?

Aynı klasördeki **`UIPROBE.txt`** dosyasını gönder (oyun kapansa bile dosya orada olmalı).

## Geri alma

`config.txt` içini tamamen boşalt, kaydet, oyunu yeniden başlat, bir göreve in. Her şey normal mi?

## Bana göndereceklerin

`STATUS.txt`, `tuner.log`, `GLOBALS.txt` (Bölüm 1), `UIPROBE.txt` (Bölüm 2), ve şu tablo:

| Soru | Cevap |
|---|---|
| STATUS'ta REJECTED yok | |
| 1: Taret tek mermide öldürüyor | |
| 2: MG-43 neredeyse hasarsız | |
| 3: Gatling taret yavaş, hasarı normal | |
| 4: Precision Strike çok geniş | |
| 5: GLOBALS.txt oluştu | |
| Bölüm 2: Sarı dikdörtgen göründü mü? Nerede? | |
| Bölüm 2: "BYOG" yazısı göründü mü? | |
| Bölüm 2: Oyun kapandı mı? Ne zaman? | |
| Geri alınca her şey normal | |
| Tuhaflık / çökme? Ne yaparken? | |
