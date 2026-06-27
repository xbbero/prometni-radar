#!/usr/bin/env python3
"""Prikupljanje prometnih podataka preko Google Routes API (computeRoutes).

Sprema u PostgreSQL. Jedan poziv po ruti vraća:
  - duration        : trajanje S prometom (cijela relacija)
  - staticDuration  : trajanje BEZ prometa (free-flow / povijesni prosjek)
  - legs[]          : isto, po svakoj dionici između definiranih točaka

Uporaba:
  python3 collect.py --init                # kreiraj/migriraj shemu iz schema.sql
  python3 collect.py --validate            # pozovi API i ISPIŠI razdiobu, NE spremaj
  python3 collect.py                        # prikupi i spremi

Okolinske varijable:
  DATABASE_URL           npr. postgresql://promet:promet@db:5432/promet  (OBAVEZNO)
  GOOGLE_MAPS_API_KEY    Google API ključ                                 (za stvarni rad)
  PROMET_CONFIG          putanja do config.yaml (default: config.yaml)
"""
import os
import sys
import json
import argparse
import datetime as dt
from zoneinfo import ZoneInfo
import urllib.request
import urllib.error

import yaml
import psycopg
from psycopg.types.json import Jsonb

ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"

# Field mask bira koja se polja vraćaju i određuje cijenu (traffic-aware = Advanced tier).
FIELD_MASK = ",".join([
    "routes.duration",
    "routes.staticDuration",
    "routes.distanceMeters",
    "routes.legs.duration",
    "routes.legs.staticDuration",
    "routes.legs.distanceMeters",
])

CONFIG_PATH = os.environ.get("PROMET_CONFIG", "config.yaml")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def connect():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("Greška: postavi DATABASE_URL (npr. postgresql://promet:promet@db:5432/promet)")
    return psycopg.connect(dsn)


def parse_seconds(value):
    """Routes API vraća trajanja kao npr. '1322s'. Vrati int sekundi ili None."""
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith("s"):
        s = s[:-1]
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def init_db():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    con = connect()
    with con.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    con.commit()
    con.close()
    print("Shema inicijalizirana u PostgreSQL.")


def sync_route(con, name, points):
    """Upsert rute i njezinih točaka. Vrati route_id."""
    with con.cursor() as cur:
        cur.execute(
            """INSERT INTO route(name) VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
               RETURNING route_id""",
            (name,),
        )
        route_id = cur.fetchone()[0]
        cur.execute("DELETE FROM route_point WHERE route_id = %s", (route_id,))
        cur.executemany(
            "INSERT INTO route_point(route_id, seq, label, lat, lng) VALUES (%s,%s,%s,%s,%s)",
            [(route_id, i, p["label"], p["lat"], p["lng"]) for i, p in enumerate(points)],
        )
    con.commit()
    return route_id


def build_body(points, cfg, departure_utc):
    def wp(p):
        return {"location": {"latLng": {"latitude": p["lat"], "longitude": p["lng"]}}}

    body = {
        "origin": wp(points[0]),
        "destination": wp(points[-1]),
        "travelMode": "DRIVE",
        "routingPreference": cfg["routing_preference"],
        "departureTime": departure_utc,
    }
    # trafficModel je dozvoljen samo uz TRAFFIC_AWARE_OPTIMAL
    if cfg["routing_preference"] == "TRAFFIC_AWARE_OPTIMAL":
        body["trafficModel"] = cfg["traffic_model"]
    # whole_route_only (default): NE šalji međutočke -> Google sam nađe najbržu
    # rutu (A1), bez rizika da neka točka skrene rutu na krivi kolnik. Vraća
    # jednu dionicu = cijela ruta. (false = v2: međutočke kao stajališta -> dionice)
    if not cfg.get("whole_route_only", True):
        intermediates = points[1:-1]
        if intermediates:
            body["intermediates"] = [wp(p) for p in intermediates]
    return body


def call_api(body, api_key):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Goog-Api-Key", api_key)
    req.add_header("X-Goog-FieldMask", FIELD_MASK)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        sys.stderr.write(f"HTTP {e.code} od Routes API:\n{body_txt}\n")
        raise


def parse_response(payload, points):
    """Izvuci sažetak rute i listu dionica iz odgovora."""
    routes = payload.get("routes") or []
    if not routes:
        raise RuntimeError(f"Prazan odgovor (nema 'routes'): {json.dumps(payload)[:500]}")
    r = routes[0]
    duration = parse_seconds(r.get("duration"))
    static = parse_seconds(r.get("staticDuration"))
    summary = {
        "distance_m": r.get("distanceMeters"),
        "duration_s": duration,
        "static_duration_s": static,
        "delay_s": (duration - static) if (duration is not None and static is not None) else None,
    }

    legs_in = r.get("legs") or []
    legs = []
    # Kad su međutočke 'via', API vraća jednu dionicu za cijelu rutu.
    one_leg_whole = (len(legs_in) == 1 and len(points) > 2)
    for i, leg in enumerate(legs_in):
        d = parse_seconds(leg.get("duration"))
        s = parse_seconds(leg.get("staticDuration"))
        if one_leg_whole:
            from_label = points[0]["label"]
            to_label = points[-1]["label"]
        else:
            from_label = points[i]["label"] if i < len(points) else f"p{i}"
            to_label = points[i + 1]["label"] if i + 1 < len(points) else f"p{i+1}"
        legs.append({
            "seq": i,
            "from_label": from_label,
            "to_label": to_label,
            "distance_m": leg.get("distanceMeters"),
            "duration_s": d,
            "static_duration_s": s,
            "delay_s": (d - s) if (d is not None and s is not None) else None,
        })
    return summary, legs


def store(con, route_id, cfg, requested_at, departure, payload, summary, legs, local_now):
    with con.cursor() as cur:
        cur.execute(
            """INSERT INTO measurement(
                   route_id, requested_at_utc, departure_utc, local_date, local_time,
                   weekday, hour, month, year, traffic_model, routing_preference,
                   distance_m, duration_s, static_duration_s, delay_s, raw_json)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING measurement_id""",
            (
                route_id,
                requested_at,
                departure,
                local_now.date(),
                local_now.strftime("%H:%M"),
                local_now.weekday(),  # 0=Pon ... 6=Ned
                local_now.hour,
                local_now.month,
                local_now.year,
                cfg["traffic_model"],
                cfg["routing_preference"],
                summary["distance_m"],
                summary["duration_s"],
                summary["static_duration_s"],
                summary["delay_s"],
                Jsonb(payload),
            ),
        )
        measurement_id = cur.fetchone()[0]
        cur.executemany(
            """INSERT INTO leg_measurement(
                   measurement_id, seq, from_label, to_label,
                   distance_m, duration_s, static_duration_s, delay_s)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(measurement_id, l["seq"], l["from_label"], l["to_label"],
              l["distance_m"], l["duration_s"], l["static_duration_s"], l["delay_s"]) for l in legs],
        )
    con.commit()
    return measurement_id


def fmt_min(seconds):
    if seconds is None:
        return "n/a"
    return f"{seconds/60:.1f} min"


def run(validate=False):
    cfg = load_config()
    tz = ZoneInfo(cfg.get("timezone", "Europe/Zagreb"))
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        sys.exit("Greška: postavi GOOGLE_MAPS_API_KEY u okolinu.")

    requested_at = dt.datetime.now(dt.timezone.utc)
    departure = requested_at + dt.timedelta(seconds=60)  # departureTime ne smije biti u prošlosti
    departure_str = departure.strftime("%Y-%m-%dT%H:%M:%SZ")
    local_now = requested_at.astimezone(tz)

    con = None if validate else connect()
    active = [r for r in cfg["routes"] if r.get("active")]
    if not active:
        print("Nema aktivnih ruta u config.yaml (active: true).")
        return

    for route in active:
        points = route["points"]
        body = build_body(points, cfg, departure_str)
        payload = call_api(body, api_key)
        summary, legs = parse_response(payload, points)

        print(f"\n=== {route['name']}  @ {local_now.strftime('%Y-%m-%d %H:%M %Z')} ===")
        print(f"  Ukupno:  s prometom {fmt_min(summary['duration_s'])} | "
              f"bez prometa {fmt_min(summary['static_duration_s'])} | "
              f"kašnjenje {fmt_min(summary['delay_s'])} | "
              f"{(summary['distance_m'] or 0)/1000:.1f} km")
        for l in legs:
            print(f"    {l['from_label']:>9} -> {l['to_label']:<9} "
                  f"s {fmt_min(l['duration_s'])} | bez {fmt_min(l['static_duration_s'])} | "
                  f"+{fmt_min(l['delay_s'])} | {(l['distance_m'] or 0)/1000:.1f} km")

        if not validate:
            route_id = sync_route(con, route["name"], points)
            mid = store(con, route_id, cfg, requested_at, departure,
                        payload, summary, legs, local_now)
            print(f"  -> spremljeno (measurement_id={mid})")

    if con:
        con.close()


def main():
    ap = argparse.ArgumentParser(description="Prikupljanje prometnih podataka (Google Routes API).")
    ap.add_argument("--init", action="store_true", help="Kreiraj/migriraj shemu iz schema.sql.")
    ap.add_argument("--validate", action="store_true",
                    help="Pozovi API i ispiši razdiobu po dionicama, ali NE spremaj u bazu.")
    args = ap.parse_args()

    if args.init:
        init_db()
        return
    run(validate=args.validate)


if __name__ == "__main__":
    main()
