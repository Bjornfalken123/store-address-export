#!/usr/bin/env python3
"""
Robust export av matbutiksadresser från OpenStreetMap via Overpass API.

Skapar:
  - butiksadresser_osm.csv
  - butiksadresser_osm_partial.csv under körning
  - overpass_failures.txt om någon del misslyckas

Kolumnen address_formatted följer formatet:
  Rue de Rivoli 75001 Paris France

Obs: Resultatet är komplett enligt OpenStreetMap vid körningstillfället, inte garanterat komplett enligt kedjornas egna interna register.
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

TARGETS: List[Tuple[str, str, str, List[str]]] = [
    ("Netherlands", "NL", "Albert Heijn", ["Albert Heijn", "AH"]),
    ("Belgium", "BE", "Carrefour", ["Carrefour", "Carrefour Market", "Carrefour Express"]),
    ("Belgium", "BE", "Delhaize", ["Delhaize", "AD Delhaize", "Proxy Delhaize", "Shop & Go Delhaize"]),
    ("Belgium", "BE", "Albert Heijn", ["Albert Heijn", "AH"]),
    ("Belgium", "BE", "Colruyt", ["Colruyt"]),
    ("Belgium", "BE", "Intermarché", ["Intermarché", "Intermarche"]),
    ("France", "FR", "Carrefour", ["Carrefour", "Carrefour Market", "Carrefour City", "Carrefour Express", "Carrefour Contact", "Carrefour Montagne", "Bon app’", "Bon app'"]),
]

COUNTRY_NAME = {"NL": "Netherlands", "BE": "Belgium", "FR": "France"}
FIELDNAMES = [
    "country", "chain", "name", "street", "housenumber", "postcode", "city",
    "address_formatted", "osm_type", "osm_id", "lat", "lon", "source"
]


def log(msg: str) -> None:
    print(msg, flush=True)


def norm_brand(value: str) -> str:
    s = (value or "").lower().replace("é", "e").replace("’", "'")
    if "albert" in s or s == "ah":
        return "Albert Heijn"
    if "carrefour" in s or "bon app" in s:
        return "Carrefour"
    if "delhaize" in s:
        return "Delhaize"
    if "colruyt" in s:
        return "Colruyt"
    if "intermarche" in s:
        return "Intermarché"
    return value


def overpass_query(country_code: str, brand: str) -> str:
    safe = brand.replace('"', '\\"')
    return f'''
[out:json][timeout:75];
area["ISO3166-1"="{country_code}"][admin_level=2]->.searchArea;
(
  nwr["shop"~"^(supermarket|convenience)$"]["brand"="{safe}"](area.searchArea);
  nwr["shop"~"^(supermarket|convenience)$"]["name"~"^{safe}$",i](area.searchArea);
);
out tags center;
'''


def fetch(query: str, attempt_label: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        for attempt in range(1, 3):
            try:
                log(f"    Trying {url} attempt {attempt}/2")
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "store-address-export-github-actions/2.0"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    text = resp.read().decode("utf-8")
                    return json.loads(text)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                log(f"    Failed: {type(exc).__name__}: {exc}")
                time.sleep(10)
    raise RuntimeError(f"{attempt_label} failed after all Overpass endpoints. Last error: {last_error}")


def format_address(tags: Dict[str, str], country_code: str) -> str:
    street = tags.get("addr:street", "").strip()
    number = tags.get("addr:housenumber", "").strip()
    postcode = tags.get("addr:postcode", "").strip()
    city = (tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village") or "").strip()
    country = COUNTRY_NAME[country_code]
    line1 = " ".join(x for x in [street, number] if x)
    return " ".join(x for x in [line1, postcode, city, country] if x)


def is_complete_address(tags: Dict[str, str]) -> bool:
    return bool(tags.get("addr:street") and tags.get("addr:postcode") and (tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")))


def write_csv(path: str | Path, rows: List[dict]) -> None:
    rows.sort(key=lambda r: (r["country"], r["chain"], r["city"], r["street"], r["housenumber"], str(r["osm_id"])))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    seen = set()
    rows: List[dict] = []
    failures: List[str] = []

    total_jobs = sum(len(variants) for _, _, _, variants in TARGETS)
    job_no = 0

    for country_name, country_code, chain, variants in TARGETS:
        for variant in variants:
            job_no += 1
            label = f"{country_name} / {chain} / {variant}"
            log(f"\n[{job_no}/{total_jobs}] Fetching {label}")
            try:
                payload = fetch(overpass_query(country_code, variant), label)
            except Exception as exc:  # noqa: BLE001
                msg = f"{label}: {type(exc).__name__}: {exc}"
                failures.append(msg)
                log(f"  SKIPPING after failure: {msg}")
                continue

            elements = payload.get("elements", [])
            added = 0
            skipped_no_address = 0
            for el in elements:
                tags = el.get("tags", {})
                if not is_complete_address(tags):
                    skipped_no_address += 1
                    continue

                raw_brand = tags.get("brand") or tags.get("name") or chain
                canonical_chain = norm_brand(raw_brand)
                wanted_chain = norm_brand(chain)
                if canonical_chain != wanted_chain:
                    continue

                address = format_address(tags, country_code)
                key = (country_code, canonical_chain, address.lower(), str(el.get("id", "")))
                if key in seen:
                    continue
                seen.add(key)

                rows.append({
                    "country": country_name,
                    "chain": canonical_chain,
                    "name": tags.get("name", ""),
                    "street": tags.get("addr:street", ""),
                    "housenumber": tags.get("addr:housenumber", ""),
                    "postcode": tags.get("addr:postcode", ""),
                    "city": tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village") or "",
                    "address_formatted": address,
                    "osm_type": el.get("type", ""),
                    "osm_id": el.get("id", ""),
                    "lat": el.get("lat") or el.get("center", {}).get("lat", ""),
                    "lon": el.get("lon") or el.get("center", {}).get("lon", ""),
                    "source": "OpenStreetMap via Overpass API",
                })
                added += 1

            write_csv("butiksadresser_osm_partial.csv", rows)
            log(f"  Found {len(elements)} OSM elements. Added {added}. Skipped without full address {skipped_no_address}. Total rows now {len(rows)}.")
            time.sleep(3)

    write_csv("butiksadresser_osm.csv", rows)

    if failures:
        Path("overpass_failures.txt").write_text("\n".join(failures), encoding="utf-8")
        log("\nCompleted with some failed chunks. See overpass_failures.txt")
    else:
        log("\nCompleted without failed chunks.")

    log(f"Done. Wrote {len(rows)} rows to butiksadresser_osm.csv")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user.")
        sys.exit(130)
