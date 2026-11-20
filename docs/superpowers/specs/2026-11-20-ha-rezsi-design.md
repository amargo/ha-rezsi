# ha-rezsi – tervezési specifikáció

Dátum: 2026-11-20 · Állapot: jóváhagyva

## Cél

Home Assistant egyedi integráció (HACS, GitHub), amely a felhasználó saját HA-statisztikáiból
megmutatja, mennyit fizet a rezsicsökkentett áron és mennyit fizetne piaci áron, egy
elszámolási időszakra (leolvasástól máig). A webes Rezsikalkulátor (rezsi.amargo.dev)
számítási logikáját követi.

## Hatókör

- v1: villany (vétel, betáplálás, szaldó/bruttó) és gáz.
- Később: víz (v2), távoli tarifafrissítés GitHubról („C” változat), Lovelace kártya.
- Nem cél: számla pontos reprodukálása (alapdíjak, egyéb díjak), jogi tanácsadás.

## Több mérőhely

- Minden mérőhely (lakás) külön config entry; a név kötelező (pl. „Velencei ház”).
- Az entitás-azonosítók a névből képződnek (`sensor.velencei_haz_villany_piaci_aron`), nincs fix előtag.
- Mérőhelyenként saját: forrásszenzorok, leolvasási nap, sávhatár-szorzó, felülírások.
- README és config flow leírás: „Minden mérőhelyhez külön példányt adj hozzá.”

## Felépítés

Repó: `amargo/ha-rezsi`, domain: `rezsi`, MIT licenc, `hacs.json`.

| Fájl (`custom_components/rezsi/`) | Feladat | HA-függő |
|---|---|---|
| `tariffs.yaml` | dátumozott tarifablokkok (`valid_from`), minden értékhez forrás | nem |
| `tariffs.py` | betöltés, adott napon érvényes blokk, felülírások összefésülése | nem |
| `calc.py` | tiszta számítás (sávos/piaci ár, szaldó, betáplálás, RHD, arányosítás, szorzó) | nem |
| `coordinator.py` | óránként LTS-lekérdezés (`statistics_during_period`, `sum`, napi), `calc` hívás | igen |
| `config_flow.py` | setup + options flow | igen |
| `sensor.py`, `button.py`, `date.py` | entitások | igen |
| `store.py` | időszak kezdete és előző lezárt időszak (`homeassistant.helpers.storage.Store`) | igen |

## Tarifák („A” változat)

`tariffs.yaml` példa-szerkezet:

```yaml
- valid_from: 2026-01-01
  source: "<rendelet / MEKH határozat száma>"
  electricity: {reduced: 36.06, above: 70.10, band_kwh: 2523, market: 130, feed_in: 15,
                rhd_base_extra: 0, rhd_kwh_extra: 0}
  gas: {reduced: 102, above: 747, band_m3: 1729, market: 500}
  vat: 27
- valid_from: 2027-01-01
  source: "MEKH H 3193/2026"
  electricity: {rhd_base_extra: 12930, rhd_kwh_extra: -2.08}   # 14376−1446 Ft/év, 21.32−23.40 Ft/kWh, nettó
```

- Egy blokk csak a változó kulcsokat tartalmazza; a betöltő az előző blokkból örököl.
- Adott napra a legutolsó `valid_from <= nap` blokk érvényes.
- Options flow-ban minden érték felülírható; üres mező = alapérték.
- Jogszabályváltozás: új blokk + forrás → teszt → release.

## Beállítás

Config flow: név (kötelező), villany vétel szenzor (kötelező, kWh, `total_increasing`),
betáplálás szenzor (opcionális), gáz szenzor (opcionális, m³), szaldó (igen/nem, alap: igen),
időszak kezdete (alap: ma − 365 nap).

Options flow: villany sávhatár-szorzó (alap 1), gáz sávhatár-szorzó (alap 1), RHD-különbség
kapcsoló (alap: ki), tarifa-felülírások (piaci ár, átvételi ár, kedvezményes/átlag feletti ár,
sávhatár).

## Entitások (mérőhelyenként)

| Entitás | Tartalom |
|---|---|
| `sensor.<hely>_villany_rezsiaron` | villanyköltség az időszakban, sávos rezsiáron (Ft) |
| `sensor.<hely>_villany_piaci_aron` | ugyanaz piaci áron |
| `sensor.<hely>_gaz_rezsiaron`, `_gaz_piaci_aron` | gáz, csak ha van gázszenzor |
| `sensor.<hely>_osszesen_rezsiaron`, `_osszesen_piaci_aron` | villany + gáz |
| `sensor.<hely>_kulonbseg` | piaci − rezsi; attribútum: százalék |
| `sensor.<hely>_eves_becsles_piaci` | időszaki piaci költség × 365 / eltelt napok |
| `button.<hely>_leolvasas_most` | lezárja és elmenti az időszakot, új kezdőnap = ma |
| `date.<hely>_idoszak_kezdete` | kézzel állítható kezdőnap |

Szenzorok: `device_class: monetary`, egység `Ft`, `state_class` nincs (időszaki érték, nullázódik).

Közös attribútumok: `idoszak_kezdete`, `eltelt_napok`, `vetel_kwh`, `betaplalas_kwh`,
`elszamolt_kwh`, `gaz_m3`, `savhatar_aranyos`, `savhatar_felhasznalt_pct`, `tarifa_valid_from`,
`tarifa_forras`, `havi_bontas`, `elozo_idoszak`, `adat_hianyos`, `elso_adat_napja`.

## Számítás

1. Napi összegek LTS-ből (`sum` különbség napról napra), az időszak kezdetétől máig.
2. Elszámolt villany: szaldónál `max(0, vétel − betáplálás)` az időszakra; jóváírás a többletre
   átvételi áron. Bruttónál elszámolt = vétel, jóváírás = betáplálás × átvételi ár.
3. Arányosított sávhatár = éves sávhatár × szorzó × eltelt napok / 365.
4. Rezsiár = `min(q, sáv) × kedvezményes + max(0, q − sáv) × átlag feletti`.
5. Piaci ár = `q × piaci`.
6. RHD-felár (ha be van kapcsolva) = (`rhd_base_extra` × napok/365 + `rhd_kwh_extra` × q) × (1 + áfa); csak a piaci összeghez adódik (a rezsiárat a Rezsitv. 2. § plafonozza).
7. Tarifaváltás az időszakon belül: a napokat az aznap érvényes blokk szerint csoportosítja; a
   sávhatárt a csoportok napszáma szerint osztja szét. Szaldó nettósítás az egész időszakra; az elszámolt kWh a blokkok között a vétel arányában, a jóváírás a betáplálás arányában oszlik meg.
8. Gáz ugyanígy, saját sávhatárral és szorzóval.

Nyitott (forrás ellenőrzése): a sávhatár időarányosítás pontos jogszabályi szabálya miniszteri
rendeletben van (Vet. 3. § 29a. pont), ez nincs még a hu-law korpuszban. Addig napi arányosítás (fix 365 nap, szökőévben is),
a specben és README-ben jelölve.

## Hibakezelés

- Nincs vételi statisztika: a setup `ConfigEntryNotReady`, a HA újrapróbálja.
- Hiányzó gázstatisztika: a gáz- és összesen-szenzorok gáz nélkül / `unavailable`, a villany számol.
- Rövidebb statisztika, mint az időszak: `adat_hianyos: true`, `elso_adat_napja`.
- Hibás `tariffs.yaml` vagy felülírás: setup hiba érthető üzenettel (a tesztek ezt kizárják release előtt).

## Tesztelés

- `calc.py`, `tariffs.py`: pytest HA nélkül; referenciaesetek a webes kalkulátor mintaadataival
  (azonos eredmény), arányosítás, 2× szorzó, szaldó/bruttó, tarifaváltás az időszak közepén,
  felülírás elsőbbsége.
- Integráció: `pytest-homeassistant-custom-component` – config/options flow, gomb (új időszak +
  mentés), restart utáni megmaradás, hiányzó szenzor.
- CI: GitHub Actions – pytest, `hassfest`, HACS action.

## Kiadás

- GitHub release semver címkével; HACS custom repository; később HACS default lista.
- Push és release csak a tulajdonos engedélyével.
