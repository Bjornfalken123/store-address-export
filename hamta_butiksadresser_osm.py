#!/usr/bin/env python3
"""
Hämtar butiksadresser för valda matkedjor i Nederländerna, Belgien och Frankrike från OpenStreetMap via Overpass API.

Output: butiksadresser_osm.csv
Kolumnen address_formatted följer formatet:
  "Rue de Rivoli 75001 Paris France"

Obs: Detta är komplett enligt OpenStreetMap-data vid körningstillfället, inte en garanti för att varje kedjas egna officiella register är komplett speglat i OSM.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Tuple

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

TARGETS: List[Tuple[str, str, List[str]]] = [
    ("Netherlands", "NL", ["Albert Heijn"]),
    ("Belgium", "BE", ["Carrefour", "Delhaize", "Albert Heijn", "Colruyt", "Intermarché", "Intermarche"]),
    ("France", "FR", ["Carrefour"]),
]

# Common brand spelling variants in OSM.
BRAND_VARIANTS: Dict[str, List[str]] = {
    "Albert Heijn": ["Albert Heijn", "AH"],
    "Carrefour": ["Carrefour", "Carrefour Market", "Carrefour City", "Carrefour Express", "Carrefour Contact"],
    "Delhaize": ["Delhaize", "AD Delhaize", "Proxy Delhaize", "Shop & Go Delhaize"],
    "Colruyt": ["Colruyt"],
    "Intermarché": ["Intermarché", "Intermarche"],
    "Intermarche": ["Intermarché", "Intermarche"],
}

COUNTRY_NAME = {"NL": "Netherlands", "BE": "Belgium", "FR": "France"}


def overpass_query(country_code: str, brands: Iterable[str]) -> str:
    parts = []
    for brand in brands:
        safe = brand.replace('"', '\\"')
        # Query by brand and by name, because OSM tagging varies by mapper.
        parts.append(f'nwr["shop"="supermarket"]["brand"="{safe}"](area.searchArea);')
        parts.append(f'nwr["shop"="supermarket"]["name"~"^{safe}$",i](area.searchArea);')
        # Some small-format stores can be tagged as convenience.
        parts.append(f'nwr["shop"="convenience"]["brand"="{safe}"](area.searchArea);')
        parts.append(f'nwr["shop"="convenience"]["name"~"^{safe}$",i](area.searchArea);')
    return f'''
[out:json][timeout:180];
area["ISO3166-1"="{country_code}"][admin_level=2]->.searchArea;
(
{chr(10).join(parts)}
);
out tags center;
'''


def fetch(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error = None
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "store-address-export/1.0"})
            with urllib.request.urlopen(req, timeout=240) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(5)
    raise RuntimeError(f"Overpass query failed: {last_error}")


def norm_brand(chain: str) -> str:
    s = chain.lower().replace("é", "e")
    if "albert" in s or s == "ah":
        return "Albert Heijn"
    if "carrefour" in s:
        return "Carrefour"
    if "delhaize" in s:
        return "Delhaize"
    if "colruyt" in s:
        return "Colruyt"
    if "intermarche" in s:
        return "Intermarché"
    return chain


def format_address(tags: Dict[str, str], country_code: str) -> str:
    street = tags.get("addr:street", "").strip()
    number = tags.get("addr:housenumber", "").strip()
    postcode = tags.get("addr:postcode", "").strip()
    city = (tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village") or "").strip()
    country = COUNTRY_NAME[country_code]
    line1 = " ".join(x for x in [street, number] if x)
    return " ".join(x for x in [line1, postcode, city, country] if x)


def main() -> None:
    seen = set()
    rows = []
    for country_name, country_code, chains in TARGETS:
        for chain in chains:
            if chain == "Intermarche":
                continue
            variants = BRAND_VARIANTS.get(chain, [chain])
            print(f"Fetching {chain} in {country_name} ...")
            payload = fetch(overpass_query(country_code, variants))
            for el in payload.get("elements", []):
                tags = el.get("tags", {})
                raw_brand = tags.get("brand") or tags.get("name") or chain
                canonical_chain = norm_brand(raw_brand)
                if canonical_chain != norm_brand(chain):
                    # Keep Carrefour formats, but exclude unrelated names accidentally matching short variants.
                    if norm_brand(chain) != "Carrefour" or "carrefour" not in raw_brand.lower():
                        continue
                address = format_address(tags, country_code)
                # Keep only entries with at least street, postcode and city so the required format is useful.
                if not (tags.get("addr:street") and tags.get("addr:postcode") and (tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"))):
                    continue
                key = (country_code, canonical_chain, address.lower())
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
            time.sleep(2)

    rows.sort(key=lambda r: (r["country"], r["chain"], r["city"], r["street"], r["housenumber"]))
    out = "butiksadresser_osm.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["country", "chain", "name", "street", "housenumber", "postcode", "city", "address_formatted", "osm_type", "osm_id", "lat", "lon", "source"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Done. Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
