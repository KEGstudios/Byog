# TEST v0.1.0 — Recon (salt-okunur keşif)

Bu sürüm oyunda **hiçbir şeyi değiştirmez**. Sadece oyunun veri tablolarını bulur ve bir rapor
dosyası yazar. Silah değerlerinde bir fark görmeyeceksin; bu normal.

Dosya: `HD2-Stat-Tuner-Recon-v0.1.0.zip`

## Kurulum

1. **Bingus Shared Loader** kurulu ve açık olmalı (v15 veya üstü). Başka bir şey gerekmiyor.
2. Zip'i mod yöneticinle (HD2 Mod Manager / Arsenal) **içe aktar**, etkinleştir ve **Deploy** et.
   Zip'i elle `data` klasörüne açma.
3. Mümkünse bu test için değer değiştiren başka modları (ör. SHODAN Stat Editor) kapat.
   Kapatamıyorsan sorun değil, ama bana hangilerinin açık olduğunu yaz.

## Test adımları

1. Oyunu aç. Ana menüde sağ alttaki **oyun sürüm numarasını** not et.
2. Gemide **en az 2 dakika** bekle.
3. Herhangi bir göreve in (tek başına, en kolay zorluk yeter). Görevde **en az 4 dakika** kal.
   Bu sırada birkaç el ateş et, bir bomba at; özel bir şey yapman gerekmiyor.
4. Gemiye dön (ya da görevi bırak), **1 dakika** daha bekle.
5. Oyunu normal şekilde kapat.

Toplam süre 10 dakika civarı. Oyunu açtıktan sonraki ilk bir saat içinde yapman yeterli.

## Dikkat etmeni istediklerim

- Takılma / FPS düşüşü oldu mu? Olduysa **ne zaman** (açılışta mı, göreve inerken mi, sürekli mi)?
- Oyun çöktü mü ya da açılmadı mı?

## Bana göndereceklerin

Windows'ta `Win + R` tuşlarına bas, şunu yapıştır ve Enter'a bas:

```
%LOCALAPPDATA%\HD2StatTuner
```

Açılan klasördeki **iki dosyayı** gönder:

- `STATUS.txt`
- `recon.log`

Bu klasör **yoksa** mod hiç çalışmamış demektir. O zaman şu klasördeki dosyaları gönder:

```
%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs
```

- `BingusSharedLoader.log`
- varsa `HD2StatTuner-STATUS.txt`

Dosyalarla birlikte şunları da yaz:

1. Oyun sürüm numarası (1. adımda not ettiğin)
2. Açık olan diğer modlar
3. Takılma / çökme gözlemin (yoksa "yok" yaz)

## Test bittikten sonra

Bu modu mod yöneticisinden kapatabilir ya da silebilirsin; oyunda kalıcı hiçbir şey bırakmaz.
