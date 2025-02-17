import requests
import os
import subprocess
import logging
import yaml
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Functie om de configuratie uit een YAML-bestand te laden
def load_config(config_file="thesauri-poolparty.yaml"):
    with open(config_file, "r") as file:
        config = yaml.safe_load(file)

    # Gebruik omgevingsvariabelen voor gevoelige data
    config["triplydb"]["token"] = os.getenv("TRIPLYDB_TOKEN", config["triplydb"].get("token"))
    config["poolparty"]["auth_headers"]["Authorization"] = os.getenv(
        "POOLPARTY_AUTH", config["poolparty"]["auth_headers"].get("Authorization")
    )

    return config

# Logging instellen
def setup_logging(log_file):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),  # Log naar bestand
            logging.StreamHandler()         # Log naar console
        ]
    )

# Functie om logginghandlers af te sluiten
def close_logging():
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)

# Exporteer RDF-data vanuit PoolParty
def export_rdf_data(project_code, export_url_template, headers, output_file):
    if os.path.exists(output_file):
        logging.info(f"Bestand '{output_file}' bestaat al, overslaan...")
        return None

    logging.info(f"Start export voor project {project_code}...")
    try:
        response = requests.post(
            export_url_template.format(project_code),
            headers=headers,
            json={"prettyPrint": True, "format": "TriG", "modules": ["concepts"]}
        )
        if response.status_code == 200:
            logging.info(f"Export succesvol voor project {project_code}!")
            return response.content
        else:
            logging.error(f"Fout bij export voor project {project_code}: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logging.error(f"Onverwachte fout bij export voor project {project_code}: {e}")
        return None

# Sla RDF-data op in een bestand
def save_to_file(data, file_name):
    try:
        with open(file_name, "wb") as file:
            file.write(data)
        logging.info(f"Data opgeslagen in bestand: {file_name}")
        return True
    except Exception as e:
        logging.error(f"Fout bij opslaan van bestand {file_name}: {e}")
        return False

# Controleer of bestanden moeten worden samengevoegd
def should_merge(input_files, output_file):
    if not os.path.exists(output_file):
        return True
    output_mtime = os.path.getmtime(output_file)
    for file in input_files:
        if os.path.getmtime(file) > output_mtime:
            return True
    return False

# Voeg meerdere bestanden samen tot één bestand
def merge_files(input_files, output_file):
    logging.info("Start met samenvoegen van bestanden...")
    try:
        with open(output_file, "wb") as merged_file:
            for file_path in input_files:
                with open(file_path, "rb") as input_file:
                    merged_file.write(input_file.read())
        logging.info(f"Bestanden samengevoegd in {output_file}")
        return True
    except Exception as e:
        logging.error(f"Fout bij samenvoegen van bestanden: {e}")
        return False

# Importeer een bestand naar TriplyDB via de CLI
def import_with_triplydb(file_path, cli_path, dataset_name, account_name, graph_name, token):
    logging.info(f"Start met importeren van '{file_path}' naar graph '{graph_name}' in dataset '{dataset_name}'...")
    try:
        command = [
            cli_path,
            "import-from-file",
            "--dataset", dataset_name,
            "--account", account_name,
            "--token", token,
            "--default-graph-name", graph_name,
            "--mode", "overwrite",  # Merge: om overwrite-bug te omzeilen
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Import succesvol voor graph {graph_name}!")
            return True
        else:
            logging.error(f"Fout bij importeren van '{file_path}' naar graph '{graph_name}': {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Onverwachte fout tijdens import: {e}")
        return False

# Parallel importeren van graphs
def import_graph_parallel(graphs, merged_file, cli_path, dataset_name, account_name, token):
    def import_task(graph_name):
        return import_with_triplydb(
            merged_file, cli_path, dataset_name, account_name, graph_name, token
        )

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(import_task, graphs))
    return results

# Service synchroniseren via de TriplyDB API
def sync_triplydb_service(token, instance, account, dataset, service_name):
    """
    Roept de TriplyDB API aan om een bestaande service te synchroniseren.
    service_name is bijvoorbeeld 'archeologischbasisregister-jena' of 'archeologischbasisregister-virtuoso'.
    """
    url = f"https://{instance}/datasets/{account}/{dataset}/services/{service_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"sync": "true"}
    logging.info(f"Start synchroniseren van service '{service_name}' voor dataset '{dataset}'...")
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            logging.info(f"Service '{service_name}' succesvol gesynchroniseerd voor dataset '{dataset}'!")
            return True
        else:
            logging.error(f"Fout bij synchroniseren service '{service_name}': {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logging.error(f"Onverwachte fout bij service sync '{service_name}': {e}")
        return False

# Upload een logbestand als asset naar TriplyDB
def upload_asset(file_path, cli_path, dataset_name, account_name, token):
    logging.info(f"Start met uploaden van asset '{file_path}' naar dataset '{dataset_name}' in account '{account_name}'...")
    try:
        command = [
            cli_path,
            "upload-asset",
            "--dataset", dataset_name,
            "--account", account_name,
            "--token", token,
            "--overwrite",
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Asset succesvol geüpload: {file_path}")
            return True
        else:
            logging.error(f"Fout bij uploaden van asset '{file_path}': {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Onverwachte fout bij uploaden van asset: {e}")
        return False

# Hoofdproces
def main():
    # 1. Laad configuratie
    config = load_config()
    triplydb_config = config["triplydb"]
    poolparty_config = config["poolparty"]
    datasets = config["datasets"]
    output_config = config["output"]

    # Haal evt. de TriplyDB instance uit de config of gebruik een standaard (bijv. api.triplydb.com).
    instance = triplydb_config.get("instance", "api.linkeddata.cultureelerfgoed.nl")

    # 2. Verwerk elke dataset afzonderlijk
    for dataset_name, dataset_config in datasets.items():
        log_file = output_config["log_file_template"].replace("<dataset>", dataset_name).replace("<date>", datetime.now().strftime("%Y%m%d"))
        merged_file = output_config["merged_file_template"].replace("<dataset>", dataset_name)
        setup_logging(log_file)

        temp_files = []

        try:
            # a. Exporteer data per project
            for project in dataset_config["projects"]:
                project_code = project["project_code"]
                file_name = f"{project_code}.trig"
                data = export_rdf_data(project_code, poolparty_config["export_url_template"], poolparty_config["auth_headers"], file_name)
                if data and save_to_file(data, file_name):
                    temp_files.append((file_name, project["graph_name"]))
                elif os.path.exists(file_name):
                    temp_files.append((file_name, project["graph_name"]))

            # b. Merge bestanden als nodig
            if should_merge([file[0] for file in temp_files], merged_file):
                merge_files([file[0] for file in temp_files], merged_file)
            else:
                logging.info(f"Samengevoegd bestand '{merged_file}' is up-to-date, overslaan...")

            # c. Parallel importeren naar TriplyDB
            graph_names = [graph_name for _, graph_name in temp_files]
            import_graph_parallel(
                graph_names,
                merged_file,
                triplydb_config["cli_path"],
                dataset_name,
                triplydb_config["account"],
                triplydb_config["token"]
            )

            # d. Upload logbestand als asset
            upload_asset(
                log_file,
                triplydb_config["cli_path"],
                dataset_name,
                triplydb_config["account"],
                triplydb_config["token"]
            )

            # e. Services synchroniseren (alleen als deze gedefinieerd zijn)
            services = dataset_config.get("services", [])
            for service_name in services:
                sync_triplydb_service(
                    triplydb_config["token"],
                    instance,
                    triplydb_config["account"],
                    dataset_name,
                    service_name
                )

        finally:
            # Sluit logging netjes af
            close_logging()

            # Verwijder tijdelijke bestanden
            for file_name, _ in temp_files:
                os.remove(file_name)
            os.remove(log_file)

    logging.info("Proces voltooid.")

# Start het script
if __name__ == "__main__":
    main()
