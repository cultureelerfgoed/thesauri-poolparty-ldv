# Thesauri van PoolParty naar de LDV

Deze repository automatiseert de export van thesauri uit PoolParty
naar TriplyDB voor de Linked Data Voorziening (LDV) van de
Rijksdienst voor het Cultureel Erfgoed (RCE).

Een Python-script haalt RDF-exportbestanden op, voegt ze per
doeldataset samen en importeert ze via de TriplyDB CLI.
Daarna uploadt het script een logbestand en vraagt het synchronisatie
aan voor de ingestelde publicatieservices.

## Onderdelen

| Bestand | Functie |
|---|---|
| `thesauri-poolparty.py` | Export, samenvoeging, import en serviceverzoeken |
| `thesauri-poolparty.yaml` | Projecten, datasets, graphnamen en services |
| `requirements.txt` | Python-afhankelijkheden |
| `.github/workflows/deploy.yml` | Geplande en handmatige uitvoering |
| `.github/workflows/keep-alive.yml` | Aanvullende onderhoudsworkflow |
| `.github/dependabot.yml` | Configuratie voor afhankelijkheidsupdates |
| `tools/` | Meegeleverde hulpmiddelen |

## Gegevensverwerking

Het script verwerkt de datasets uit de YAML-configuratie achter elkaar.

Per dataset voert het script deze stappen uit:

1. Exporteer de ingestelde PoolParty-projecten als TriG.
2. Vraag daarbij de modules `concepts`, `void` en `adms` op.
3. Sla de projectexports tijdelijk op.
4. Voeg de beschikbare exports samen tot één bestand.
5. Start parallelle importopdrachten voor de ingestelde graphnamen.
6. Upload het logbestand als asset naar de dataset.
7. Vraag synchronisatie aan voor de ingestelde services.
8. Verwijder de tijdelijke projectbestanden en het lokale logbestand.

Het samengevoegde TriG-bestand blijft lokaal staan.

## Configuratie

Alle instellingen staan in `thesauri-poolparty.yaml`.

### TriplyDB

| Instelling | Functie |
|---|---|
| `cli_path` | Pad naar de TriplyDB CLI |
| `account` | Doelaccount, momenteel `thesauri` |
| `token` | Token; gebruik hiervoor de omgevingsvariabele `TRIPLYDB_TOKEN` |
| `instance` | Optionele API-host voor de serviceverzoeken |

Als `instance` ontbreekt, gebruikt het script voor serviceverzoeken:

`api.linkeddata.cultureelerfgoed.nl`

De CLI-opdrachten voor import en asset-upload krijgen geen expliciete
`--url` mee. Controleer daarom afzonderlijk welke TriplyDB-instantie
de CLI gebruikt. De instelling `instance` geldt in de huidige code
alleen voor de serviceverzoeken.

### PoolParty

De export-URL is:

`https://data.cultureelerfgoed.nl/PoolParty/api/projects/{}/export`

Het script vervangt `{}` door de ingestelde projectcode.

De omgevingsvariabele `POOLPARTY_AUTH` levert de volledige waarde
voor de HTTP-header `Authorization`.

### Projecten en datasets

Elke dataset bevat:

- `projects`: PoolParty-projectcodes met bijbehorende graphnamen;
- `services`: namen van bestaande services waarvoor het script
  synchronisatie aanvraagt.

De configuratie bevat momenteel deze doeldatasets:

| Dataset | Inhoud volgens de configuratie |
|---|---|
| `oorlogsbronnen` | WO2-thesaurus en WO2-biografieën |
| `Cultuurhistorische-Thesaurus-CHT` | Combinatie van CHT-, referentienetwerk- en ABR-projecten |
| `archeologischbasisregister` | ABR-project met graph-URI voor versie 2 |
| `referentienetwerk` | Referentienetwerk |
| `cht` | Cultuurhistorische Thesaurus |
| `homosaurus` | Homosaurus; gemarkeerd als tijdelijke oplossing |
| `onderwerpen-not` | Onderwerpenlijst voor het Termennetwerk |
| `rechtenstatus-en-gebruiksrechten` | Rechtenstatements |
| `thesauri` | Combinatie van projecten, gemarkeerd als testproject voor Jena |

De YAML-configuratie is leidend voor de exacte projectcodes,
graph-URI's en servicenamen.

## Uitvoeren via GitHub Actions

De workflow heet **Deploy Thesauri PoolParty**.

### Automatisch

De workflow staat dagelijks gepland om **03:00 UTC**:

- 04:00 uur in de Nederlandse wintertijd;
- 05:00 uur in de Nederlandse zomertijd.

Een push naar de repository start deze workflow niet.

### Handmatig

1. Open de tab **Actions**.
2. Kies **Deploy Thesauri PoolParty**.
3. Klik op **Run workflow**.
4. Controleer na afloop de uitvoer en importlogs.

### Secrets

Stel deze repositorysecrets in onder:

**Settings > Secrets and variables > Actions > New repository secret**

| Secret | Functie |
|---|---|
| `TRIPLYDB_TOKEN` | Authenticatie voor TriplyDB |
| `POOLPARTY_AUTH` | Waarde voor de PoolParty-header `Authorization` |

De workflow draait op Windows met Python 3.11.
Hij installeert de Python-afhankelijkheden en downloadt de TriplyDB CLI.

## Lokaal uitvoeren op Windows

Let op: het script voert echte imports uit.
Er is geen proefmodus zonder wijzigingen aan TriplyDB.

### 1. Repository ophalen

```text
git clone https://github.com/cultureelerfgoed/thesauri-poolparty-ldv.git
cd thesauri-poolparty-ldv
```

### 2. Python-afhankelijkheden installeren

```text
python -m pip install -r requirements.txt
```

### 3. CLI instellen

Zorg dat `cli_path` in `thesauri-poolparty.yaml` verwijst
naar een beschikbare TriplyDB CLI.

### 4. Authenticatie instellen

Gebruik in PowerShell:

```powershell
$env:TRIPLYDB_TOKEN = "<jouw-triplydb-token>"
$env:POOLPARTY_AUTH = "<jouw-volledige-authorization-header>"
```

Sla deze waarden niet op in de repository.

### 5. Script starten

Voer het script uit vanuit de hoofdmap van de repository:

```text
python thesauri-poolparty.py
```

## Uitvoer en logging

| Bestand | Functie |
|---|---|
| `<project_code>.trig` | Tijdelijke export van één PoolParty-project |
| `merged_data_<dataset>.trig` | Samengevoegde exports voor een dataset |
| `import_log_<dataset>_<date>.log` | Verwerkingslog per dataset |

Het script probeert het logbestand als asset naar TriplyDB te uploaden.
Het verwijdert daarna het lokale logbestand.

De serviceverzoeken vinden plaats na de logupload.
Het geüploade log bevat daardoor niet de latere meldingen
over die serviceverzoeken. Die staan wel in de console-uitvoer.

## Importgedrag

De huidige implementatie importeert voor iedere ingestelde graphnaam
hetzelfde samengevoegde bestand. Daarbij gebruikt het script:

- `--default-graph-name` met de ingestelde graphnaam;
- `--mode overwrite`.

Dit is geen afzonderlijke import van uitsluitend de bijbehorende
projectexport. Controleer bij wijzigingen hoe de CLI de named graphs
uit het TriG-bestand en de opgegeven default graph verwerkt.

De importopdrachten voor één dataset lopen parallel.

## Servicesynchronisatie

Het script verstuurt voor elke ingestelde service een
synchronisatieverzoek naar de TriplyDB API.

Het controleert de HTTP-respons, maar wacht niet totdat de
service klaar is met synchroniseren. Controleer de servicestatus
in TriplyDB wanneer je wilt vaststellen of de nieuwe gegevens
beschikbaar zijn.

## Controle en foutafhandeling

Controleer na uitvoering:

- of alle gewenste PoolParty-projecten zijn geëxporteerd;
- of alle imports zijn geslaagd;
- of de juiste graphs in de juiste dataset staan;
- of het logbestand als asset beschikbaar is;
- of de publicatieservices de nieuwe gegevens aanbieden.

Een succesvolle GitHub Actions-status bewijst niet dat alle
onderdelen zijn geslaagd. Verschillende functies loggen fouten
en geven `False` of `None` terug, zonder dat het hoofdproces
daarop stopt.

Daardoor kan het script:

- doorgaan met alleen de beschikbare projectexports;
- serviceverzoeken versturen na een mislukte import;
- het lokale log verwijderen na een mislukte logupload.

Er is geen automatische terugdraaiing van eerdere imports.

## Bestaande lokale bestanden

Als een projectbestand al bestaat, slaat het script de export over
en gebruikt het dat bestand opnieuw.

Bij een lokale herstart kunnen daardoor oudere exports worden gebruikt.
Controleer achtergebleven projectbestanden en samengevoegde bestanden
voordat je opnieuw start.

## Onderhoud

Werk de YAML-configuratie bij wanneer projecten, graphnamen,
datasets of services veranderen.

Controleer daarnaast periodiek:

- of de tijdelijke Homosaurus-configuratie nog nodig is;
- of het Jena-testproject `thesauri` nog bij deze verwerking hoort;
- of CLI-imports en serviceverzoeken dezelfde TriplyDB-instantie gebruiken;
- of de documentatie overeenkomt met het script en de workflow.

## Licentie

Er staat momenteel geen `LICENSE`-bestand in deze repository.
De eerdere README noemde MIT, maar die vermelding moet nog
worden bevestigd en aangevuld met een licentiebestand.

Raadpleeg voor de geëxporteerde thesauri de gebruiksvoorwaarden
van de betreffende bron.
