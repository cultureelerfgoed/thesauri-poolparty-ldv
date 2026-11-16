# Beheer

## Inrichting

Twee repositorysecrets (Settings → Secrets and variables → Actions). Ze bestonden al voor de vorige versie van de ETL:

| Secret | Inhoud |
|---|---|
| `POOLPARTY_AUTH` | de volledige waarde van de HTTP-header `Authorization` voor PoolParty |
| `TRIPLYDB_TOKEN` | een token met schrijfrechten op het account `thesauri` in de LDV |

## Een run starten

Actions → *Deploy Thesauri PoolParty* → *Run workflow*. De planning draait elke dag om 03:00 UTC en **publiceert direct**.

Na een wijziging in de code of de configuratie:

| Run | `datasets` | `publish` | Doel |
|---|---|---|---|
| 1 | `onderwerpen-not` | uit | kleinste thesaurus: export en controles, niets gepubliceerd |
| 2 | `all` | uit | alle exports en controles; bekijk de samenvatting |
| 3 | `all` | aan | volledige run |

## Planning actief houden

GitHub schakelt geplande workflows in een openbare repository uit na **60 dagen zonder repository-activiteit** (commits). Een
week vooraf komt er een e-mail. De job `keepalive` zet de workflow bij elke run via de API opnieuw aan
(`PUT /repos/…/actions/workflows/deploy.yml/enable`), zonder nepcommits.

Staat de planning toch uit, zet hem dan zelf weer aan: Actions → *Deploy Thesauri PoolParty* → *Enable workflow*, of:

```bash
gh workflow enable deploy.yml --repo cultureelerfgoed/thesauri-poolparty-ldv
```

## De uitkomst lezen

De **samenvatting** van de run heeft twee tabellen:

- **Export uit PoolParty**: per dataset en graph het aantal statements, het aantal in de LDV vóór de run, het verschil en het
  aantal concepten. ❌ betekent dat de dataset niet wordt gepubliceerd; de reden staat onder *Fouten*.
- **Publicatie in de LDV**: per dataset of de import is gelukt en welke services bij zijn.

Fouten en waarschuwingen verschijnen ook als annotaties bovenaan de run. Het artefact `thesauri-export` bevat de bestanden,
`manifest.json` en `export.log` (7 dagen bewaard), `thesauri-publish-log` het publicatielog.

In de LDV staat per dataset het asset `etl-rapport.json` met het resultaat van de laatste publicatie.

### Kleur van de run

| Job | Rood betekent |
|---|---|
| `test` | de tests falen; er is niets geëxporteerd of gepubliceerd |
| `export` | minstens één dataset is afgekeurd. De **andere** datasets zijn wel gepubliceerd |
| `publish` | een import, de telling achteraf of een service-sync is mislukt |

## Foutmeldingen

| Melding | Oorzaak en oplossing |
|---|---|
| `Project … mislukt: HTTP 404` | de projectcode bestaat niet in PoolParty; controleer `project_code` |
| `Project … mislukt: na 4 pogingen: HTTP 500 …` | PoolParty geeft een interne fout. Blijft het, controleer dan de projectcode (een verkeerde code geeft soms 500 in plaats van 404) en het project in PoolParty |
| `HTTP 401` of `HTML-pagina in plaats van TriG` | `POOLPARTY_AUTH` klopt niet of is verlopen |
| `de thesaurusgraph … staat niet in de export` | PoolParty exporteert onder een andere graph-URI. Pas `graph_name` aan, en ruim zo nodig de oude graph in de LDV op |
| `graph … krimpt van N naar M statements` | de export is veel kleiner dan wat gepubliceerd is. Controleer het project in PoolParty. Is de krimp terecht, start dan handmatig met `allow_shrink` aan |
| `graph … staat in de LDV maar niet in de export` | waarschuwing: een oude graph blijft staan. Verwijder hem in de LDV als hij weg mag |
| `vergelijking met de LDV niet mogelijk` | de LDV is onbereikbaar of de dataset bestaat niet |
| `graph … heeft na de import N statements, de export had er M` | de import is onvolledig; start opnieuw en kijk in de LDV |
| `Service … na 1800s nog niet klaar` | de service synchroniseert nog of hangt; kijk in de LDV bij *Services* |
| `Projectcode … is geen geldige UUID` | waarschuwing bij het laden van de configuratie; ook een test faalt hierop |

## Een project of dataset toevoegen

1. Voeg het project toe in `config/config.yml` onder de dataset (`project_code` en `graph_name`). De dataset moet al bestaan in de LDV.
2. `python -m pytest`.
3. Start de workflow handmatig met alleen die dataset en `publish` uit; controleer de samenvatting.
4. Start opnieuw met `publish` aan. Maak in de LDV zo nodig services aan; die worden vanaf dan automatisch gesynchroniseerd.

## Terugdraaien

De import vervangt alleen de graphs uit de export. De vorige versie van een graph is daarna weg; TriplyDB bewaart geen
versies. Een afgekeurde dataset wordt niet aangeraakt, dus daar blijft de vorige versie staan. Wil je een oudere versie terug,
importeer dan het `.nq.gz`-bestand uit het artefact van een eerdere run (7 dagen beschikbaar):

```bash
TRIPLYDB_TOKEN=… ./triplydb-linux import-from-file --account thesauri --url https://api.linkeddata.cultureelerfgoed.nl \
  --dataset cht --mode overwrite cht.nq.gz
```

## Lokaal draaien

Zie de [README](../README.md#snel-starten-lokaal). Uitvoer komt in `data/` (of `CACHE_PATH`). Voor een echte publicatie
heb je de TriplyDB CLI nodig ([Windows](https://static.triply.cc/cli/triplydb.exe),
[Linux](https://static.triply.cc/cli/triplydb-linux)); geef het pad mee met `--cli` of `TRIPLYDB_CLI`.
