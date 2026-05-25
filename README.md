# Retail Address Finder Light

Buildbar MVP med Cloudflare Pages + Pages Functions + GitHub Actions.

- `public/` = frontend
- `functions/api/start.js` = Cloudflare Function som startar GitHub Actions
- `.github/workflows/export-custom.yml` = workflow med inputs
- `scripts/export_osm.py` = export från OpenStreetMap/Overpass till CSV

CSV:n innehåller kolumnen `address_formatted`.
