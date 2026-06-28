# v2 — koordinate na glavnoj pruzi A1, PO SMJERU (po kolniku)

Place ID-evi naplata/čvorova ne rade kao međutočke jer su naplate na rampama
(zatvoreni sustav naplate) → ruta silazi i vraća se = obilazak. Rješenje: točka
na **glavnoj traci A1**, na **kolniku koji odgovara smjeru vožnje**. Kolnici su
fizički razdvojeni, pa svaka točka treba DVIJE koordinate (po jednu po smjeru).

Krajevi (Šibenik, Zagreb/Rotor) ostaju Place ID/adresa — terminalne točke rade čisto.

Kako vaditi: u Maps zumiraj na glavnu prugu A1 (NE naplata, NE rampe), desni klik
točno na traku traženog smjera → koordinata. DMS je ok, pretvaram u decimalne.
Provjera: nakon svake točke `--validate`, kilometraža dionice mora sjesti na realno.

| # | Točka | → Zagreb (sjeverni kolnik) | → Šibenik (južni kolnik) | Status |
|---|-------|----------------------------|--------------------------|--------|
| 1 | Zadar     | | | ⬜ |
| 2 | Sveti Rok | | | ⬜ |
| 3 | Gospić    | | | ⬜ |
| 4 | Otočac    | | | ⬜ |
| 5 | **Bosiljevo** | `45.408917, 15.270444` | `45.408111, 15.255861` | ✅ |
| 6 | **Karlovac** | `45.515972, 15.552056` | `45.513556, 15.545194` | ✅ |
| 7 | **Lučko** | `45.749972, 15.885361` | `45.748389, 15.883472` | ✅ |

## Realne duljine dionica (za provjeru pri validaciji)

Okvirno, smjer Šibenik→Zagreb (potvrdit ćemo mjerenjem):
- Šibenik→Zadar ~75 km · Zadar→Sveti Rok ~55 km · Sveti Rok→Gospić ~50 km
- Gospić→Otočac ~35 km · Otočac→Bosiljevo ~70 km · Bosiljevo→Karlovac ~37 km
- Karlovac→Lučko ~42 km · Lučko→Zagreb ~8 km   →  ukupno ~339 km

## Endpoint Place ID-evi (ostaju, za krajeve)
- Šibenik (naplata): `ChIJRTCczq8vNRMRUZiAaPFigR8`
- Zagreb (Rotor): `ChIJOwVxSqrVZUcREOmyVeVIGF0`
