# TEST v2.0.0 — fare, zırhlar, pasifler, yeni değerler

v1.1.17'den beri oyunda hiçbir şey denenmedi: bu liste v1.2.0 listesini de içerir. Çevrimdışı testlerin
hepsi geçiyor. Yeni olanlar: **fare**, **Armor** ve **Passives** sekmeleri, şarjlı silahlar / wind-up /
beam / arc değerleri, taret ve düşman canı, status hasarı, alev silahları (Flame Sentry, Hot Dog...),
jump / hover / warp pack, taret dönüş hızı, eklentiler (**Attach.** sekmesi), şarapnel, Solo Silo füzesi,
LAS-22 Shear geri geldi, düşmanlar kendi sekmesinde ve adlarının başında fraksiyon var.

> Tuşlar: **F9** aç/kapat, **F6 / F7** sayfa, **oklar** gezin, **Tab** sütun, **Enter** seç / ara /
> değer yaz / onayla, **Esc** vazgeç, **Delete** sıfırla, **F3** ara, **Shift** on kat.

## Kurulum

1. Arsenal'da eski BYOG'u sil, `BYOG-v2.0.0.zip` dosyasını ekle, etkinleştir, **Deploy** et.
2. `%LOCALAPPDATA%\BYOG` klasörüne dokunma.
3. Başka bir zırh modu (Armory Forge, Passive Picker) kuruluysa önce onsuz dene.

## M. Fare (yeni)

1. Menüyü aç, fareyi oynat: menünün kendi imleci görünüyor mu? Oyunun imleci / kamerası oynuyor mu (oynamamalı)?
2. İmleç farenin gittiği yere tam gidiyor mu, yoksa kayık mı? (Pencere modu ve tam ekran, ikisinde de bak.)
3. Üstteki sayfa adlarına (Items / Presets / Keys / Language) ve kategori sekmelerine tıkla: geçiyor mu?
4. Soldaki listeden bir silaha tıkla, sağdan bir değerin **sayısına** tıkla: yazma kutusu (`= _`) açılıyor mu?
   Sayı yaz, Enter: değer değişti mi?
5. Arama kutusuna tıkla: arama açılıyor mu?
6. Presets / Language sayfasında bir satıra tıkla (seçer), aynı satıra tekrar tıkla (onaylar).
7. Menü kapalıyken fare ve nişan normal mi? Menüyü açıp kapattıktan sonra da normal mi?

## Z. Zırhlar ve pasifler (yeni — en riskli kısım)

Önce `%LOCALAPPDATA%\BYOG\STATUS.txt` dosyasına bak: bir zırh değeri ayarladıktan sonra en üst satır
`OK - N values applied` mi, yoksa `HelldiverCustomizationKit` / `...PassiveBonusSettings` tablosu
bulunamadı mı diyor? Bulunamadıysa bu bölüm çalışmaz; STATUS.txt'yi gönder, yeter.

1. **Armor** sekmesi: 136 satır, en üstte `* Helldiver: movement, stamina`, sonra zırhlar oyundaki adlarıyla.
   Adı `armor_xxxxxxxx` olan sekiz zırh var: hangileri olduğunu biliyorsan yaz.
2. `* Helldiver` → **Sprinting speed** = 9. Gemide / görevde koş: belirgin hızlı mı? Delete ile geri al.
3. `* Helldiver` → **Seconds of sprinting on full stamina** = 200: stamina çok yavaş mı bitiyor?
4. Giydiğin ağır bir zırh → **Weight class** = 0 (light). Zırh seçme ekranında değerler hafif zırhınki
   (50 / 550 / 125) gibi mi görünüyor? Görevde hafif gibi mi koşuyor? Görünmüyorsa zırhı çıkarıp tekrar giy.
5. Giydiğin zırh → **Passive** = 7 (Med-Kit; numaralar Passives sekmesinde adların yanında). Zırh ekranında
   pasif değişti mi, görevde 6 stim mi var? **Oyun çökerse hangi sayıyla çöktüğünü yaz.**
6. **Passives** sekmesi → Med-Kit → **Extra stims** = 6. Med-Kit'li bir zırhla göreve in: 8 stim mi?
7. Passives → Fortified → **Explosive damage taken** = 0. Kendi bombanla öl(me)meyi dene.
8. Passives → Engineering Kit → **Extra grenades** = 6.
9. Adı `effect_xxxxxxxx` olan satırlar ne yaptığını bilmediğimiz etkiler; oyundaki açıklamadan
   tanıyorsan yaz.
10. Her şeyi Delete ile geri al, görevden çık-gir: değerler oyununkine döndü mü?

## X. Paketler, taretler, eklentiler, şarapnel (yeni)

1. Backpacks → **LIFT-850 Jump Pack** → **Recharge (s)** = 2, **Launch force** = 80. Paketi YENİDEN çağır
   (değerleri çağrılırken okuyor olmalı): 2 saniyede doluyor mu, daha yükseğe mi atıyor?
2. Backpacks → **LIFT-860 Hover Pack** → **Hovering (s)** = 30.
3. Backpacks → **LIFT-182 Warp Pack** → **Warp distance (m)** = 40, **Heat per warp** = 0.
4. Strat. guns → **A/G-16 Gatling Sentry** → TURRET → **Turn speed, sideways** = 360,
   **Looks for a target every (s)** ikisi de 0.05: taret çok hızlı dönüp hedef buluyor mu?
5. **Attach.** sekmesi: 166 satır (nişangâhlar, namlu ağızları, kabzalar, mühimmat türleri).
   **Vertical Grip** → **Recoil upward, times** = 0. Vertical Grip takılı bir silahla (Liberator) ateş et:
   dikey geri tepme kalktı mı? Silahı yeniden al / göreve yeniden gir, sonra bak.
6. Throwables → **G-6 Frag** → EXPLOSION → **Shrapnel: Damage** = 2000 ve **Shrapnel speed** = 200: parçalar
   uzaktaki düşmanı öldürüyor mu? (Bu parçayı anti-tank bombası, Phoenix ve luring mine da kullanıyor.)
7. Strat. guns → **MS-11 Solo Silo (the missile)** → patlama hasarını değiştir: füze farklı vuruyor mu?
8. Stratagems → **eagle_rearm** → **Cooldown** = 10: Eagle 10 saniyede yeniden silahlanıyor mu?
9. **Fuse (patlayan mermiler):** Strat. guns → **Eagle 500kg Bomb** (`eagle_500kg_bomb`) → PROJECTILE →
   **Fuse time after the hit (s)** = 5: bomba yere düştükten 5 saniye sonra mı patlıyor?
   Weapons → **GL-21 Grenade Launcher** → aynı değer = 3: bombalar çarptıktan 3 sn sonra mı patlıyor?
   **Explodes this near a target (m)** = 5: düşmana değmeden yakınında patlıyor mu?
10. Bombalarda eski **Fuse time (s)** değeri duruyor (G-12 HE → 0.5 yap).

## A0. Açılır başlıklar, reload, parçalar (en son eklenenler)

1. **Açılır başlıklar:** bir silahta sağdaki her başlık `[-] DAMAGE` gibi mi görünüyor? Bir değerin üstündeyken
   **Esc**: o başlık kapanıp `[+] DAMAGE` oluyor mu? Kapalı başlıkta **Enter** ya da **Sağ ok** açıyor mu?
   Fareyle başlığa tıklamak açıp kapatıyor mu?
2. **Gruplar kapalı açılıyor:** Enemies → **Trooper**: 17 bölüm `[+]` ile kapalı mı? Birini aç, değerini değiştir.
   Stratagems sekmesi artık 17 satır mı (Eagle, Orbital, Sentrys...)? **Eagle** → `500kg bomb` bölümünü aç → Cooldown.
3. **Reload:** AR-23 Liberator → AMMO → **Reload time** artık 0 değil 3 mü gösteriyor? 1 yap: yeniden doldurma
   belirgin hızlandı mı? (Silahı yeniden al / göreve yeniden gir.) Aynı şarjörü kullanan diğer Liberator'lar da
   değişir; STATUS.txt "also affects" satırında yazar. Reload'u 0 gösteren bir silahta (ör. PLAS-1 Scorcher)
   0.5 yaz: hızlanıyor mu, yavaşlıyor mu?
4. **Parça adları:** bir düşmanın ya da aracın parçaları artık `PART: head`, `PART: left_arm`, `PART: front_left_wheel`
   gibi adlarla mı? Hâlâ `PART: 8a4d2905` gibi görünenler adını bulamadıklarımız.
5. **Helldiver'ın kendi gövdesi:** Armor → **\* Helldiver** → `BODY` bölümü → **Health** = 500: çok daha dayanıklı mısın?
   (Oyunun değeri 125.) Parçalar: `PART: head`, `PART: chest`...
6. **Yeni adlar:** Vehicles sekmesinde TD-220 Bastion MK XVI, TD-110 Maelstrom, EXO-49 Emancipator, EXO-55 Breakthrough,
   EXO-51 Lumberer, M-103 Supply FRV, M-104 Incinerator FRV, SEAF troops var mı? Backpacks: AX/AR-23 Guard Dog,
   AX/LAS-5 Rover, AX/ARC-3 K-9, AX/TX-13 Dog Breath, B-100 Portable Hellbomb.

## G. Tek satırda toplanan öğeler (yeni)

Aynı şeyin parçaları artık solda tek satır; sağda bölümlere ayrılıyor. Değerler yine ayrı ayrı.

1. Enemies sekmesinde **Voteless** tek satır mı? Sağda `BODY: HEAVY - ...`, `BODY: LIGHT - ...`, `BODY: MEDIUM - ...`
   ve `SWIPE AND CLAW (MELEE) - ...` bölümleri var mı? Üstte "4 items, one section each" yazıyor mu?
2. **Hunter**, **Trooper**, **Heavy Devastator**, **Annihilator Tank** da tek satır mı (gövdeleri, silahları, vuruşları içinde)?
3. Bir değerin üstündeyken alt satırda `[cha_corrupted_v3] health` gibi, o değerin kimin olduğu yazıyor mu?
4. Voteless → BODY: HEAVY → **Health** = 7 yap. Sadece ağır Voteless mi değişti (hafif ve orta aynı mı)?
5. Armor sekmesi: **B-01 Tactical** tek satır mı (içinde aynı adlı 9 zırh kaydı)? Bölümlerin çok uzun olması
   kullanmayı zorlaştırıyor mu (Trooper'da 17 bölüm var)? Görüşünü yaz.
6. Aramaya `corrupted` ya da `tier 2` yaz: grubun içindeki öğeler de aramada bulunuyor mu?

## Y. Yeni silah değerleri (yeni)

1. **Railgun** veya **Quasar Cannon** → CHARGE başlığı: *charge time* değerlerini 0.2 yap: anında mı ateşliyor?
2. Wind-up'lı bir silah (HMG emplacement / Gatling sentry silahı) → **windup_seconds** = 0.
3. **LAS-98 Laser Cannon** → **beam_range** = 20: ışın 20 m'de kesiliyor mu?
4. **ARC-3 Arc Thrower** → **arc_chain_length** = 10.
5. Strat. guns → **A/MG-43 Machine Gun Sentry** → BODY → **Health** = 10: taret tek kurşunla ölüyor mu?
6. Enemies sekmesi: adlar wiki'deki adlar mı (`Heavy Devastator: Fusion Repeater`, `Bile Titan (unit)`,
   `Gazer`...)? Tanıyamadıklarımız `Automaton: ...` / `Illuminate: ...` diye duruyor; yanlış ad görürsen yaz.
   `Annihilator Tank: Fusion Battle Cannon` → **Health** = 10: tank tareti hemen patlıyor mu?
   `Bile Titan (unit)` → **Health** = 100: Bile Titan çabuk ölüyor mu?
   Artık her düşman listede (168 satır): `Hunter (unit)`, `Charger (unit)`, `Hulk (unit)`, `Voteless (unit, light)`...
   `Charger (unit)` → **Health** = 50: Charger tek atışta ölüyor mu? `Hunter (unit, tier 2)` → **Health** = 2000: ölmüyor mu?
   Hangi "tier" hangi zorlukta çıkıyor bilmiyoruz; bir değer etki etmezse aynı düşmanın diğer satırlarını dene.
   **Yakın dövüş:** Enemies → `Hunter: Serrated Slash (melee)` → **Damage** = 1: Hunter pençesi neredeyse hiç can
   götürmüyor mu? `Charger: Heavy Ram (melee)` → **Damage** = 1. `Voteless: Swipe and Claw (melee)` → **Damage** = 500:
   tek vuruşta öldürüyor mu? Adı olmayan vuruşlar Unknown sekmesinde `Damage row 571: 30 / 30, AP 7` biçiminde.
   **ÖNEMLİ — düşman hasarı denerken:** solo ya da lobinin SAHİBİ olarak dene. Düşmanları host hesaplıyor olabilir;
   misafirken etki etmediyse bunu ayrıca yaz. Her denemede `STATUS.txt` içindeki ilgili satırı da gönder
   (`APPLIED` mi, başka bir şey mi yazıyor).
   `Trooper: HE Grenade` → **Fuse time (s)** = 0.5: bot bombası hemen mi patlıyor?
7. Status → **Fire** → hasar değerini 0 yap: yanarken can gidiyor mu?
8. Strat. guns → **A/FLAM-40 Flame Sentry**, **AX/FLAM-75 "Guard Dog" Hot Dog**; Throwables → **B/MD C4 Pack
   (the charge)**; Weapons → **LAS-22 Shear**: listede var mı, bir değerini değiştir, etkisi var mı?

## 0. Silah adları

Silahlar sayfasındaki adlar tablodan işlendi. Menüde silah adları doğru mu? Aynı adı taşıyan çiftler
iç adlarıyla birlikte görünür: `SG-8 Punisher (pump_shotgun)`, `SMG-37 Defender (smg_defender)`,
`PLAS-45 Epoch (plasma_rifle)`. Hangisi hangisi, tabloya yazarsan düzeltirim.
Çıkarılan tek şey ikinci Punisher (`pump_shotgun_flm`). `smg_defender` = MP-98 Knight, `plasma_rifle` = PLAS-1 Scorcher, `marksman_rifle_justice` = R-72 Censor, `grenade_launcher_tactical` = GL-52 De-Escalator, `laser_rifle_charge` = LAS-22 Shear oldu.

## 00. Mermisi tek tek doldurulan silahlar (bu sürümün asıl düzeltmesi)

Senator, Veto, Autocannon, Grenade Pistol, Deadeye, Sweeper gibi silahlar mermiyi silah kaydından değil
"rounds" kaydından alıyor; mod orayı değiştirmiyordu, o yüzden "uygulandı" yazıp etkisiz kalıyordu.

1. **P-4 Senator** → Damage = 1000. Bir düşmana ateş et: tek atışta ölüyor mu?
2. **P-69 Veto** → Damage = 1000. Aynı deneme.
3. **AC-8 Autocannon** → Damage = 5 (çok düşük). Neredeyse hasarsız mı?
4. Değerleri Delete ile geri al, yeni silah çağır: eski haline döndü mü?
5. `revolver_pistol_long` artık farklı değerler gösteriyor (340 hasar). Oyunda hangi silah bu?

## 01. Reload süresi (yeni, oyunda hiç denenmedi)

Silahlarda AMMO başlığı altında "Reload time (s, 0 = as animated)" var. 0, oyunun animasyon süresini
olduğu gibi kullandığı anlamına geliyor.

1. **GR-8 Recoilless Rifle** (oyundaki değer 6) → 1. Yeniden doldurma belirgin şekilde hızlandı mı?
2. **P-4 Senator** (2.8) → 8. Yavaşladı mı?
3. **AR-23 Liberator** (oyundaki değer 0) → 0.5. Hızlandı mı? Animasyon garip görünüyor mu?
4. Değeri Delete ile geri al: eski hız geri geldi mi (yeni silah çağırmak gerekebilir)?

## 02. Yeni kategoriler (oyunda hiç denenmedi)

1. Üstte on kategori sığıyor mu (… Vehicles, Enemies, Unknown, Status)? Yazılar üst üste biniyor mu?
2. **Strat. weapons** → "Anti-Tank Emplacement (gun)" → Damage = 1 ya da 20000: fark ediliyor mu?
   Aynısı "Exosuit flak cannon", "Storm tank: main gun", "Eagle gun pods" için.
3. **Enemies** → `soldier_machinegun` ya da `conscript_smg` → Damage = 1: o düşmanın atışı neredeyse hasarsız mı?
   Damage = 5000: tek atışta öldürüyor mu? (Hangi düşmanın hangi silahı taşıdığını bilmiyoruz; gözlemini yaz.)
4. **Unknown** → 92 silah `weapon_xxxxxxxx` adıyla. Değerlerinden (hasar, atış hızı, şarjör) tanıdıkların var mı?
   Örneğin R-27 Censor, namlu altı bombaatar, Solo Silo füzesi, diğer exosuit silahları buradadır.
   Tanıdığını Google tablosuna yaz.

## 03. "Explodes like" menüde

Bir silahın değer listesinde EXPLOSION başlığı altında "Explodes like" satırı var.
1. **JAR-5 Dominator** → "Explodes like" satırında sağ ok ile bir patlayıcı seç (örneğin G-12 High Explosive).
   Mermi isabet ettiğinde patlıyor mu?
2. Sol ok ile "its own" değerine dön: patlama gitti mi?
3. Bu satırda Enter'a basınca sayı kutusu **açılmamalı**.

## 04. Tuşlar

Onay artık **Enter**, vazgeçme **Esc**; Insert ve End de çalışmaya devam ediyor.
1. Enter ve Esc menüde çalışıyor mu? Menü açıkken Enter oyunun sohbetini, Esc oyunun menüsünü açıyor mu? (Açmamalı.)

## A. Menü ve eski ayarlar

1. F9 menüyü açıyor mu, başlıkta `v2.0.0` yazıyor mu? Üstte dört sayfa, sağ üstte `Preset: Default` var mı?
2. 1.0'da yaptığın değişiklikler duruyor mu (değerler sarı)? `presets\Default.txt` oluşmuş mu?
3. Stat adları okunur mu ("Armor penetration, direct hit", "Magazine size")? Listenin altında seçili
   değerin config.txt adı (`ap_direct`) yazıyor mu?
4. Bir değere gel, **Enter**'e bas, sayı yaz, **Enter**: değer yazdığın sayı oldu mu? Aralık dışı bir
   sayı (örn. rpm için 99999) sınıra çekiliyor mu? **End** ile vazgeçince değer aynı kalıyor mu?
5. Status değerlerinde numaranın yanında ad çıkıyor mu (`5  Fire`)?

## B. Yazı yazma

1. Items sayfasında hiçbir tuşa basmadan bir harfe bas: arama **başlamamalı**.
2. Arama kutusu artık listenin **üstünde**. Öğe listesindeyken **Enter** (ya da F3) kutuya giriyor mu?
   `sentry` yaz: liste süzülüyor mu? Kutudayken ok tuşları ve Tab menüde bir şeyi oynatmamalı.
   Backspace harf siliyor mu? Enter kutudan çıkıp sonuçları koruyor, Esc aramayı temizliyor mu?

## C. Presetler

1. F7 ile Presets sayfası. "+ New preset (empty)" → Enter → `fun` yaz → Enter. Sağ üstte `Preset: fun`
   oldu mu, Default'taki bütün değişiklikler oyunda geri alındı mı?
2. `fun` içinde bir iki değer değiştir. Presets sayfasında Default satırında `[Activate]` → Enter:
   Default'un değerleri geri geldi mi, `fun`'ınkiler gitti mi?
3. Sol/sağ ile `Rename`, `Duplicate`, `Delete` dene. Delete önce soruyor mu?
4. Oyunu kapat-aç: son etkin preset ve değerleri duruyor mu?
5. `presets` klasörüne bir preset dosyasını başka adla kopyala: listede çıkıyor mu?

## D. Tuş atama

1. Keys sayfasında bir eyleme gel, Enter, yeni bir tuşa bas: atandı mı, alt satırdaki ipuçları değişti mi?
2. İki eyleme aynı tuşu ver: uyarı çıkıyor mu?
3. "Reset the keys" varsayılanlara döndürüyor mu? Oyunu kapat-aç: atadığın tuşlar duruyor mu?

## E. Tuş engelleme ve donma (en önemli kontrol)

Odağı değiştiren bütün yöntemler ya tuş kaçırdı ya oyunu dondurdu. Bu sürüm odağa dokunmuyor: oyunun
pencere iş parçacığına küçük bir mesaj süzgeci koyuyor ve menü açıkken tuş mesajlarını orada düşürüyor.

**Tuşlar engelleniyor mu?**
1. Menü açıkken W/A/S/D, Esc, Enter, Tab, M: oyunda bir şey oluyor mu? Ses çıkıyor mu?
2. Arama kutusuna yaz, Backspace'e bas: oyunun menüsü açılıyor mu?
3. Bir tuşu (örneğin W) basılı tutarken F9 ile menüyü aç, sonra bırak: karakter yürümeye devam ediyor mu? (Etmemeli.)

**Oyun normal mi?**
4. Menü açıkken görüntü akıyor mu, ses kesiliyor mu? Menüyü kapatınca tuşlar hemen dönüyor mu?
5. Oyunun sohbet kutusu ve kendi menüleri menü kapalıyken normal çalışıyor mu (yazı yazılabiliyor mu)?

**Donuyor mu?**
6. Menü açıkken Alt+Tab ile çık, 10 saniye bekle, dön. Beş kez tekrarla.
7. Menü açıkken oyun penceresine fareyle tıkla, menüde gezin.
8. Birkaç değeri hızlıca değiştir; bir değerin üstünde Enter ile sayı yaz.
9. Menü açıkken Alt+F4 oyunu kapatıyor mu? (Kapatmalı.)

Donarsa ya da oyun kapanırsa: **yeniden açmadan** haber ver (`watch.txt`, `byog.log`).

## F. Çince (deneme — oyun donabilir)

Oyunun dili Çince olmalı (oyun içi ayarlardan). Language sayfasında "Chinese (Simplified)" → Enter.

1. Oyun dondu ya da kapandı mı? Öyleyse oyunu kapatıp yeniden aç: mod Çinceyi kendisi kapatmış olmalı
   (Language sayfasında "Chinese is switched off..." yazar). Bunu yaz.
2. Donmadıysa: metinler Çince mi, okunuyor mu? Kutu, soru işareti ya da boşluk çıkıyor mu?
   İngilizce silah adları ve rakamlar düzgün mü? Yazılar sütunlara sığıyor mu?
3. Oyunun dili İngilizceyken "Chinese (Simplified)" seçilince ne oluyor? ("no font..." yazmalı.)

## G. Status süresi

1. Status effects kategorisi (Items sayfasında sola bas: son kategori). 71 etki var mı?
2. **Gas (6 s)** → Duration = 30. Gaz bombası at: düşmandaki gaz etkisi belirgin şekilde uzun sürüyor mu?
3. **Acid Storm** → Duration = 10; bir silaha `Status effect 1: type` = 55 ver (yorumcunun yaptığı gibi):
   etki daha uzun sürüyor mu? Zırh azaltma da uzuyor mu, yoksa yalnızca ekran efekti mi?

## Gönderilecekler

`%LOCALAPPDATA%\BYOG` içinden: `STATUS.txt`, `byog.log`, `settings.txt`, `presets` klasörü.
