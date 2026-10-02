# TEST v0.3.2 — ikinci sonda (sadece okur)

Bu sürüm oyunda **hiçbir şeyi değiştirmiyor**. Tek işi şunu öğrenmek: oyun mermi / hasar / patlama
kayıtlarını bulmak için kullandığı listeleri nerede tutuyor ve hangi kod bu listeleri kullanıyor.
Buna göre oyuna yeni mermi kaydı eklemenin mümkün olup olmadığına karar vereceğiz.

Dosya: `dist/HD2-Stat-Tuner-v0.3.2.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.3.2.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner` klasöründeki eski `PROBE.txt` dosyasını sil.
4. `%LOCALAPPDATA%\HD2StatTuner\config.txt` içeriğini **tamamen** şununla değiştir ve kaydet:

```ini
[settings]
probe = true
```

## Deneme

1. Oyunu aç. **Tek başına ya da özel lobide**, kolay bir göreve in.
   (Sonda gemide başlamaz: hasar tablosu ancak görev yüklenince geliyor. `STATUS.txt` o sırada
   `waiting for DamageSettings` yazar, bu normal.)
2. Görevde güvenli bir yerde **5 dakika** bekle. Savaşmana gerek yok.
3. Klasörde yeni `PROBE.txt` belirince tarama bitmiştir. Görevi bitirebilir ya da oyunu kapatabilirsin.

5 dakikada `PROBE.txt` oluşmadıysa bir 5 dakika daha bekle; yine yoksa `STATUS.txt` ve `tuner.log`
dosyalarını gönder.

## Bana göndereceklerin

`%LOCALAPPDATA%\HD2StatTuner` klasöründen **üç dosya**: `STATUS.txt`, `tuner.log`, `PROBE.txt`.

| Soru | Cevap |
|---|---|
| `PROBE.txt` oluştu mu? Yaklaşık kaç dakikada? | |
| Tarama sırasında takılma hissettin mi? | |
| Çökme oldu mu? Ne zaman? | |
