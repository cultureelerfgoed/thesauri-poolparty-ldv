# thesauri-poolparty-ldv
Automatiseer PoolParty-extracties naar TriplyDB met Python en GitHub Actions.


# Thesauri PoolParty to TriplyDB

Dit project automatiseert het exporteren van thesauri uit PoolParty en het importeren ervan naar datasets in TriplyDB. Het script haalt RDF-data van PoolParty op, verwerkt deze lokaal en uploadt deze naar specifieke datasets in TriplyDB, met ondersteuning voor meerdere projecten en datasets.

## Overzicht

- **Bron**: PoolParty API
- **Doel**: TriplyDB-datasets
- **Talen**: Python 3.11
- **Workflow**: GitHub Actions voor automatisering
- **CLI**: TriplyDB CLI (`triplydb.exe`) wordt gebruikt voor het importeren en uploaden van data.

---

## Functies

1. **Meerdere projecten ondersteunen**:
   - Elk project in PoolParty wordt geëxporteerd naar een specifieke graph in een TriplyDB-dataset.
2. **Configuratie in YAML**:
   - Alle projecten en datasets worden gedefinieerd in een configuratiebestand (`thesauri-poolparty.yaml`).
3. **Logbeheer**:
   - Logs worden geüpload als assets naar de respectieve TriplyDB-datasets.
4. **Beveiliging via Secrets**:
   - Gevoelige gegevens zoals authenticatietokens worden opgeslagen als GitHub Secrets.
5. **Automatische workflow via GitHub Actions**:
   - Exporteer, verwerk en upload data met één push naar de repository.

---

## Bestandsstructuur

```plaintext
thesauri-poolparty/
├── thesauri-poolparty.py        # Python-script voor verwerking
├── thesauri-poolparty.yaml      # Configuratiebestand
├── tools/
│   └── triplydb.exe             # TriplyDB CLI
├── .github/
│   └── workflows/
│       └── deploy.yml           # GitHub Actions workflow
└── README.md                    # Projectdocumentatie
```

---

## Installatie en Gebruik

### 1. Vereisten

- **Python 3.11**: Download [hier](https://www.python.org/downloads/).
- **GitHub Desktop**: Voor het lokaal beheren van deze repository ([Download hier](https://desktop.github.com/)).

### 2. Repository klonen

Kloon de repository naar uw lokale machine:
```bash
git clone https://github.com/cultureelerfgoed/thesauri-poolparty.git
cd thesauri-poolparty
```

### 3. Installeer Python-pakketten

Voer de volgende commando's uit om afhankelijkheden te installeren:
```bash
pip install -r requirements.txt
```

### 4. Configureren van omgevingsvariabelen (lokaal)

Stel de volgende omgevingsvariabelen in:
- **Windows**:
  ```bash
  set TRIPLYDB_TOKEN=<uw-triplydb-token>
  set POOLPARTY_AUTH=<uw-poolparty-auth>
  ```
- **Linux/Mac**:
  ```bash
  export TRIPLYDB_TOKEN=<uw-triplydb-token>
  export POOLPARTY_AUTH=<uw-poolparty-auth>
  ```

### 5. Draai het script lokaal

Om het script lokaal te draaien:
```bash
python thesauri-poolparty.py
```

---

## Automatisering via GitHub Actions

De GitHub Actions workflow (`deploy.yml`) automatiseert het proces van exporteren, verwerken en uploaden naar TriplyDB. Dit gebeurt automatisch bij elke push naar de `main`-branch.

### 1. Secrets instellen

Voeg de volgende secrets toe aan uw GitHub-repository via **Settings > Secrets and variables > Actions**:

- `TRIPLYDB_TOKEN`: Uw TriplyDB-token.
- `POOLPARTY_AUTH`: Uw PoolParty-authorization-header.

### 2. Workflowoverzicht

Bij elke push:
1. **Checkout repository**: Haalt de laatste wijzigingen op.
2. **Python-setup**: Installeert de afhankelijkheden.
3. **Script uitvoeren**: Voert het script uit om data te verwerken.
4. **Logs opslaan**: Uploadt logbestanden naar de respectieve TriplyDB-datasets.

---

## Configuratiebestand (`thesauri-poolparty.yaml`)

Het configuratiebestand bevat alle informatie over PoolParty-projecten en TriplyDB-datasets.

**Voorbeeld:**
```yaml
triplydb:
  cli_path: "C:\\Users\\linkeddata\\Downloads\\triplydb.exe"
  account: "rce"
  token: "${TRIPLYDB_TOKEN}"

poolparty:
  export_url_template: "https://data.cultureelerfgoed.nl/PoolParty/api/projects/{}/export"
  auth_headers:
    Authorization: "${POOLPARTY_AUTH}"
    Content-Type: "application/json"

datasets:
  thesauri:
    projects:
      - project_code: "1DE00318-CB07-0001-FBB4-C620F33C1540"
        graph_name: "https://data.niod.nl/WO2_Thesaurus/thesaurus"
      - project_code: "1DF16AC7-7868-0001-FBB8-E60098F4D110"
        graph_name: "https://data.niod.nl/Organizations/thesaurus"
      - project_code: "1E0320A6-62BA-0001-FCF2-1C301C80F490"
        graph_name: "https://data.niod.nl/WO2_biografieen/thesaurus"

  erfgoedthesaurus:
    projects:
      - project_code: "1DF17ED4-4A38-0001-C6FF-883013B04AD0"
        graph_name: "https://data.cultureelerfgoed.nl/term/id/cht/thesaurus"
      - project_code: "f475b9b7-177b-430f-b7eb-5ccc2420ad69"
        graph_name: "https://data.cultureelerfgoed.nl/term/id/rn/2/thesaurus"

  archeologisch-basis-register:
    projects:
      - project_code: "cb410a13-a6e8-4077-a02c-412a93714114"
        graph_name: "https://data.cultureelerfgoed.nl/term/id/abr/thesaurus"

output:
  merged_file_template: "merged_data_<dataset>.trig"
  log_file_template: "import_log_<dataset>_<date>.log"
```

---

## Licentie

Dit project valt onder de MIT-licentie. Zie het bestand `LICENSE` voor meer informatie.

