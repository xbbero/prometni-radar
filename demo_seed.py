#!/usr/bin/env python3
"""Generira LAŽNE prometne podatke za 16 nedjelja kako bi se odmah mogla
isprobati analiza (analyze.py) prije nego skupiš prave podatke.

Uporaba (unutar Dockera):
  docker compose run --rm collector python collect.py --init
  docker compose run --rm collector python demo_seed.py
  docker compose run --rm collector python analyze.py --route 1 --charts

Brisanje demo podataka: docker compose run --rm collector python demo_seed.py --clear
"""
import sys
import random
import datetime as dt
from zoneinfo import ZoneInfo

import collect

random.seed(7)


def clear(con):
    with con.cursor() as cur:
        cur.execute("DELETE FROM leg_measurement")
        cur.execute("DELETE FROM measurement")
        cur.execute("DELETE FROM holiday")
    con.commit()
    print("Demo podaci obrisani (rute ostaju).")


def seed(con):
    cfg = collect.load_config()
    tz = ZoneInfo(cfg["timezone"])
    route = cfg["routes"][0]
    points = route["points"]
    route_id = collect.sync_route(con, route["name"], points)

    base = [1500, 1400, 2600, 2900, 900, 1300, 600]  # free-flow po dionici (s)
    start = dt.date(2026, 6, 7)
    for w in range(16):
        d = start + dt.timedelta(days=7 * w)
        season = 1.0 + (0.25 if d.month in (7, 8) else 0.0)
        for hour in range(7, 22):
            rush = 1.0 + 0.5 * max(0, 1 - abs(hour - 17) / 4.0)
            legs, total_d, total_s, total_dist = [], 0, 0, 0
            for i, static in enumerate(base):
                seg_factor = 1.0 + (0.4 if i in (3, 5) else 0.1) * (rush - 1) * season
                duration = int(static * seg_factor + random.randint(-30, 40))
                dist = static * 28
                legs.append({"seq": i, "from_label": points[i]["label"],
                             "to_label": points[i + 1]["label"], "distance_m": dist,
                             "duration_s": duration, "static_duration_s": static,
                             "delay_s": duration - static})
                total_d += duration; total_s += static; total_dist += dist
            summary = {"distance_m": total_dist, "duration_s": total_d,
                       "static_duration_s": total_s, "delay_s": total_d - total_s}
            local_now = dt.datetime(d.year, d.month, d.day, hour, 0, tzinfo=tz)
            req_utc = local_now.astimezone(dt.timezone.utc)
            collect.store(con, route_id, cfg, req_utc, req_utc,
                          {"_mock": True}, summary, legs, local_now)

    with con.cursor() as cur:
        cur.executemany(
            """INSERT INTO holiday(holiday_date, name, is_long_weekend) VALUES (%s,%s,%s)
               ON CONFLICT (holiday_date) DO NOTHING""",
            [(dt.date(2026, 8, 15), "Velika Gospa", 1),
             (dt.date(2026, 6, 22), "Dan antifašističke borbe", 1)],
        )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM measurement").fetchone()[0]
    nl = con.execute("SELECT COUNT(*) FROM leg_measurement").fetchone()[0]
    print(f"Ubačeno: {n} mjerenja, {nl} redaka dionica")


def main():
    con = collect.connect()
    if "--clear" in sys.argv:
        clear(con)
    else:
        seed(con)
    con.close()


if __name__ == "__main__":
    main()
