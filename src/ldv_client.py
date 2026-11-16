"""TriplyDB (Linked Data Voorziening): graphs en services via de API, import en assets via de CLI.

Het token gaat naar de CLI via de omgevingsvariabele TRIPLYDB_TOKEN, niet als argument: zo staat het niet in de
proceslijst of in een foutmelding.
"""
import logging
import os
import subprocess
import time

import requests

logger = logging.getLogger(__name__)

ERR_FILE = '.triplydb-js.err'


class LdvError(Exception):
    """Een API- of CLI-actie op de LDV is mislukt."""


class Ldv:
    def __init__(self, config: dict, token: str = None, cli: str = None, session=None):
        tdb = config['triplydb']
        self.url = tdb['url'].rstrip('/')
        self.account = tdb['account']
        self.token = token
        self.cli = cli
        self.import_timeout = float(tdb.get('import_timeout', 3600))
        self.sync_timeout = float(tdb.get('sync_timeout', 1800))
        self.poll_interval = float(tdb.get('poll_interval', 15))
        self.http = session or requests.Session()

    # --- API ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    def _get_all(self, path: str) -> list:
        """GET met paginering (Link: rel=next)."""
        url, items = f'{self.url}{path}', []
        while url:
            response = self.http.get(url, headers=self._headers(), timeout=60)
            if response.status_code == 404:
                raise LdvError(f'Niet gevonden in de LDV: {path}')
            if response.status_code != 200:
                raise LdvError(f'GET {path}: HTTP {response.status_code} {response.text[:200]}')
            items.extend(response.json())
            url = response.links.get('next', {}).get('url')
        return items

    def graph_counts(self, dataset: str) -> dict:
        """{graphnaam: aantal statements} zoals nu gepubliceerd."""
        graphs = self._get_all(f'/datasets/{self.account}/{dataset}/graphs')
        return {g['graphName']: int(g.get('numberOfStatements') or 0) for g in graphs}

    def services(self, dataset: str) -> list:
        return self._get_all(f'/datasets/{self.account}/{dataset}/services')

    def service(self, dataset: str, name: str) -> dict:
        response = self.http.get(f'{self.url}/datasets/{self.account}/{dataset}/services/{name}',
                                 headers=self._headers(), timeout=60)
        if response.status_code != 200:
            raise LdvError(f'Service {name}: HTTP {response.status_code} {response.text[:200]}')
        return response.json()

    def sync_service(self, dataset: str, name: str) -> None:
        response = self.http.post(f'{self.url}/datasets/{self.account}/{dataset}/services/{name}',
                                  headers={**self._headers(), 'Content-Type': 'application/json'},
                                  json={'sync': 'true'}, timeout=120)
        if response.status_code not in (200, 202):
            raise LdvError(f'Sync van service {name}: HTTP {response.status_code} {response.text[:200]}')

    def wait_for_service(self, dataset: str, name: str) -> dict:
        """Wacht tot de service draait en bij is. Geeft de laatste status terug; LdvError bij time-out of fouten."""
        deadline = time.monotonic() + self.sync_timeout
        while True:
            info = self.service(dataset, name)
            status, out_of_sync = info.get('status'), info.get('outOfSync')
            if status == 'running' and out_of_sync is False:
                if info.get('numberOfGraphErrors'):
                    raise LdvError(f"Service {name} meldt {info['numberOfGraphErrors']} graph(s) met fouten.")
                return info
            if status in ('failed', 'error'):
                raise LdvError(f'Service {name} staat op {status}: {info.get("error") or ""}'.strip())
            if time.monotonic() >= deadline:
                raise LdvError(f'Service {name} na {self.sync_timeout:.0f}s nog niet klaar (status={status}, '
                               f'outOfSync={out_of_sync}).')
            time.sleep(self.poll_interval)

    # --- CLI ------------------------------------------------------------------

    def _run_cli(self, subcommand: str, options: list, path: str, timeout: float) -> None:
        if not self.cli:
            raise LdvError('Geen TriplyDB CLI opgegeven (--cli of TRIPLYDB_CLI).')
        if not self.token:
            raise LdvError('TRIPLYDB_TOKEN ontbreekt.')
        env = {**os.environ, 'TRIPLYDB_TOKEN': self.token}
        command = [self.cli, subcommand, *options, '--account', self.account, '--url', self.url, path]
        if os.path.exists(ERR_FILE):
            os.remove(ERR_FILE)
        try:
            result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise LdvError(f'{subcommand} duurde langer dan {timeout:.0f}s en is afgebroken.')
        except OSError as e:
            raise LdvError(f'TriplyDB CLI niet te starten ({self.cli}): {e}')
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or '').strip()
            if os.path.exists(ERR_FILE):
                with open(ERR_FILE, encoding='utf-8', errors='replace') as f:
                    detail += '\n' + f.read()
            raise LdvError(f'{subcommand} mislukt (code {result.returncode}): {self._redact(detail)[-2000:]}')

    def _redact(self, text: str) -> str:
        return text.replace(self.token, '***') if self.token else text

    def import_file(self, dataset: str, path: str) -> None:
        """Vervang de graphs in `path` (N-Quads) in de dataset. Andere graphs blijven staan."""
        self._run_cli('import-from-file', ['--dataset', dataset, '--mode', 'overwrite'], path, self.import_timeout)

    def upload_asset(self, dataset: str, path: str) -> None:
        self._run_cli('upload-asset', ['--dataset', dataset, '--overwrite'], path, 600)
