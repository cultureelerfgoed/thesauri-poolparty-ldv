"""De echte configuratie, de configuratiecontroles en de LDV-client (zonder netwerk)."""
import pytest

import common
import ldv_client
from conftest import ROOT


def test_repository_config_is_valid():
    config = common.load_config(str(ROOT / 'config' / 'config.yml'))
    assert config['triplydb']['account'] == 'thesauri'
    assert len(config['datasets']) >= 1


def test_every_project_code_is_a_uuid():
    """Een tikfout in een projectcode gaf maandenlang een stille HTTP 500 (rechtenstatus, 2026)."""
    config = common.load_config(str(ROOT / 'config' / 'config.yml'))
    bad = [p['project_code'] for d in config['datasets'].values() for p in d['projects']
           if not common.UUID.match(p['project_code'])]
    assert bad == []


def test_conflicting_graph_for_same_project_is_rejected(config):
    config['datasets']['drie']['projects'][0] = {'project_code': 'P1', 'graph_name': 'https://ex.org/anders'}
    with pytest.raises(common.ConfigError, match='andere graph_name'):
        common.check_config(config)


def test_dataset_without_projects_is_rejected(config):
    config['datasets']['leeg'] = {'projects': []}
    with pytest.raises(common.ConfigError, match='geen projecten'):
        common.check_config(config)


def test_select_datasets(config):
    assert common.select_datasets(config, 'all') == ['een', 'twee', 'drie']
    assert common.select_datasets(config, ' twee , een') == ['twee', 'een']
    with pytest.raises(common.ConfigError, match='Onbekende dataset'):
        common.select_datasets(config, 'een,vier')


# --- LDV-client ---------------------------------------------------------------------

class Resp:
    def __init__(self, status, data=None, links=None):
        self.status_code, self._data, self.links, self.text = status, data, links or {}, str(data)

    def json(self):
        return self._data


class Http:
    def __init__(self, pages):
        self.pages, self.urls = pages, []

    def get(self, url, headers, timeout):
        self.urls.append(url)
        return self.pages.pop(0)


def test_graph_counts_follows_pagination(config):
    http = Http([Resp(200, [{'graphName': 'a', 'numberOfStatements': 3}], {'next': {'url': 'https://api.example/p2'}}),
                 Resp(200, [{'graphName': 'b', 'numberOfStatements': 4}])])
    ldv = ldv_client.Ldv(config, session=http)
    assert ldv.graph_counts('cht') == {'a': 3, 'b': 4}
    assert http.urls == ['https://api.example/datasets/thesauri/cht/graphs', 'https://api.example/p2']


def test_wait_for_service_times_out(config, monkeypatch):
    ldv = ldv_client.Ldv(config, session=None)
    ldv.sync_timeout, ldv.poll_interval = 0, 0
    monkeypatch.setattr(ldv, 'service', lambda d, n: {'status': 'updating', 'outOfSync': True})
    with pytest.raises(ldv_client.LdvError, match='nog niet klaar'):
        ldv.wait_for_service('cht', 'cht-jena')


def test_wait_for_service_reports_graph_errors(config, monkeypatch):
    ldv = ldv_client.Ldv(config, session=None)
    monkeypatch.setattr(ldv, 'service', lambda d, n: {'status': 'running', 'outOfSync': False, 'numberOfGraphErrors': 2})
    with pytest.raises(ldv_client.LdvError, match='2 graph'):
        ldv.wait_for_service('cht', 'cht-jena')


def test_cli_gets_token_via_environment_and_redacts_it(config, monkeypatch, tmp_path):
    seen = {}

    class Result:
        returncode, stdout, stderr = 1, '', 'Unauthorized for token geheim-token'

    def fake_run(command, capture_output, text, env, timeout):
        seen['command'], seen['env'] = command, env
        return Result()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ldv_client.subprocess, 'run', fake_run)
    ldv = ldv_client.Ldv(config, token='geheim-token', cli='triplydb')
    with pytest.raises(ldv_client.LdvError) as e:
        ldv.import_file('cht', 'cht.nq.gz')
    assert 'geheim-token' not in ' '.join(seen['command'])
    assert seen['env']['TRIPLYDB_TOKEN'] == 'geheim-token'
    assert seen['command'][:2] == ['triplydb', 'import-from-file'] and seen['command'][-1] == 'cht.nq.gz'
    assert '--mode' in seen['command'] and 'overwrite' in seen['command'] and '--url' in seen['command']
    assert 'geheim-token' not in str(e.value) and '***' in str(e.value)
