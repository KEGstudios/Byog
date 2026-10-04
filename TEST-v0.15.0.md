# TEST v0.15.0 — oyun içi menü (ilk sürüm) + MG-43 düzeltmesi

Bu sürümde:

- **Oyun içi menü.** **F9** ile ekranın ortasında açılır. Kategoriler, eşya listesi ve değerler; değeri
  ok tuşlarıyla değiştirirsin, oyun anında uygular. Yapılan değişiklikler `menu.txt` dosyasında saklanır
  ve oyunu kapatıp açınca geri gelir.
- **Tabloların kaybolması düzeltildi.** Geçen testte MG-43'ün değişmemesinin nedeni buydu: Windows,
  oyunun bir süredir dokunmadığı bellek sayfalarını geçici olarak kaldırıyor; mod o zaman tabloları
  bulamayıp bekliyordu. Artık buluyor.

> **Tek başına ya da sadece arkadaşlarınla özel lobide oyna.**
>
> Oyun kapanırsa ya da donarsa: ne yaparken olduğunu yaz, `STATUS.txt` ve `tuner.log` dosyalarını
> yine gönder.

Dosya: `dist/HD2-Stat-Tuner-v0.15.0.zip`

## Kurulum

1. Arsenal'da eski **HD2 Stat Tuner**'ı sil.
2. `HD2-Stat-Tuner-v0.15.0.zip` dosyasını Arsenal'a ekle, etkinleştir, **Deploy** et.
3. `%LOCALAPPDATA%\HD2StatTuner\config.txt` içini **tamamen boşalt** ve kaydet (bu testte her şeyi
   menüden yapacağız).

## Menü tuşları

| Tuş | Ne yapar |
|---|---|
| **F9** | Menüyü aç / kapat |
| **Yukarı / Aşağı** | Listede gez |
| **PageUp / PageDown** | On satır atla |
| **Tab** | Eşya listesi ↔ değer listesi |
| **Sol / Sağ** | Eşya listesindeyken: kategori değiştir. Değer listesindeyken: değeri azalt / artır |
| **Shift + Sol / Sağ** | On kat büyük adım |
| **Delete** | Seçili değeri oyunun kendi değerine döndür |

Not: menü açıkken oyun tuşları almaya devam ediyor. Ok tuşlarıyla stratagem giriyorsan menüyü gemide
ya da güvenli bir anda kullan.

## Bölüm 1 — menü görünüyor mu?

Gemide **F9**'a bas.

- Panel ekranın **ortasında** mı? Yazılar okunuyor mu, taşan / üst üste binen bir şey var mı?
  (Bir ekran görüntüsü çok işime yarar.)
- Yukarı / aşağı, Tab, sol / sağ beklendiği gibi çalışıyor mu?
- F9 ile kapanıyor mu?

## Bölüm 2 — menüden değiştir, oyunda gör

Menüden şunları ayarla (eşyayı bul, **Tab**, değerin üstüne gel, sağ / sol):

1. `weapon` → `machinegun` → `damage` = **5** (Shift + sol hızlı indirir)
2. `stratagem_weapon` → `turret_machinegun_gpmg` → `damage` = **500 ya da üstü** (Shift + sağ tuşunu basılı tut)
3. `weapon` → `assault_rifle` → `rpm` = **1200** civarı
4. `stratagem` → `orbital_precision_strike` → `cooldown` = **10**

Menüyü kapat, göreve in.

- **MG-43** neredeyse hasarsız mı? (geçen testte değişmemişti)
- **Makineli taret** tek mermide öldürüyor mu?
- **Liberator** çok hızlı mı atıyor?
- **Precision Strike** 10 saniyede mi doluyor?

## Bölüm 3 — görevde değiştir

Görevdeyken F9, Liberator `rpm` değerini **Delete** ile sıfırla, menüyü kapat.

- Atış hızı hemen normale döndü mü?
- Menü görevde de ortada ve okunaklı mı?

## Bölüm 4 — kalıcılık

Oyunu kapat, yeniden aç, göreve in (config.txt hâlâ boş).

- MG-43 ve taret ayarları duruyor mu? (`menu.txt` sayesinde durmalı)

## Geri alma

`STATUS.txt`, `tuner.log` ve `menu.txt` dosyalarını kopyala. Sonra `menu.txt` dosyasını **sil**, oyunu
yeniden başlat. Her şey normal mi?

## Bana göndereceklerin

`STATUS.txt`, `tuner.log`, `menu.txt`, mümkünse menünün bir ekran görüntüsü, ve şu tablo:

| Soru | Cevap |
|---|---|
| 1: Menü ortada ve okunaklı | |
| 1: Tuşlar beklendiği gibi | |
| 2: MG-43 neredeyse hasarsız | |
| 2: Taret tek mermide öldürüyor | |
| 2: Liberator hızlı | |
| 2: Precision Strike 10 sn | |
| 3: Görevde Delete ile hemen normale döndü | |
| 4: Yeniden açınca ayarlar duruyor | |
| Geri alınca her şey normal | |
| Menüde eksik / rahatsız eden ne var? | |
| Tuhaflık / çökme? Ne yaparken? | |
