# Configuratie

Alle instellingen staan in [`config/config.yml`](../config/config.yml). Een ander bestand kies je met `CONFIG_PATH`.

## Omgevingsvariabelen

| Variabele | Gebruikt door | Betekenis |
|---|---|---|
| `POOLPARTY_AUTH` | export | volledige waarde van de header `Authorization` |
| `TRIPLYDB_TOKEN` | export (optioneel), publicatie | token voor de LDV |
| `TRIPLYDB_CLI` | publicatie | pad naar de TriplyDB CLI (standaard `./triplydb-linux`, op Windows `triplydb.exe`) |
| `CACHE_PATH` | beide | map voor de uitvoer (standaard `data`) |
| `CONFIG_PATH` | beide | configuratiebestand (standaard `config/config.yml`) |

## `poolparty`

| Instelling | Standaard | Betekenis |
|---|---|---|
| `export_url` | | export-URL; `{project}` wordt de projectcode |
| `modules` | `concepts, void, adms` | modules in de export; elk komt in een eigen named graph |
| `timeout` | 900 | seconden per exportverzoek |
| `retries` | 4 | pogingen bij HTTP 5xx, 429 of een netwerkfout. Andere 4xx worden niet herhaald |
| `backoff` | 15 | wachttijd in seconden, maal het nummer van de poging |

## `triplydb`

| Instelling | Standaard | Betekenis |
|---|---|---|
| `url` | | API van de LDV; gebruikt voor de API én de CLI |
| `account` | | account met de datasets |
| `import_timeout` | 3600 | seconden voor één import |
| `sync_timeout` | 1800 | seconden wachten tot een service bij is |
| `poll_interval` | 15 | seconden tussen twee statuscontroles van een service |
| `report_asset` | `etl-rapport.json` | naam van het rapport-asset per dataset |

## `checks`

| Instelling | Standaard | Betekenis |
|---|---|---|
| `min_concepts` | 1 | minimaal aantal `skos:Concept` in de thesaurusgraph van een project |
| `max_shrink_percent` | 10 | een graph die meer dan dit percentage krimpt ten opzichte van de LDV, blokkeert de dataset |
| `max_import_deviation_percent` | 1 | toegestane afwijking tussen export en LDV na de import |

## `datasets`

Per dataset (de naam is de datasetnaam in de LDV) een lijst `projects`:

| Veld | Betekenis |
|---|---|
| `project_code` | PoolParty-projectcode (UUID) |
| `graph_name` | de thesaurusgraph die het project exporteert; moet in de export staan |

De configuratie wordt bij het starten gecontroleerd. Een project moet overal dezelfde `graph_name` hebben, een dataset mag een
graph maar één keer bevatten, en een projectcode die geen UUID is geeft een waarschuwing (en een falende test).

Services staan niet in de configuratie: na een import worden **alle** services van de dataset gesynchroniseerd.
