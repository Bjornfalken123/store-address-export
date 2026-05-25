#!/usr/bin/env python3
import argparse, csv, re, sys, time
from pathlib import Path
import requests

ENDPOINTS = [
  'https://overpass-api.de/api/interpreter',
  'https://overpass.kumi.systems/api/interpreter',
]
COUNTRIES = {
  'norway': ('NO','Norway'), 'norge': ('NO','Norway'),
  'france': ('FR','France'), 'frankrike': ('FR','France'),
  'belgium': ('BE','Belgium'), 'belgien': ('BE','Belgium'),
  'netherlands': ('NL','Netherlands'), 'nederländerna': ('NL','Netherlands'), 'nederlanderna': ('NL','Netherlands'),
  'sweden': ('SE','Sweden'), 'sverige': ('SE','Sweden'),
  'denmark': ('DK','Denmark'), 'danmark': ('DK','Denmark'),
  'finland': ('FI','Finland'), 'germany': ('DE','Germany'), 'tyskland': ('DE','Germany'),
  'uk': ('GB','United Kingdom'), 'united kingdom': ('GB','United Kingdom')
}

def log(msg): print(msg, flush=True)
def safe_filename(s): return re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')
def esc(s): return re.escape(s.strip())

def build_query(iso, chain):
  c = esc(chain)
  return f'''[out:json][timeout:180];
area["ISO3166-1"="{iso}"][admin_level=2]->.a;
(
  nwr["shop"~"supermarket|convenience|department_store|chemist|pharmacy"]["name"~"{c}",i](area.a);
  nwr["shop"~"supermarket|convenience|department_store|chemist|pharmacy"]["brand"~"{c}",i](area.a);
  nwr["name"~"{c}",i](area.a);
  nwr["brand"~"{c}",i](area.a);
);
out tags center;'''

def fetch(query):
  last = None
  for endpoint in ENDPOINTS:
    for attempt in range(1,3):
      try:
        log(f'Trying {endpoint} attempt {attempt}/2')
        r = requests.post(endpoint, data={'data': query}, timeout=240)
        r.raise_for_status()
        return r.json()
      except Exception as e:
        last = e
        log(f'Failed: {type(e).__name__}: {e}')
        time.sleep(8*attempt)
  raise RuntimeError(last)

def tag(tags, *keys):
  for key in keys:
    if tags.get(key): return str(tags[key]).strip()
  return ''

def row_from(el, country, chain):
  t = el.get('tags') or {}
  street = tag(t,'addr:street')
  number = tag(t,'addr:housenumber')
  postcode = tag(t,'addr:postcode')
  city = tag(t,'addr:city','addr:town','addr:village','addr:municipality')
  full = tag(t,'addr:full')
  street_line = f'{street} {number}'.strip() if street else full
  if not street_line or not postcode or not city: return None
  return {
    'chain_requested': chain,
    'name': tag(t,'name'), 'brand': tag(t,'brand'),
    'street': street, 'housenumber': number, 'postcode': postcode, 'city': city, 'country': country,
    'address_formatted': f'{street_line} {postcode} {city} {country}',
    'source': 'OpenStreetMap via Overpass API',
    'osm_type': el.get('type',''), 'osm_id': el.get('id','')
  }

def main():
  p = argparse.ArgumentParser()
  p.add_argument('--country', required=True); p.add_argument('--chain', required=True); p.add_argument('--out')
  args = p.parse_args()
  key = args.country.strip().lower()
  if key not in COUNTRIES:
    log(f'Unsupported country: {args.country}. Add it in scripts/export_osm.py')
    sys.exit(2)
  iso, country = COUNTRIES[key]
  chain = args.chain.strip()
  log(f'Exporting {chain} in {country}')
  data = fetch(build_query(iso, chain))
  elements = data.get('elements', [])
  log(f'Found {len(elements)} OSM elements')
  rows, skipped = [], 0
  seen = set()
  for el in elements:
    row = row_from(el, country, chain)
    if not row:
      skipped += 1; continue
    k = (row['address_formatted'].lower(), row['name'].lower())
    if k in seen: continue
    seen.add(k); rows.append(row)
  log(f'Rows with full address: {len(rows)}. Skipped without full address: {skipped}')
  out = Path(args.out or f'exports/{safe_filename(country)}_{safe_filename(chain)}.csv')
  out.parent.mkdir(exist_ok=True, parents=True)
  fields = ['chain_requested','name','brand','street','housenumber','postcode','city','country','address_formatted','source','osm_type','osm_id']
  with out.open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
  log(f'Wrote {out}')
if __name__ == '__main__': main()
