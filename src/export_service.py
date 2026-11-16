"""Exporteer de thesauri uit PoolParty, controleer ze en zet per dataset één N-Quads-bestand klaar voor publicatie.

Gebruik:
    python src/export_service.py                         # alle datasets
    python src/export_service.py --datasets cht,homosaurus
    python src/export_service.py --allow-shrink          # krimp van een graph eenmalig toestaan

Per run:
  1. Elk project dat in de gekozen datasets voorkomt wordt één keer geëxporteerd (TriG), ook als het in meer datasets staat.
  2. De export moet een geldige TriG zijn, de thesaurusgraph (graph_name) bevatten en minstens `min_concepts`
     skos:Concept hebben. Triples zonder graph gaan naar de thesaurusgraph.
  3. Per dataset worden de projecten samengevoegd tot `{CACHE_PATH}/{dataset}.nq.gz`.
  4. Elke graph wordt vergeleken met de LDV: is hij meer dan `max_shrink_percent` kleiner geworden, dan wordt de dataset
     niet gepubliceerd (bescherming tegen een halve export). Graphs die in de LDV staan maar niet in de export, blijven
     ongemoeid en worden gemeld.
  5. `{CACHE_PATH}/manifest.json` legt per project en dataset vast wat er is gebeurd; de publicatie leest alleen dit bestand.

Een dataset wordt alleen gepubliceerd als AL zijn projecten en controles slagen. Datasets staan los van elkaar: een fout bij
één dataset houdt de andere niet tegen, maar de run eindigt dan wel met afsluitcode 1.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import logging
import os
import shutil
import sys
import time

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF, SKOS

import common
import ldv_client
import poolparty_client

logger = logging.getLogger(__name__)


class ProjectError(Exception):
    """De export van een project is onbruikbaar."""


# --- één project ---------------------------------------------------------------

def analyse(raw: bytes, graph_name: str, min_concepts: int) -> tuple:
    """Parse de TriG, verplaats triples zonder graph naar de thesaurusgraph en tel per graph.

    Geeft (rdflib Dataset, {graph: {'statements', 'concepts'}}, aantal verplaatste triples)."""
    ds = Dataset()
    try:
        ds.parse(data=raw, format='trig')
    except Exception as e:
        raise ProjectError(f'export is geen geldige TriG: {type(e).__name__}: {str(e)[:300]}')

    default = ds.default_graph if hasattr(type(ds), 'default_graph') else ds.default_context
    moved = len(default)
    if moved:
        target = ds.graph(URIRef(graph_name))
        for triple in default:
            target.add(triple)
        default.remove((None, None, None))

    graphs = {}
    for graph in ds.graphs():
        if graph.identifier == default.identifier or len(graph) == 0:
            continue
        graphs[str(graph.identifier)] = {'statements': len(graph),
                                         'concepts': len(set(graph.subjects(RDF.type, SKOS.Concept)))}
    if graph_name not in graphs:
        raise ProjectError(f'de thesaurusgraph {graph_name} staat niet in de export '
                           f'(wel: {", ".join(sorted(graphs)) or "geen enkele graph"})')
    if graphs[graph_name]['concepts'] < min_concepts:
        raise ProjectError(f'{graph_name} bevat {graphs[graph_name]["concepts"]} skos:Concept '
                           f'(minimaal {min_concepts})')
    return ds, graphs, moved


def export_project(code: str, graph_name: str, config: dict, auth: str, out_dir: str) -> dict:
    """Exporteer, controleer en schrijf één project als N-Quads. Geeft een resultaat, gooit niet."""
    result = {'project_code': code, 'graph_name': graph_name, 'status': 'failed', 'error': None}
    started = time.monotonic()
    logger.info('Export project %s (%s)', code, graph_name)
    try:
        raw = poolparty_client.export_project(code, config, auth)
        result['export_bytes'] = len(raw)
        ds, graphs, moved = analyse(raw, graph_name, int(config['checks'].get('min_concepts', 1)))
        del raw
        path = os.path.join(out_dir, f'{code}.nq.gz')
        with gzip.open(path, 'wb') as f:
            ds.serialize(destination=f, format='nquads', encoding='utf-8')
        del ds
        result.update(status='ok', graphs=graphs, moved_from_default_graph=moved, file=path)
        if moved:
            logger.warning('Project %s: %d triples zonder graph zijn in %s gezet.', code, moved, graph_name)
        logger.info('Project %s: %s', code, ', '.join(f'{g} {i["statements"]} statements/{i["concepts"]} concepten'
                                                   for g, i in graphs.items()))
    except (poolparty_client.ExportError, ProjectError) as e:
        result['error'] = str(e)
        logger.error('Project %s mislukt: %s', code, e)
    except Exception as e:  # onverwacht: niet stilzwijgend door, wel de andere projecten afmaken
        result['error'] = f'onverwachte fout: {type(e).__name__}: {e}'
        logger.exception('Project %s mislukt door een onverwachte fout', code)
    result['seconds'] = round(time.monotonic() - started, 1)
    return result


# --- één dataset ---------------------------------------------------------------

def compare_with_ldv(graphs: dict, live: dict, max_shrink: float, allow_shrink: bool) -> tuple:
    """Vergelijk de nieuwe graphs met de LDV. Geeft (fouten, waarschuwingen) en vult per graph `live_statements`."""
    errors, warnings = [], []
    for name, info in graphs.items():
        before = live.get(name)
        info['live_statements'] = before
        if before is None:
            warnings.append(f'graph {name} is nieuw in deze dataset')
        elif before and info['statements'] < before * (1 - max_shrink / 100):
            message = (f'graph {name} krimpt van {before} naar {info["statements"]} statements '
                       f'(meer dan {max_shrink:g}%)')
            (warnings if allow_shrink else errors).append(message + (' — toegestaan met --allow-shrink'
                                                                     if allow_shrink else ''))
    for name in sorted(set(live) - set(graphs)):
        warnings.append(f'graph {name} staat in de LDV maar niet in de export; hij blijft ongewijzigd staan')
    return errors, warnings


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def build_dataset(name: str, config: dict, projects: dict, ldv, out_dir: str, allow_shrink: bool) -> dict:
    """Voeg de projecten van een dataset samen en controleer tegen de LDV."""
    entry = {'status': 'failed', 'errors': [], 'warnings': [], 'projects': [], 'graphs': {}}
    for project in config['datasets'][name]['projects']:
        code = project['project_code']
        entry['projects'].append(code)
        result = projects[code]
        if result['status'] != 'ok':
            entry['errors'].append(f'project {code} mislukt: {result["error"]}')
            continue
        for graph, info in result['graphs'].items():
            if graph in entry['graphs']:
                entry['errors'].append(f'graph {graph} komt uit meer dan één project')
            entry['graphs'][graph] = dict(info)

    if not entry['errors']:
        try:
            live = ldv.graph_counts(name)
        except Exception as e:
            entry['errors'].append(f'vergelijking met de LDV niet mogelijk: {e}')
        else:
            errors, warnings = compare_with_ldv(entry['graphs'], live,
                                                float(config['checks'].get('max_shrink_percent', 10)), allow_shrink)
            entry['errors'] += errors
            entry['warnings'] += warnings

    if not entry['errors']:
        path = os.path.join(out_dir, f'{name}.nq.gz')
        with gzip.open(path, 'wb') as dst:
            for code in entry['projects']:
                with gzip.open(projects[code]['file'], 'rb') as src:
                    shutil.copyfileobj(src, dst)
        entry.update(status='ok', file=os.path.basename(path), sha256=sha256(path),
                     statements=sum(i['statements'] for i in entry['graphs'].values()))

    for message in entry['warnings']:
        logger.warning('%s: %s', name, message)
    for message in entry['errors']:
        logger.error('%s: %s', name, message)
    logger.info('Dataset %s: %s', name, 'klaar voor publicatie' if entry['status'] == 'ok' else 'WORDT NIET GEPUBLICEERD')
    return entry


# --- run -----------------------------------------------------------------------

def summary_markdown(manifest: dict) -> str:
    lines = ['## Export uit PoolParty', '',
             '| Dataset | Status | Graph | Statements | Nu in LDV | Verschil | Concepten |', '|---|---|---|--:|--:|--:|--:|']
    for name, entry in manifest['datasets'].items():
        status = '✅ klaar' if entry['status'] == 'ok' else '❌ niet publiceren'
        if not entry['graphs']:
            lines.append(f'| {name} | {status} | | | | | |')
        for graph, info in entry['graphs'].items():
            before = info.get('live_statements')
            diff = '' if before is None else f'{info["statements"] - before:+d}'
            lines.append(f'| {name} | {status} | `{graph}` | {info["statements"]} | '
                         f'{"" if before is None else before} | {diff} | {info["concepts"]} |')
    problems = [f'- **{n}**: {m}' for n, e in manifest['datasets'].items() for m in e['errors']]
    notes = [f'- {n}: {m}' for n, e in manifest['datasets'].items() for m in e['warnings']]
    if problems:
        lines += ['', '### Fouten', *problems]
    if notes:
        lines += ['', '<details><summary>Meldingen</summary>', '', *notes, '', '</details>']
    return '\n'.join(lines)


def run(config: dict, names: list, auth: str, out_dir: str, allow_shrink: bool = False, ldv=None) -> dict:
    ldv = ldv or ldv_client.Ldv(config, token=os.getenv('TRIPLYDB_TOKEN'))
    project_dir = os.path.join(out_dir, 'projects')
    os.makedirs(project_dir, exist_ok=True)
    manifest = {'started_at': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
                'account': config['triplydb']['account'], 'allow_shrink': allow_shrink,
                'projects': {}, 'datasets': {}}

    wanted = {}
    for name in names:
        for project in config['datasets'][name]['projects']:
            wanted.setdefault(project['project_code'], project['graph_name'])
    logger.info('%d dataset(s), %d unieke project(en)', len(names), len(wanted))
    for code, graph_name in wanted.items():
        manifest['projects'][code] = export_project(code, graph_name, config, auth, project_dir)

    for name in names:
        manifest['datasets'][name] = build_dataset(name, config, manifest['projects'], ldv, out_dir, allow_shrink)

    manifest['complete'] = all(e['status'] == 'ok' for e in manifest['datasets'].values())
    manifest['finished_at'] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    for result in manifest['projects'].values():
        result.pop('file', None)          # lokaal pad, niet nodig na de export
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Exporteer en controleer de thesauri uit PoolParty.')
    parser.add_argument('--datasets', default='all', help="'all' of een kommagescheiden lijst datasetnamen")
    parser.add_argument('--allow-shrink', action='store_true',
                        help='publiceer ook als een graph meer dan max_shrink_percent krimpt (eenmalig, bewust)')
    args = parser.parse_args(argv)

    out_dir = common.data_dir()
    common.setup_logging(os.path.join(out_dir, 'export.log'))
    try:
        config = common.load_config()
        names = common.select_datasets(config, args.datasets)
    except (common.ConfigError, OSError) as e:
        logger.error('Configuratie: %s', e)
        return 2
    auth = os.getenv('POOLPARTY_AUTH')
    if not auth:
        logger.error('POOLPARTY_AUTH ontbreekt (de volledige waarde van de Authorization-header).')
        return 2

    manifest = run(config, names, auth, out_dir, args.allow_shrink)
    common.write_summary(summary_markdown(manifest))
    failed = [n for n, e in manifest['datasets'].items() if e['status'] != 'ok']
    if failed:
        logger.error('Niet klaar voor publicatie: %s', ', '.join(failed))
        return 1
    logger.info('Alle %d dataset(s) klaar voor publicatie.', len(names))
    return 0


if __name__ == '__main__':
    sys.exit(main())
