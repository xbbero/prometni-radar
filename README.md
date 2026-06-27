# Traffic Pattern Analyzer · Analizator prometnih obrazaca

A self-hosted system that builds a **historical traffic knowledge base** for road
routes using the Google Routes API — so you can answer questions about *patterns*,
not just the current moment.

Samostalno hostan sustav koji gradi **povijesnu bazu prometnog znanja** za cestovne
relacije pomoću Google Routes API-ja — da odgovara na pitanja o *obrascima*, ne samo
o trenutnom stanju.

**[ English ](#english)** · **[ Hrvatski ](#hrvatski)**

---

<a name="english"></a>
## English

### The idea

Google Maps shows you traffic *right now*. It can't tell you whether leaving at 10:00
instead of 17:00 on a summer Sunday saves you 25 minutes on average, which highway
stretch reliably jams, or how much worse a long holiday weekend is than a normal one.

This system periodically samples a route's travel time (with and without traffic),
stores every measurement in PostgreSQL, and turns months of history into reports,
charts and departure-time recommendations.

First use case: the **A1 motorway, Šibenik ⇄ Zagreb**, both directions, every 30
minutes — broken down into named segments (Šibenik–Zadar, Zadar–Sveti Rok,
Bosiljevo–Karlovac, Karlovac–Lučko, …).

### Questions it answers

- When is traffic lightest / heaviest on a given day?
- How much does traffic extend the trip on average (and at the 90th percentile)?
- How do patterns differ by month and tourist season?
- Which motorway segments reliably become bottlenecks, and when?
- Which holidays and long weekends are the most congested?
- Is the direction asymmetric (e.g. jam toward Zagreb while the other way is clear)?

### How it works

The key efficiency: a single `computeRoutes` call with `routingPreference:
TRAFFIC_AWARE` returns both `duration` (with traffic) and `staticDuration`
(free-flow) — at the whole-route level **and** per leg. By defining intermediate
waypoints, one call yields the full route plus every segment's traffic delay. The
difference `duration − staticDuration` is the time lost to traffic.

```
config.yaml ──► collect.py ──► PostgreSQL ──► analyze.py ──► reports + charts
  (routes,       (1 API call/route,  (measurement +
   waypoints)     parses legs)        leg_measurement)
       ▲
  supercronic schedule (every 30 min)
```

Everything runs in Docker: one PostgreSQL container and one collector container
(Python + [supercronic](https://github.com/aptible/supercronic) for container-native
scheduling). Designed to run on a free-tier cloud VM.

### Tech stack

Python · PostgreSQL · Docker / Docker Compose · Google Routes API · matplotlib

### Quick start

```bash
cp .env.example .env          # set DB password and Google API key
docker compose up -d --build  # starts Postgres + collector, creates the schema
```

Try the analysis immediately on **fake** data (no API key needed):

```bash
docker compose exec collector python demo_seed.py
docker compose exec collector python analyze.py --route 1 --charts
docker compose exec collector python demo_seed.py --clear   # remove demo data
```

Validate a route against the live API before scheduling (calls Google, stores nothing):

```bash
docker compose exec collector python collect.py --validate
```

### Viewing results

Results are a **terminal report** plus **PNG charts** in `reports/`:

```bash
docker compose exec collector python analyze.py --route 1 --charts
docker compose exec collector python analyze.py --route 1 --weekday -1   # all days
```

Because all data lives in PostgreSQL, you can also point any BI tool (Metabase,
Grafana, …) at it for dashboards — e.g. an hour × month congestion heatmap.

### Cost

Traffic-aware calls fall under the Routes API **Pro** tier (5,000 free events/month).
Both directions, every 30 min, 06–22h ≈ **~2,100 calls/month — within the free tier**.
A daily quota cap in the Google Cloud Console is recommended as a safety net.

### Project structure

| File | Role |
|------|------|
| `config.yaml` | Routes and waypoints (edit here) |
| `schema.sql` | PostgreSQL schema |
| `collect.py` | Collector (Routes API → Postgres) |
| `analyze.py` | Analysis: reports + charts |
| `demo_seed.py` | Fake data for trying the pipeline |
| `docker-compose.yml` / `Dockerfile` / `entrypoint.sh` / `crontab` | Containerisation + schedule |

### Roadmap

- `speedReadingIntervals` layer (per-polyline congestion: NORMAL / SLOW / JAM)
- Arbitrary routes, days and time windows (the schema already supports this)
- Automated `pg_dump` backups to object storage
- Pre-built BI dashboards

### License

MIT — see [LICENSE](LICENSE).

> Note: the waypoint coordinates in `config.yaml` are approximate and should be
> verified to sit exactly on the motorway (see comments in that file).

---

<a name="hrvatski"></a>
## Hrvatski

### Ideja

Google Maps pokazuje promet *upravo sada*. Ne može ti reći štedi li polazak u 10:00
umjesto u 17:00 ljetne nedjelje prosječno 25 minuta, koja dionica autoceste redovito
zapne, ni koliko je produženi blagdanski vikend gori od običnog.

Ovaj sustav u pravilnim razmacima mjeri trajanje putovanja (s prometom i bez njega),
sprema svako mjerenje u PostgreSQL, te od višemjesečne povijesti radi izvještaje,
grafove i preporuke za optimalno vrijeme polaska.

Prvi slučaj korištenja: **autocesta A1, Šibenik ⇄ Zagreb**, oba smjera, svakih 30
minuta — razloženo na imenovane dionice (Šibenik–Zadar, Zadar–Sveti Rok,
Bosiljevo–Karlovac, Karlovac–Lučko, …).

### Na koja pitanja odgovara

- Kada je promet najmanji / najveći određenog dana?
- Koliko promet prosječno (i u 90. percentilu) produžuje putovanje?
- Kako se obrasci razlikuju po mjesecima i turističkoj sezoni?
- Koje dionice autoceste redovito postaju usko grlo, i kada?
- Koji su blagdani i produženi vikendi prometno najopterećeniji?
- Je li promet asimetričan po smjeru (npr. kolona prema Zagrebu, a obrnuto čisto)?

### Kako radi

Ključ učinkovitosti: jedan `computeRoutes` poziv s `routingPreference: TRAFFIC_AWARE`
vraća i `duration` (s prometom) i `staticDuration` (bez prometa) — na razini cijele
rute **i** po svakoj dionici. Definiranjem međutočaka jedan poziv daje cijelu rutu
plus kašnjenje svake dionice. Razlika `duration − staticDuration` je vrijeme
izgubljeno u prometu.

```
config.yaml ──► collect.py ──► PostgreSQL ──► analyze.py ──► izvještaji + grafovi
  (rute,         (1 API poziv/ruti,  (measurement +
   točke)         parsira legs)       leg_measurement)
       ▲
  supercronic raspored (svakih 30 min)
```

Sve radi u Dockeru: jedan PostgreSQL kontejner i jedan collector kontejner (Python +
[supercronic](https://github.com/aptible/supercronic) za raspoređivanje prilagođeno
kontejnerima). Predviđeno za pokretanje na besplatnoj cloud VM-ki.

### Tehnologije

Python · PostgreSQL · Docker / Docker Compose · Google Routes API · matplotlib

### Brzi početak

```bash
cp .env.example .env          # upiši lozinku baze i Google API ključ
docker compose up -d --build  # diže Postgres + collector, kreira shemu
```

Isprobaj analizu odmah na **lažnim** podacima (bez API ključa):

```bash
docker compose exec collector python demo_seed.py
docker compose exec collector python analyze.py --route 1 --charts
docker compose exec collector python demo_seed.py --clear   # obriši demo podatke
```

Provjeri rutu na živom API-ju prije rasporeda (poziva Google, ništa ne sprema):

```bash
docker compose exec collector python collect.py --validate
```

### Pregled rezultata

Rezultati su **tekstualni izvještaj** plus **PNG grafovi** u mapi `reports/`:

```bash
docker compose exec collector python analyze.py --route 1 --charts
docker compose exec collector python analyze.py --route 1 --weekday -1   # svi dani
```

Pošto su svi podaci u PostgreSQL-u, možeš na bazu spojiti i bilo koji BI alat
(Metabase, Grafana, …) za dashboarde — npr. heatmapu zagušenja sat × mjesec.

### Trošak

Traffic-aware pozivi spadaju u **Pro** tier Routes API-ja (5.000 besplatnih
događaja/mjesec). Oba smjera, svakih 30 min, 06–22h ≈ **~2.100 poziva/mjesec —
unutar besplatnog tiera**. Preporučuje se dnevni quota cap u Google Cloud Consoleu
kao zaštitna mreža.

### Struktura projekta

| Datoteka | Uloga |
|----------|-------|
| `config.yaml` | Rute i točke (ovdje uređuješ) |
| `schema.sql` | PostgreSQL shema |
| `collect.py` | Prikupljanje (Routes API → Postgres) |
| `analyze.py` | Analiza: izvještaji + grafovi |
| `demo_seed.py` | Lažni podaci za isprobavanje |
| `docker-compose.yml` / `Dockerfile` / `entrypoint.sh` / `crontab` | Kontejnerizacija + raspored |

### Plan razvoja

- Sloj `speedReadingIntervals` (gustoća po poliliniji: NORMAL / SLOW / JAM)
- Proizvoljne rute, dani i vremenski periodi (shema to već podržava)
- Automatski `pg_dump` backupi u object storage
- Gotovi BI dashboardi

### Licenca

MIT — vidi [LICENSE](LICENSE).

> Napomena: koordinate međutočaka u `config.yaml` su približne i treba ih provjeriti
> da leže točno na autocesti (vidi komentare u toj datoteci).
