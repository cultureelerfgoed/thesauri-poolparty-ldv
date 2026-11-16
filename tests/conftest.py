import gzip
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

BASE = 'https://data.cultureelerfgoed.nl/term/id/test'
THESAURUS = f'{BASE}/thesaurus'
VOID = f'{BASE}/metadata/void'


def trig(base=BASE, concepts=3, default_triples=0, with_void=True) -> bytes:
    """Een kleine PoolParty-achtige TriG-export: thesaurusgraph met concepten, plus void."""
    lines = ['@prefix skos: <http://www.w3.org/2004/02/skos/core#> .',
             '@prefix void: <http://rdfs.org/ns/void#> .', '',
             f'<{base}/thesaurus> {{',
             f'  <{base}/scheme> a skos:ConceptScheme .']
    for i in range(concepts):
        lines.append(f'  <{base}/{i}> a skos:Concept ; skos:prefLabel "term {i}"@nl ; skos:inScheme <{base}/scheme> .')
    lines.append('}')
    if with_void:
        lines += [f'<{base}/metadata/void> {{', f'  <{base}/void> a void:Dataset .', '}']
    for i in range(default_triples):
        lines.append(f'<{base}/{i}> skos:notation "{i}" .')
    return '\n'.join(lines).encode('utf-8')


def read_nquads(path) -> list:
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [line for line in f if line.strip()]


@pytest.fixture
def config():
    return {
        'poolparty': {'export_url': 'https://pp.example/api/projects/{project}/export', 'modules': ['concepts', 'void'],
                      'timeout': 5, 'retries': 3, 'backoff': 0},
        'triplydb': {'url': 'https://api.example', 'account': 'thesauri', 'import_timeout': 5, 'sync_timeout': 1,
                     'poll_interval': 0, 'report_asset': 'etl-rapport.json'},
        'checks': {'min_concepts': 1, 'max_shrink_percent': 10, 'max_import_deviation_percent': 1},
        'datasets': {
            'een': {'projects': [{'project_code': 'P1', 'graph_name': 'https://ex.org/p1/thesaurus'}]},
            'twee': {'projects': [{'project_code': 'P1', 'graph_name': 'https://ex.org/p1/thesaurus'},
                                  {'project_code': 'P2', 'graph_name': 'https://ex.org/p2/thesaurus'}]},
            'drie': {'projects': [{'project_code': 'P3', 'graph_name': 'https://ex.org/p3/thesaurus'}]},
        },
    }


class FakeLdv:
    """Nagebootste LDV: graphs met aantallen, services, en een import die de aantallen uit het bestand overneemt."""

    def __init__(self, live=None, services=None, fail_import=(), drop_graph=None):
        self.live = live or {}
        self.services_by_dataset = services or {}
        self.fail_import = set(fail_import)
        self.drop_graph = drop_graph
        self.imports, self.synced, self.assets = [], [], []

    def graph_counts(self, dataset):
        if dataset not in self.live:
            import ldv_client
            raise ldv_client.LdvError(f'Niet gevonden in de LDV: /datasets/thesauri/{dataset}/graphs')
        return dict(self.live[dataset])

    def import_file(self, dataset, path):
        import ldv_client
        if dataset in self.fail_import:
            raise ldv_client.LdvError('import-from-file mislukt (code 1): Error: boom')
        self.imports.append(dataset)
        counts = {}
        for line in read_nquads(path):
            graph = line.rsplit(' ', 2)[-2].strip('<>')
            counts[graph] = counts.get(graph, 0) + 1
        if self.drop_graph:
            counts.pop(self.drop_graph, None)
        self.live.setdefault(dataset, {}).update(counts)

    def services(self, dataset):
        return [{'name': n} for n in self.services_by_dataset.get(dataset, [])]

    def sync_service(self, dataset, name):
        self.synced.append((dataset, name))

    def wait_for_service(self, dataset, name):
        return {'status': 'running', 'outOfSync': False, 'numberOfLoadedStatements': 1}

    def upload_asset(self, dataset, path):
        with open(path, encoding='utf-8') as f:
            self.assets.append((dataset, pathlib.Path(path).name, f.read()))
