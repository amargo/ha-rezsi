# Rezsi kalkulátor – Home Assistant

Mennyit fizetsz most rezsicsökkentett (sávos) áron, és mennyit fizetnél piaci áron? Az integráció a
saját HA hosszú távú statisztikáidból (villany vétel/betáplálás, gáz) számolja ki az aktuális
elszámolási időszak költségét. A webes változat: https://rezsi.amargo.dev

## Telepítés (HACS)
1. HACS → Integrations → ⋮ → Custom repositories → `https://github.com/amargo/ha-rezsi`, kategória: Integration.
2. Telepítés, HA újraindítás.
3. Beállítások → Eszközök és szolgáltatások → Integráció hozzáadása → **Rezsi kalkulátor**.

Megadandó: hely neve, villany vételi energiaszenzor (kWh), opcionálisan betáplálási (kWh) és gáz (m³)
szenzor, szaldó be/ki, az időszak kezdete. A szenzoroknak hosszú távú statisztikával (`state_class`)
kell rendelkezniük.

**Minden mérőhelyhez külön példányt adj hozzá.** Két mérőhely = két példány, saját névvel. Az
entitás-azonosítók a névből képződnek (pl. `sensor.velencei_haz_villany_piaci_aron`).
Az entitásnevek fixen magyarok, így az azonosítók a HA nyelvétől függetlenül állandóak.

## Entitások (mérőhelyenként)
| Entitás (azonosító-végződés) | Jelentés |
|---|---|
| `villany_rezsiaron`, `gaz_rezsiaron`, `osszesen_rezsiaron` | költség az időszakban, sávos rezsiáron (Ft) |
| `villany_piaci_aron`, `gaz_piaci_aron`, `osszesen_piaci_aron` | ugyanez piaci áron (a gáz csak gázszenzor megadásakor) |
| `kulonbseg` | piaci − rezsi (attribútum: `kulonbseg_pct`) |
| `eves_becsles_piaci` | az időszaki piaci költség 365 napra vetítve |
| `button.<hely>_leolvasas_most` | lezárja az időszakot (az `elozo_idoszak` attribútumba menti), új időszak mától |
| `date.<hely>_idoszak_kezdete` | az időszak kezdete, kézzel állítható |

Hasznos attribútumok: `eltelt_napok`, `vetel_kwh`, `betaplalas_kwh`, `elszamolt_kwh`,
`savhatar_aranyos`, `savhatar_felhasznalt_pct`, `tarifa_valid_from`, `havi_bontas`,
`adat_hianyos`, `elso_adat_napja`.

## Időszak
- Alapértelmezett kezdet: ma − 364 nap (365 számolt nap a mai napot beleértve). Módosítható a
  `date.<hely>_idoszak_kezdete` entitással vagy a „Leolvasás most” gombbal. Jövőbeli dátum elutasítva.
- A leolvasás napjának fogyasztása a lezárt és az új időszakban is beleszámít (napi felbontás).
- Ha a statisztika később kezdődik, mint az időszak (`adat_hianyos: true`, `elso_adat_napja`), a
  sávhatár ettől függetlenül az időszak összes napjára arányosodik, így a rezsiáras költség alulbecsült.
- Az első tarifablokk előtti napokra az első blokk árai érvényesek.

## Beállítások (Konfigurálás)
- **Szaldó**: a vétel és betáplálás az egész időszakra nettózódik. Tarifaváltás esetén az elszámolt
  kWh a vételi arány, a jóváírás a betáplálási arány szerint oszlik meg az időszakon belül.
  Bruttónál a betáplálás átvételi áron jóváíródik.
- **Sávhatár-szorzó** (villany, gáz): ha a mérőhely két lakásnak minősül (dupla kedvezmény), állítsd 2-re.
- **RHD-felár**: a 2027-es hálózati díjváltozás (MEKH H 3193/2026) különbözete (a `tariffs.yaml`
  a 2027−2026 nettó különbséget tárolja) csak a *piaci* költséghez adódik, mert a rezsiárat a
  2013. évi LIV. tv. 2. §-a plafonozza. Ez szándékosan eltér a webes kalkulátortól, amely mindkét
  oldalhoz hozzáadja.
- **Árfelülírások**: bármely ár vagy sávhatár; üresen a beépített, adott napon érvényes tarifa megy.
  Hibás felülírás (kézzel szerkesztett tárolt adat) esetén a bejegyzés beállítási hibába kerül:
  javítsd a beállításokat, majd töltsd újra a bejegyzést.

## Tarifák frissítése
Az árak a `custom_components/rezsi/tariffs.yaml` fájlban vannak, dátumozott blokkokban
(`valid_from`), forrással. Jogszabályváltozásnál új blokk kerül a végére (csak a változó
értékekkel), a tesztek lefutnak, és új release jön. PR-t szívesen fogadunk.

## Számítás és korlátok
- A sávhatár napi arányosítással, fix 365 napos évvel számol (szökőévben is). A pontos jogszabályi
  arányosítási szabály (Vet. 3. § 29a., miniszteri rendelet) nyitott kérdés.
- Alapdíjak és egyéb számlatételek nincsenek benne. **Becslés, nem számla és nem jogi tanács.**
