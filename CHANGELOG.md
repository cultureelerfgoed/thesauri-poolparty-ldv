# Changelog

Nieuwste bovenaan.

## 2026-11-16: robuuste ETL

Herschreven in de opzet van de bibliotheek-, beeldbank- en kunstcollectie-ETL's.

### Gerepareerd
- **Rechtenstatus**: de projectcode miste de eerste `c` (`e0ebf95-…` in plaats van `ce0ebf95-…`). De export gaf sinds september 2026
  elke dag HTTP 500 en de dataset werd niet meer bijgewerkt, terwijl de workflow groen bleef.
- Fouten laten de run nu falen. Voorheen eindigde de workflow altijd groen.
- Serviceverzoeken naar services die niet bestaan (`referentienetwerk-jena`, `referentienetwerk-virtuoso`, `homosaurus-jena`):
  vervangen door het synchroniseren van de services die de dataset echt heeft.
- Het samengevoegde bestand werd parallel en per graph opnieuw geïmporteerd; nu één import per dataset.
- De CLI gebruikte geen expliciete `--url`; import, assets en API gebruiken nu dezelfde LDV.
- Lokale herstarts gebruikten oude exportbestanden; elke run exporteert nu opnieuw.

### Toegevoegd
- Controles vóór publicatie: geldige TriG, thesaurusgraph aanwezig, concepten, geen krimp van meer dan 10% ten opzichte van de LDV.
- Telling per graph na de import; wachten tot de services bij zijn.
- `manifest.json` met checksums, een samenvatting per run, en `etl-rapport.json` als vast asset per dataset.
- Handmatige invoer: `datasets`, `publish` en `allow_shrink`. Lokaal: `--dry-run` voor de publicatie.
- Time-outs en retries voor PoolParty; HTML-foutpagina's worden herkend.
- Tests zonder netwerk (`python -m pytest`), ook als eerste job in de workflow.
- Documentatie in `docs/`.

### Verwijderd
- `thesauri-poolparty.py` en `thesauri-poolparty.yaml` (vervangen door `src/` en `config/config.yml`).
- `tools/triplydb.exe` (40 MB, de workflow haalt de CLI zelf op) en `tools/run` (los bestand met een rijksmonument).
- De lijst `services` per dataset in de configuratie.
- `.github/workflows/keep-alive.yml`: die echode alleen iets en hield de planning niet actief. Vervangen door de job `keepalive`
  in `deploy.yml`, die de workflow via de API opnieuw aanzet.
