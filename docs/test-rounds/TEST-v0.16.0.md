# TEST v0.16.0 — menüde arama + taret ömrü

Yeni olanlar:

- **Arama.** Menü açıkken eşya listesindeyken yazmaya başla: bütün kategorilerde, oyundaki adda ya da iç
  adda geçen her eşya listelenir. **Backspace** bir harf siler, **Delete** aramayı temizler.
- **Taret ömrü** (`lifetime_seconds`): taretlerin, Tesla kulesinin ve kalkan rölesinin kendiliğinden yok
  olmadan önce kaldığı süre. Normal değerler: taretler 150 sn, havan taretleri 180 sn, kalkan rölesi 40 sn.

Hâlâ oyunda görmediklerimiz (önceki turlardan): MG-43 hasarı, menüden yapılan değişikliğin oyunu yeniden
açınca kalması. Bu listede onlar da var.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.**
>
> Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve `tuner.log` dosyalarını
> yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.16.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.16.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` içi **boş** olsun. `menu.txt` varsa sil (temiz başlayalım).

## Menü tuşları

| Tuş | Ne yapar |
|---|---|
| **F9** | Menüyü aç / kapat |
| **Yukarı / Aşağı**, **PageUp / PageDown** | Listede gez (on satır atla) |
| **Tab** | Eşya listesi ↔ değer listesi |
| **Sol / Sağ** | Eşya listesinde: kategori. Değer listesinde: değeri azalt / artır (**Shift**: on kat) |
| **Delete** | Değer listesinde: oyunun değerine dön. Eşya listesinde: aramayı temizle |
| **Harf / rakam** | Eşya listesinde: ara. **Backspace**: bir harf sil |

Not: menü açıkken oyun da tuşları alıyor; arama yazarken karakterin hareket edebilir. Gemide kullan.

## Bölüm 1 — arama

Gemide **F9**, sonra `sentry` yaz.

- Listede yalnızca taretler mi kaldı (başka kategorilerden de olsa)? Altta `search: sentry_` yazıyor mu?
- **Backspace** ile silince liste eski haline dönüyor mu?
- `lib` yazınca Liberator'lar geliyor mu?

## Bölüm 2 — menüden ayarla, oyunda gör

Aramayla bulup ayarla (eşyanın üstündeyken **Tab**, değerin üstünde sağ / sol):

1. **Machine Gun Sentry (gun)** → `lifetime_seconds` = **30** (Shift + sol)
2. **MG-43 Machine Gun** → `damage` = **5**
3. **Orbital Precision Strike** (kategori `stratagem`) → `cooldown` = **10**

Menüyü kapat, göreve in.

- Makineli taret yaklaşık **30 saniye** sonra kendiliğinden yok oldu mu? (normali 150)
- **MG-43** neredeyse hasarsız mı?
- Precision Strike 10 saniyede doluyor mu?

## Bölüm 3 — kalıcılık

Oyunu kapat, yeniden aç, göreve in.

- Üç ayar da duruyor mu?

## Geri alma

`STATUS.txt`, `tuner.log`, `menu.txt` dosyalarını kopyala. Sonra `menu.txt` dosyasını sil, oyunu yeniden
başlat. Her şey normal mi?

## Bana göndereceklerin

`STATUS.txt`, `tuner.log`, `menu.txt`, mümkünse menünün bir ekran görüntüsü, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: Arama çalışıyor (yaz / sil / temizle) | |
| 2: Taret ~30 sn sonra yok oldu | |
| 2: MG-43 neredeyse hasarsız | |
| 2: Precision Strike 10 sn | |
| 3: Yeniden açınca ayarlar duruyor | |
| Geri alınca her şey normal | |
| Yanlış / fazla / eksik isimler (iç ad → doğru ad) | |
| 1.0.0 için menüde eksik gördüğün ne var? | |
| Tuhaflık / çökme? Ne yaparken? | |
