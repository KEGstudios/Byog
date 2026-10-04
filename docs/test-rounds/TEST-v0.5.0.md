# TEST v0.5.0 — her silaha kendi mermisi ve kendi hasar kaydı

v0.4.1 Liberator'a yeni bir **mermi** kaydı veriyordu, hasar kaydı ise oyundaki boş bir kayıttı.
Bu sürümde **hasar kaydı da yeni**, ve bu artık mermi atan **bütün silahlar** için kullanılabiliyor.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna. Başkalarının lobisine bu modla girme:**
> oyunları çökebilir ve onların oyununu bozmuş olursun.

Deneysel sürüm: çökme mümkün. Çökerse **tam ne yaparken** olduğunu yaz.

Dosya: `dist/HD2-Stat-Tuner-v0.5.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.5.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, oyunda **F10**'a bas.

## Deneme 1 — Liberator, yeni hasar kaydı

```ini
[weapon: assault_rifle]
own_bullet = new
damage = 5000
durable_damage = 5000
```

Göreve in. `STATUS.txt` içinde şu yazmalı:
`OWN BULLET ACTIVE: projectile row 276 -> NEW ID ..., damage row 108 -> NEW ID ...`

- Liberator düşmanları tek mermide öldürüyor mu?
- Mermi izi, ses, isabet efekti normal mi?
- Stalwart normal mi?

## Deneme 2 — altı silah birden

```ini
[weapon: assault_rifle]
own_bullet = new
damage = 5000
durable_damage = 5000

[weapon: lmg_stalwart]
own_bullet = new
damage = 1

[weapon: standard_pistol]
own_bullet = new
damage = 5000

[weapon: machinegun]
own_bullet = new

[weapon: grenade_launcher]
own_bullet = new

[weapon: recoilless_rifle]
own_bullet = new
```

Beklenen:

| Silah | Beklenen |
|---|---|
| Liberator | tek mermide öldürür |
| Stalwart | neredeyse hiç hasar vermez (hasar 1) |
| Peacemaker (başlangıç tabancası) | tek mermide öldürür |
| MG-43 Machine Gun | **tamamen normal** |
| GL-21 Grenade Launcher | **tamamen normal** (patlama, ses, hasar) |
| Recoilless Rifle | **tamamen normal** (roket, patlama, zırhlı hedefe hasar) |

Hepsini tek görevde deneyemezsen birkaç göreve böl; hangisini denediğini yaz.

## Deneme 3 — ikinci görev

Deneme 2 açıkken görevi bitir, yeni bir göreve in. Liberator hâlâ tek atıyor, Stalwart hâlâ güçsüz mü?

## Deneme 4 — geri alma

`config.txt` içini tamamen boşalt, kaydet, **F10**. Hepsi normale döndü mü?

## Bana göndereceklerin

Deneme 4'ten **önce** `STATUS.txt` ve `tuner.log` dosyalarının birer kopyası, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: `NEW ID` iki kere yazdı (mermi ve hasar) | |
| 1: Liberator tek atıyor, Stalwart normal | |
| 2: Liberator tek atıyor | |
| 2: Stalwart neredeyse hasar vermiyor | |
| 2: Peacemaker tek atıyor | |
| 2: MG-43 normal | |
| 2: Grenade Launcher normal | |
| 2: Recoilless Rifle normal | |
| 3: İkinci görevde de aynı | |
| 4: Her şey normale döndü | |
| Tuhaflık / çökme / takılma? Ne yaparken? | |
