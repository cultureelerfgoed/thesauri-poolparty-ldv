"""Gedeelde hulpfuncties: configuratie laden en controleren, logging (ook als GitHub-annotaties) en de samenvatting."""
import logging
import os
import re

import yaml

logger = logging.getLogger(__name__)

UUID = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


class ConfigError(Exception):
    """De configuratie is onbruikbaar; de run stopt voordat er iets gebeurt."""


def load_config(path: str = None) -> dict:
    path = path or os.getenv('CONFIG_PATH', 'config/config.yml')
    with open(path, encoding='utf-8') as f:
        config = yaml.safe_load(f)
    check_config(config)
    return config


def check_config(config: dict) -> None:
    """Weiger een configuratie die tot een verkeerde publicatie kan leiden."""
    for section in ('poolparty', 'triplydb', 'checks', 'datasets'):
        if not config.get(section):
            raise ConfigError(f"Sectie '{section}' ontbreekt in de configuratie.")
    graph_of = {}
    for name, dataset in config['datasets'].items():
        projects = (dataset or {}).get('projects') or []
        if not projects:
            raise ConfigError(f"Dataset '{name}' heeft geen projecten.")
        graphs = set()
        for project in projects:
            code, graph = project.get('project_code'), project.get('graph_name')
            if not code or not graph:
                raise ConfigError(f"Dataset '{name}': elk project heeft project_code en graph_name nodig.")
            if graph in graphs:
                raise ConfigError(f"Dataset '{name}': graph {graph} staat er twee keer in.")
            graphs.add(graph)
            if graph_of.setdefault(code, graph) != graph:
                raise ConfigError(f'Project {code} heeft in verschillende datasets een andere graph_name '
                                  f'({graph_of[code]} en {graph}).')
            if not UUID.match(code):
                logger.warning("Projectcode '%s' (dataset %s) is geen geldige UUID; controleer de code in PoolParty.",
                               code, name)


def select_datasets(config: dict, selection: str) -> list:
    """'all' of een kommagescheiden lijst datasetnamen; onbekende namen zijn een fout."""
    available = list(config['datasets'])
    if not selection or selection.strip() == 'all':
        return available
    names = [n.strip() for n in selection.split(',') if n.strip()]
    unknown = [n for n in names if n not in config['datasets']]
    if unknown:
        raise ConfigError(f"Onbekende dataset: {', '.join(unknown)} (beschikbaar: {', '.join(available)})")
    return names


class _GitHubAnnotations(logging.Handler):
    """Zet waarschuwingen en fouten ook als annotatie in de GitHub Actions-weergave."""

    def emit(self, record):
        if record.levelno >= logging.WARNING:
            kind = 'error' if record.levelno >= logging.ERROR else 'warning'
            message = record.getMessage().replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::{kind}::{message}', flush=True)


def setup_logging(log_file: str = None) -> None:
    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    if os.getenv('GITHUB_ACTIONS') == 'true':
        handlers.append(_GitHubAnnotations())
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO, handlers=handlers, force=True)
    # requests/urllib3 loggen anders volledige URL's en retries dubbel
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def write_summary(markdown: str) -> None:
    """Schrijf naar de samenvatting van de GitHub Action (als die er is)."""
    path = os.getenv('GITHUB_STEP_SUMMARY')
    if path:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(markdown.rstrip() + '\n\n')


def data_dir(path: str = None) -> str:
    path = path or os.getenv('CACHE_PATH', 'data')
    os.makedirs(path, exist_ok=True)
    return path
