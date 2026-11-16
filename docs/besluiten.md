# Besluiten en open punten

## Open punten

| # | Onderwerp | Wat is er aan de hand | Gevolg tot dan |
|---|---|---|---|
| 1 | **Rechtenstatus na de codefout** | De projectcode miste de eerste `c`; de export gaf sinds september 2026 elke dag HTTP 500, terwijl de run groen bleef. De code is gecorrigeerd. De LDV-versie is van 18 september 2026 en heeft alleen de thesaurusgraph; de eerste run voegt `metadata/void` en `metadata/adms` toe. | Controleer de eerste run (samenvatting: verschil per graph) |
| 2 | **Oude ABR-graphs in `archeologischbasisregister`** | Naast `abr/2` staan daar ook `abr/thesaurus` en `abr/metadata/*`, die geen project in deze dataset meer vullen. Ze verschillen al van de versie in `Cultuurhistorische-Thesaurus-CHT`. | Blijven staan; de run meldt ze als waarschuwing |
| 3 | **Oude logbestanden als asset** | De vorige versie zette elke dag een `import_log_<dataset>_<datum>.log` als nieuw asset bij elke dataset. | Kunnen in de LDV worden opgeruimd; de nieuwe versie gebruikt één vast asset |
| 4 | **Homosaurus en het testproject `thesauri`** | Beide staan in de configuratie als tijdelijk. | Worden gewoon meegenomen |
| 5 | **Licentie van de code** | Geen `LICENSE`-bestand. De andere RCE-ETL's gebruiken GPL-3.0. | Geen licentie |

## Genomen besluiten

| Besluit | Waarom |
|---|---|
| **Een run faalt zichtbaar** | de vorige versie logde fouten maar eindigde altijd groen. Daardoor bleef de rechtenstatus twee maanden oud zonder dat iemand het zag. |
| **Elk project één keer per run exporteren** | de CHT stond in drie datasets en werd drie keer opgehaald. |
| **Controleren vóór publiceren** | een lege, halve of afgebroken export (of een HTML-foutpagina met HTTP 200) mag nooit een gepubliceerde thesaurus vervangen. |
| **Krimpgrens van 10% ten opzichte van de LDV** | er is geen telling in PoolParty om tegen te controleren; de vorige publicatie is de beste maat. Een bewuste grote opschoning kan met `allow_shrink`. |
| **Datasets los van elkaar** | één kapot project mag de andere thesauri niet maandenlang tegenhouden. Binnen een dataset gaat het alles of niets: een dataset met een ontbrekend project wordt niet gepubliceerd. |
| **N-Quads in plaats van aan elkaar geplakte TriG** | samenvoegen per regel is veilig; prefixes en blank nodes kunnen niet botsen. Het parsen is meteen de syntaxcontrole. |
| **Eén import per dataset, `--mode overwrite`** | de vorige versie importeerde hetzelfde bestand parallel één keer per graph. Eén import vervangt precies de graphs uit de export en laat andere graphs staan. |
| **Triples zonder graph gaan naar de thesaurusgraph** | zo tellen export en LDV hetzelfde. PoolParty levert ze nu niet, maar de run meldt het als het gebeurt. |
| **Telling achteraf** | een geslaagde CLI-aanroep bewijst niet dat de data er staat; het aantal statements per graph wel. |
| **Alle services synchroniseren en erop wachten** | de lijst in de oude configuratie klopte niet meer (`referentienetwerk` heeft geen services, `homosaurus` geen Jena). Een service die niet bij is, levert oude data. |
| **Token via de omgeving, nooit als argument** | anders staat het in de proceslijst en in foutmeldingen. |
| **Linux-runner, Python 3.12, CLI per run ophalen** | zoals de andere RCE-ETL's. De CLI hoort niet in de repository (40 MB). |
| **Eén rapport-asset per dataset met een vaste naam** | de oude logbestanden liepen op. |
