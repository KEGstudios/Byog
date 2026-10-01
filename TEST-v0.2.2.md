# TEST v0.2.2 — Silaha özel hasar (ikinci aday)

Önceki testte `damage_bonus` belleğe yazıldı ama oyunda etkisi olmadı. Oyunun verisinde bunun hemen
yanında ikinci bir "ekleme" alanı var ve oyunun kendi namlu eklentileri (Senator'ın uzun/kısa namlusu)
o alanı kullanıyor. Bu test, silaha özel hasarın o ikinci alandan gelip gelmediğini deniyor.

Değişiklikler sadece bellekte; oyunu kapatınca her şey eski haline döner. **Tek başına ya da özel
lobide** yap.

Dosya: `dist/HD2-Stat-Tuner-v0.2.2.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.2.2.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` dosyasını Not Defteri ile aç.

Her denemede `config.txt` içeriğini bloktakiyle **tamamen değiştir**, kaydet, oyunda **F10**'a bas.

## Deneme 1 — ikinci ekleme alanı

```ini
[weapon: assault_rifle]
ap_bonus = +5000
durable_ap_bonus = +5000
```

1. Gemide Liberator'ın **stat kartına** bak: hasar sayısı değişti mi?
2. Göreve in. Liberator küçük/orta düşmanları **tek mermide** öldürüyor mu?
3. Stalwart **normal** mi kaldı?

## Deneme 2 — ağır zırh

Aynı ayar açıkken Liberator ile **ağır zırhlı** bir düşmanın zırhlı yerine ateş et (Charger'ın önü,
Hulk'ın gövdesi, tank gibi; normalde Liberator mermisi sekiyor).

- Mermiler hâlâ sekiyor mu, yoksa artık hasar veriyor mu?

## Deneme 3 — ilk alan zırh delme mi?

```ini
[weapon: assault_rifle]
damage_bonus = 10
durable_damage_bonus = 10
```

Yine ağır zırhlı bir düşmanın zırhlı yerine ateş et.

- Mermiler sekiyor mu, yoksa hasar veriyor mu?

## Deneme 4 — geri alma

`config.txt` içini tamamen boşalt, kaydet, **F10**. Her şey normale döndü mü?

## Bana göndereceklerin

`%LOCALAPPDATA%\HD2StatTuner` klasöründen `STATUS.txt` ve `tuner.log`, ve şu tablo:

| Soru | Cevap (evet / hayır / emin değilim) |
|---|---|
| 1: Stat kartında hasar değişti | |
| 1: Liberator tek mermide öldürüyor | |
| 1: Stalwart normal kaldı | |
| 2: Ağır zırha hasar veriyor (sekmiyor) | |
| 3: Ağır zırha hasar veriyor (sekmiyor) | |
| 4: Her şey normale döndü | |
| Takılma ya da çökme oldu mu? | |
| Oyunu kapatınca Görev Yöneticisi'nde `helldivers2.exe` kaldı mı? | |
