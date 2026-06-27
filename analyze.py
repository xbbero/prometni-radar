#!/usr/bin/env python3
"""Analiza prikupljenih prometnih podataka (PostgreSQL).

Odgovara na pitanja iz zahtjeva:
  - u koje je vrijeme (nedjeljom) najmanji / najveći promet
  - koliko promet prosječno produžuje putovanje
  - razlike po mjesecima / sezoni
  - blagdani i produženi vikendi
  - koje su dionice redovito najopterećenije

Uporaba:
  python3 analyze.py --list                       # popis ruta u bazi
  python3 analyze.py --route 1                     # cijeli izvještaj (default: nedjelja)
  python3 analyze.py --route 1 --weekday 6         # filtriraj dan (0=Pon..6=Ned, -1=svi)
  python3 analyze.py --route 1 --charts            # + spremi PNG grafove u reports/

Okolinske varijable: DATABASE_URL (obavezno)
"""
import os
import sys
import argparse

import psycopg
from psycopg.rows import dict_row

REPORT_DIR = os.environ.get("PROMET_REPORTS", "reports")
WEEKDAYS = ["Pon", "Uto", "Sri", "Čet", "Pet", "Sub", "Ned"]
MONTHS = ["", "Sij", "Velj", "Ožu", "Tra", "Svi", "Lip",
          "Srp", "Kol", "Ruj", "Lis", "Stu", "Pro"]


def connect():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("Greška: postavi DATABASE_URL (npr. postgresql://promet:promet@db:5432/promet)")
    return psycopg.connect(dsn, row_factory=dict_row)


def mins(seconds):
    if seconds is None:
        return "  n/a"
    return f"{seconds/60:5.1f}"


def weekday_clause(weekday):
    """Vrati (sql_uvjet, params). weekday=-1 -> svi dani."""
    if weekday is not None and weekday >= 0:
        return "AND weekday = %s", [weekday]
    return "", []


def list_routes(con):
    rows = con.execute(
        """SELECT r.route_id, r.name, COUNT(m.measurement_id) AS n,
                  MIN(m.local_date) AS od, MAX(m.local_date) AS datum_do
           FROM route r LEFT JOIN measurement m ON m.route_id = r.route_id
           GROUP BY r.route_id, r.name ORDER BY r.route_id"""
    ).fetchall()
    print("\nRute u bazi:")
    for r in rows:
        raspon = f"{r['od']} .. {r['datum_do']}" if r['od'] else "(nema mjerenja)"
        print(f"  [{r['route_id']}] {r['name']}  —  {r['n']} mjerenja  {raspon}")
    print()


def report_by_hour(con, route_id, weekday):
    wc, wp = weekday_clause(weekday)
    rows = con.execute(
        f"""SELECT hour,
                   COUNT(*)                       AS n,
                   AVG(duration_s)::float8        AS avg_dur,
                   AVG(static_duration_s)::float8 AS avg_static,
                   AVG(delay_s)::float8           AS avg_delay
            FROM measurement
            WHERE route_id = %s {wc}
            GROUP BY hour ORDER BY hour""",
        [route_id, *wp],
    ).fetchall()
    print("Sat | n  | s prometom | bez prometa | kašnjenje | kašnjenje %")
    print("----+----+------------+-------------+-----------+-----------")
    for r in rows:
        pct = (100.0 * r["avg_delay"] / r["avg_static"]) if r["avg_static"] else 0
        print(f" {r['hour']:>2} | {r['n']:>2} |   {mins(r['avg_dur'])}   |   "
              f"{mins(r['avg_static'])}    |   {mins(r['avg_delay'])}   |   {pct:5.1f}%")
    if rows:
        best = min(rows, key=lambda x: x["avg_dur"])
        worst = max(rows, key=lambda x: x["avg_dur"])
        print(f"\n  → Najmanji promet: {best['hour']:>2}:00  ({mins(best['avg_dur'])} min)")
        print(f"  → Najveća gužva:   {worst['hour']:>2}:00  ({mins(worst['avg_dur'])} min, "
              f"+{mins(worst['avg_delay'])} min zbog prometa)")
    return rows


def report_overall(con, route_id, weekday):
    wc, wp = weekday_clause(weekday)
    r = con.execute(
        f"""SELECT COUNT(*) AS n,
                   AVG(duration_s)::float8        AS avg_dur,
                   AVG(static_duration_s)::float8 AS avg_static,
                   AVG(delay_s)::float8           AS avg_delay,
                   MAX(delay_s)                   AS max_delay
            FROM measurement WHERE route_id = %s {wc}""",
        [route_id, *wp],
    ).fetchone()
    if not r or not r["n"]:
        print("  (nema podataka za ovaj filter)")
        return
    pct = (100.0 * r["avg_delay"] / r["avg_static"]) if r["avg_static"] else 0
    print(f"  Mjerenja:                {r['n']}")
    print(f"  Prosj. trajanje:         {mins(r['avg_dur'])} min")
    print(f"  Prosj. bez prometa:      {mins(r['avg_static'])} min")
    print(f"  Prosj. produženje:       {mins(r['avg_delay'])} min  ({pct:.1f}% više)")
    print(f"  Najgore zabilježeno:     +{mins(r['max_delay'])} min")


def report_by_month(con, route_id, weekday):
    wc, wp = weekday_clause(weekday)
    rows = con.execute(
        f"""SELECT year, month, COUNT(*) AS n,
                   AVG(duration_s)::float8 AS avg_dur,
                   AVG(delay_s)::float8    AS avg_delay
            FROM measurement WHERE route_id = %s {wc}
            GROUP BY year, month ORDER BY year, month""",
        [route_id, *wp],
    ).fetchall()
    print("Mjesec   | n  | prosj. trajanje | prosj. kašnjenje")
    print("---------+----+-----------------+-----------------")
    for r in rows:
        print(f" {MONTHS[r['month']]} {r['year']} | {r['n']:>2} |     {mins(r['avg_dur'])}     |"
              f"      {mins(r['avg_delay'])}")
    return rows


def report_segments(con, route_id, weekday):
    wc, wp = weekday_clause(weekday)
    rows = con.execute(
        f"""SELECT l.seq, l.from_label, l.to_label,
                   COUNT(*)                  AS n,
                   AVG(l.duration_s)::float8 AS avg_dur,
                   AVG(l.delay_s)::float8    AS avg_delay,
                   AVG(l.distance_m)::float8 AS avg_dist
            FROM leg_measurement l
            JOIN measurement m ON m.measurement_id = l.measurement_id
            WHERE m.route_id = %s {wc}
            GROUP BY l.seq, l.from_label, l.to_label
            ORDER BY l.seq""",
        [route_id, *wp],
    ).fetchall()
    print("Dionica                  | prosj. kašnjenje | kašnjenje/km | prosj. trajanje")
    print("-------------------------+------------------+--------------+----------------")
    enriched = []
    for r in rows:
        km = (r["avg_dist"] or 0) / 1000.0
        per_km = (r["avg_delay"] / km) if km else 0
        enriched.append((r, per_km))
        seg = f"{r['from_label']} → {r['to_label']}"
        print(f" {seg:<23} |     {mins(r['avg_delay'])}      |   {mins(per_km)}    |"
              f"     {mins(r['avg_dur'])}")
    if enriched:
        worst = max(enriched, key=lambda x: x[0]["avg_delay"] or 0)
        print(f"\n  → Najopterećenija dionica: {worst[0]['from_label']} → {worst[0]['to_label']} "
              f"(+{mins(worst[0]['avg_delay'])} min prosječno)")
    return rows


def report_holidays(con, route_id):
    rows = con.execute(
        """SELECT h.name, h.holiday_date,
                  AVG(m.duration_s)::float8 AS avg_dur,
                  AVG(m.delay_s)::float8    AS avg_delay,
                  COUNT(*) AS n
           FROM measurement m
           JOIN holiday h ON h.holiday_date = m.local_date
           WHERE m.route_id = %s
           GROUP BY h.name, h.holiday_date ORDER BY avg_delay DESC""",
        [route_id],
    ).fetchall()
    if not rows:
        print("  (nema mjerenja na datumima iz tablice 'holiday' — popuni je da bi ovo radilo)")
        return
    print("Blagdan / datum                | n | prosj. trajanje | prosj. kašnjenje")
    print("-------------------------------+---+-----------------+-----------------")
    for r in rows:
        label = f"{r['name']} ({r['holiday_date']})"
        print(f" {label:<29} | {r['n']:>1} |     {mins(r['avg_dur'])}     |      {mins(r['avg_delay'])}")


def make_charts(con, route_id, route_name, weekday, hour_rows, seg_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(matplotlib nije instaliran — preskačem grafove)")
        return []

    os.makedirs(REPORT_DIR, exist_ok=True)
    files = []

    if hour_rows:
        hours = [r["hour"] for r in hour_rows]
        dur = [r["avg_dur"] / 60 for r in hour_rows]
        delay = [r["avg_delay"] / 60 for r in hour_rows]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.bar(hours, dur, color="#9bb8d3", label="bez prometa (osnova)")
        ax.bar(hours, delay, bottom=[d - x for d, x in zip(dur, delay)],
               color="#d9534f", label="kašnjenje zbog prometa")
        ax.set_xlabel("Sat polaska")
        ax.set_ylabel("Trajanje (min)")
        ax.set_title(f"{route_name} — prosječno trajanje po satu")
        ax.set_xticks(hours)
        ax.legend()
        fig.tight_layout()
        p = os.path.join(REPORT_DIR, f"route{route_id}_po_satu.png")
        fig.savefig(p, dpi=110)
        plt.close(fig)
        files.append(p)

    if seg_rows:
        labels = [f"{r['from_label']}→{r['to_label']}" for r in seg_rows]
        delay = [(r["avg_delay"] or 0) / 60 for r in seg_rows]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.barh(labels, delay, color="#d9534f")
        ax.invert_yaxis()
        ax.set_xlabel("Prosječno kašnjenje (min)")
        ax.set_title(f"{route_name} — kašnjenje po dionici")
        fig.tight_layout()
        p = os.path.join(REPORT_DIR, f"route{route_id}_dionice.png")
        fig.savefig(p, dpi=110)
        plt.close(fig)
        files.append(p)

    for f in files:
        print(f"  graf -> {f}")
    return files


def main():
    ap = argparse.ArgumentParser(description="Analiza prometnih podataka.")
    ap.add_argument("--list", action="store_true", help="Ispiši rute u bazi i izađi.")
    ap.add_argument("--route", type=int, help="route_id za analizu.")
    ap.add_argument("--weekday", type=int, default=6,
                    help="Dan (0=Pon..6=Ned, -1=svi). Default 6 (nedjelja).")
    ap.add_argument("--charts", action="store_true", help="Spremi PNG grafove.")
    args = ap.parse_args()

    con = connect()
    if args.list or not args.route:
        list_routes(con)
        if not args.route:
            return

    name_row = con.execute("SELECT name FROM route WHERE route_id = %s", [args.route]).fetchone()
    if not name_row:
        sys.exit(f"Ruta {args.route} ne postoji.")
    route_name = name_row["name"]
    day_label = "svi dani" if args.weekday < 0 else WEEKDAYS[args.weekday]

    print("\n" + "=" * 70)
    print(f"  IZVJEŠTAJ: {route_name}   (filter dana: {day_label})")
    print("=" * 70)

    print("\n## Sažetak\n")
    report_overall(con, args.route, args.weekday)
    print("\n## Po satu polaska\n")
    hour_rows = report_by_hour(con, args.route, args.weekday)
    print("\n## Po mjesecima / sezoni\n")
    report_by_month(con, args.route, args.weekday)
    print("\n## Po dionicama\n")
    seg_rows = report_segments(con, args.route, args.weekday)
    print("\n## Blagdani / produženi vikendi\n")
    report_holidays(con, args.route)

    if args.charts:
        print("\n## Grafovi\n")
        make_charts(con, args.route, route_name, args.weekday, hour_rows, seg_rows)

    con.close()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
