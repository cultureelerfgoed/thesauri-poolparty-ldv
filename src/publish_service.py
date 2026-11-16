"""Publiceer de goedgekeurde exports in de LDV en synchroniseer de services.

Gebruik:
    python src/publish_service.py                         # alles wat in data/manifest.json klaarstaat
    python src/publish_service.py --datasets cht --dry-run

Leest alleen `{CACHE_PATH}/manifest.json` van export_service.py. Per dataset met status ok:
  1. controleer de checksum van `{dataset}.nq.gz` (het bestand is onderweg niet veranderd);
  2. importeer met `--mode overwrite`: de graphs in het bestand worden vervangen, andere graphs blijven staan;
  3. controleer dat elke graph in de LDV nu (vrijwel) evenveel statements heeft als de export;
  4. synchroniseer ALLE services van de dataset en wacht tot ze draaien en bij zijn;
  5. zet het rapport als asset `etl-rapport.json` bij de dataset (vaste naam: er loopt niets op).
Datasets gaan één voor één, nooit parallel. Afsluitcode 1 als een import, controle of sync mislukt.
"""
import argparse
import datetime
import json
import logging
import os
import sys
import tempfile

import common
import export_service
import ldv_client

logger = logging.getLogger(__name__)


def default_cli() -> str:
    return os.getenv('TRIPLYDB_CLI') or ('triplydb.exe' if os.name == 'nt' else './triplydb-linux')


def verify_import(ldv, name: str, graphs: dict, max_deviation: float) -> list:
    """Vergelijk de LDV na de import met de export. Geeft een lijst fouten."""
    live = ldv.graph_counts(name)
    errors = []
    for graph, info in graphs.items():
        expected, actual = info['statements'], live.get(graph)
        info['published_statements'] = actual
        if actual is None:
            errors.append(f'graph {graph} staat na de import niet in de LDV')
        elif expected and abs(actual - expected) / expected * 100 > max_deviation:
            errors.append(f'graph {graph} heeft na de import {actual} statements, de export had er {expected}')
        elif actual != expected:
            logger.info('%s: %s heeft %d statements in de LDV, %d in de export (binnen de marge).',
                        name, graph, actual, expected)
    return errors


def sync_services(ldv, name: str) -> tuple:
    """Synchroniseer alle services en wacht erop. Geeft ({service: status}, fouten)."""
    services, errors = {}, []
    names = [s['name'] for s in ldv.services(name)]
    if not names:
        logger.info('%s heeft geen services; niets te synchroniseren.', name)
        return services, errors
    for service in names:          # eerst alle syncs starten, zodat ze tegelijk lopen
        try:
            ldv.sync_service(name, service)
            logger.info('%s: sync van %s gestart', name, service)
        except ldv_client.LdvError as e:
            errors.append(str(e))
            services[service] = 'sync mislukt'
    for service in names:
        if service in services:
            continue
        try:
            info = ldv.wait_for_service(name, service)
            services[service] = f"bij ({info.get('numberOfLoadedStatements')} statements)"
            logger.info('%s: %s is bij (%s statements)', name, service, info.get('numberOfLoadedStatements'))
        except ldv_client.LdvError as e:
            errors.append(str(e))
            services[service] = 'niet bij'
    return services, errors


def upload_report(ldv, name: str, report: dict, asset_name: str) -> None:
    """Zet het rapport als asset bij de dataset; een mislukte upload is een waarschuwing, de data is al gepubliceerd."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, asset_name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        try:
            ldv.upload_asset(name, path)
        except ldv_client.LdvError as e:
            logger.warning('%s: rapport niet als asset geüpload: %s', name, e)


def run_url() -> str:
    if os.getenv('GITHUB_RUN_ID'):
        return f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
    return None


def publish_dataset(ldv, config: dict, name: str, entry: dict, data_dir: str, dry_run: bool) -> dict:
    result = {'dataset': name, 'status': 'failed', 'errors': [], 'services': {}}
    path = os.path.join(data_dir, entry['file'])
    if not os.path.exists(path):
        result['errors'].append(f'bestand {entry["file"]} ontbreekt')
        return result
    if export_service.sha256(path) != entry['sha256']:
        result['errors'].append(f'checksum van {entry["file"]} klopt niet met het manifest')
        return result
    if dry_run:
        logger.info('[droog] %s: zou %s importeren (%d statements in %d graphs) en de services synchroniseren.',
                    name, entry['file'], entry['statements'], len(entry['graphs']))
        result['status'] = 'dry-run'
        return result

    logger.info('%s: import van %s (%d statements)', name, entry['file'], entry['statements'])
    try:
        ldv.import_file(name, path)
        result['errors'] += verify_import(ldv, name, entry['graphs'],
                                          float(config['checks'].get('max_import_deviation_percent', 1)))
    except ldv_client.LdvError as e:
        result['errors'].append(str(e))
    if not result['errors']:
        try:
            result['services'], errors = sync_services(ldv, name)
            result['errors'] += errors
        except ldv_client.LdvError as e:
            result['errors'].append(str(e))
    result['status'] = 'ok' if not result['errors'] else 'failed'

    report = {'dataset': name, 'account': config['triplydb']['account'], 'status': result['status'],
              'published_at': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
              'run': run_url(), 'errors': result['errors'], 'warnings': entry['warnings'], 'graphs': entry['graphs'],
              'services': result['services'], 'projects': entry['projects']}
    upload_report(ldv, name, report, config['triplydb'].get('report_asset', 'etl-rapport.json'))
    return result


def summary_markdown(results: dict) -> str:
    icons = {'ok': '✅ gepubliceerd', 'failed': '❌ mislukt', 'skipped': '⏭️ overgeslagen', 'dry-run': '🔍 droog'}
    lines = ['## Publicatie in de LDV', '', '| Dataset | Status | Services | Opmerking |', '|---|---|---|---|']
    for name, r in results.items():
        services = ', '.join(f'{s}: {v}' for s, v in r['services'].items())
        lines.append(f"| {name} | {icons.get(r['status'], r['status'])} | {services} | {'; '.join(r['errors'])} |")
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Publiceer de goedgekeurde exports in de LDV.')
    parser.add_argument('--datasets', default='all', help="'all' of een kommagescheiden lijst datasetnamen")
    parser.add_argument('--cli', default=default_cli(), help='pad naar de TriplyDB CLI (standaard: TRIPLYDB_CLI)')
    parser.add_argument('--dry-run', action='store_true', help='controleer alleen; importeer en synchroniseer niets')
    args = parser.parse_args(argv)

    data_dir = common.data_dir()
    common.setup_logging(os.path.join(data_dir, 'publish.log'))
    try:
        config = common.load_config()
        names = common.select_datasets(config, args.datasets)
        with open(os.path.join(data_dir, 'manifest.json'), encoding='utf-8') as f:
            manifest = json.load(f)
    except (common.ConfigError, OSError, ValueError) as e:
        logger.error('Kan niet starten: %s', e)
        return 2
    if manifest.get('account') != config['triplydb']['account']:
        logger.error('Het manifest hoort bij account %s, de configuratie bij %s.', manifest.get('account'),
                     config['triplydb']['account'])
        return 2
    token = os.getenv('TRIPLYDB_TOKEN')
    if not token and not args.dry_run:
        logger.error('TRIPLYDB_TOKEN ontbreekt.')
        return 2

    ldv = ldv_client.Ldv(config, token=token, cli=args.cli)
    results = {}
    for name in names:
        entry = manifest['datasets'].get(name)
        if entry is None:
            logger.warning('%s staat niet in het manifest (niet geëxporteerd); overgeslagen.', name)
            continue
        if entry['status'] != 'ok':
            logger.warning('%s wordt niet gepubliceerd: de export is afgekeurd (%s).', name, '; '.join(entry['errors']))
            results[name] = {'status': 'skipped', 'errors': ['export afgekeurd'], 'services': {}}
            continue
        results[name] = publish_dataset(ldv, config, name, entry, data_dir, args.dry_run)
        for message in results[name]['errors']:
            logger.error('%s: %s', name, message)

    common.write_summary(summary_markdown(results))
    failed = [n for n, r in results.items() if r['status'] == 'failed']
    if failed:
        logger.error('Publicatie mislukt voor: %s', ', '.join(failed))
        return 1
    logger.info('Publicatie klaar: %s', ', '.join(n for n, r in results.items() if r['status'] in ('ok', 'dry-run'))
                or 'niets te publiceren')
    return 0


if __name__ == '__main__':
    sys.exit(main())
