"""Exportservice: analyse van de TriG, vergelijking met de LDV en de hele run per dataset."""
import json

import pytest

import export_service
import poolparty_client
from conftest import THESAURUS, VOID, FakeLdv, read_nquads, trig


# --- analyse -----------------------------------------------------------------------

def test_analyse_counts_graphs_and_concepts():
    _, graphs, moved = export_service.analyse(trig(concepts=3), THESAURUS, 1)
    assert moved == 0
    assert graphs[THESAURUS] == {'statements': 1 + 3 * 3, 'concepts': 3}
    assert graphs[VOID] == {'statements': 1, 'concepts': 0}


def test_analyse_moves_default_graph_triples_into_thesaurus():
    ds, graphs, moved = export_service.analyse(trig(concepts=3, default_triples=2), THESAURUS, 1)
    assert moved == 2
    assert graphs[THESAURUS]['statements'] == 1 + 3 * 3 + 2
    assert len(ds.default_graph if hasattr(type(ds), 'default_graph') else ds.default_context) == 0


def test_analyse_rejects_missing_thesaurus_graph():
    with pytest.raises(export_service.ProjectError, match='staat niet in de export'):
        export_service.analyse(trig(), 'https://ex.org/andere/thesaurus', 1)


def test_analyse_rejects_too_few_concepts():
    with pytest.raises(export_service.ProjectError, match='skos:Concept'):
        export_service.analyse(trig(concepts=0), THESAURUS, 1)


def test_analyse_rejects_invalid_trig():
    with pytest.raises(export_service.ProjectError, match='geen geldige TriG'):
        export_service.analyse(b'<x> { <a> <b> ', THESAURUS, 1)


# --- vergelijking met de LDV -------------------------------------------------------------

def test_shrink_beyond_limit_blocks_publication():
    graphs = {'g': {'statements': 80}}
    errors, _ = export_service.compare_with_ldv(graphs, {'g': 100}, 10, allow_shrink=False)
    assert errors and 'krimpt van 100 naar 80' in errors[0]
    assert graphs['g']['live_statements'] == 100


def test_shrink_allowed_explicitly_becomes_warning():
    errors, warnings = export_service.compare_with_ldv({'g': {'statements': 80}}, {'g': 100}, 10, allow_shrink=True)
    assert not errors and '--allow-shrink' in warnings[0]


def test_small_shrink_growth_and_untouched_graphs():
    graphs = {'g': {'statements': 95}, 'nieuw': {'statements': 5}}
    errors, warnings = export_service.compare_with_ldv(graphs, {'g': 100, 'oud': 7}, 10, allow_shrink=False)
    assert not errors
    assert any('nieuw' in w and 'is nieuw' in w for w in warnings)
    assert any('oud' in w and 'ongewijzigd' in w for w in warnings)


# --- hele run ------------------------------------------------------------------------

def _fake_exports(monkeypatch, exports):
    calls = []

    def fake(code, config, auth):
        calls.append(code)
        result = exports[code]
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(poolparty_client, 'export_project', fake)
    return calls


def _exports():
    return {'P1': trig('https://ex.org/p1', concepts=4), 'P2': trig('https://ex.org/p2', concepts=2),
            'P3': trig('https://ex.org/p3', concepts=1)}


def test_run_exports_each_project_once_and_builds_datasets(monkeypatch, tmp_path, config):
    calls = _fake_exports(monkeypatch, _exports())
    ldv = FakeLdv(live={'een': {}, 'twee': {}, 'drie': {}})
    manifest = export_service.run(config, ['een', 'twee', 'drie'], 'auth', str(tmp_path), ldv=ldv)

    assert sorted(calls) == ['P1', 'P2', 'P3']          # P1 staat in twee datasets, maar wordt één keer geëxporteerd
    assert manifest['complete'] is True
    twee = manifest['datasets']['twee']
    assert twee['status'] == 'ok'
    assert set(twee['graphs']) == {'https://ex.org/p1/thesaurus', 'https://ex.org/p1/metadata/void',
                                   'https://ex.org/p2/thesaurus', 'https://ex.org/p2/metadata/void'}
    # het bestand bevat precies wat het manifest zegt
    lines = read_nquads(tmp_path / 'twee.nq.gz')
    assert len(lines) == twee['statements'] == sum(g['statements'] for g in twee['graphs'].values())
    assert all(line.rstrip().endswith('> .') for line in lines)          # elke regel heeft een graph
    assert twee['sha256'] == export_service.sha256(str(tmp_path / 'twee.nq.gz'))
    on_disk = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert on_disk['datasets']['twee']['sha256'] == twee['sha256']


def test_failed_project_blocks_only_its_datasets(monkeypatch, tmp_path, config):
    exports = _exports()
    exports['P2'] = poolparty_client.ExportError('na 3 pogingen: HTTP 500: Internal Error')
    _fake_exports(monkeypatch, exports)
    manifest = export_service.run(config, ['een', 'twee', 'drie'], 'auth', str(tmp_path),
                                  ldv=FakeLdv(live={'een': {}, 'twee': {}, 'drie': {}}))

    assert manifest['complete'] is False
    assert manifest['datasets']['een']['status'] == 'ok'
    assert manifest['datasets']['drie']['status'] == 'ok'
    assert manifest['datasets']['twee']['status'] == 'failed'
    assert 'P2' in manifest['datasets']['twee']['errors'][0]
    assert not (tmp_path / 'twee.nq.gz').exists()


def test_shrunken_export_is_not_published(monkeypatch, tmp_path, config):
    _fake_exports(monkeypatch, _exports())
    live = {'een': {'https://ex.org/p1/thesaurus': 1000}, 'twee': {}, 'drie': {}}
    manifest = export_service.run(config, ['een'], 'auth', str(tmp_path), ldv=FakeLdv(live=live))
    assert manifest['datasets']['een']['status'] == 'failed'
    assert 'krimpt' in manifest['datasets']['een']['errors'][0]


def test_unknown_dataset_in_ldv_fails(monkeypatch, tmp_path, config):
    _fake_exports(monkeypatch, _exports())
    manifest = export_service.run(config, ['drie'], 'auth', str(tmp_path), ldv=FakeLdv(live={}))
    assert manifest['datasets']['drie']['status'] == 'failed'
    assert 'vergelijking met de LDV niet mogelijk' in manifest['datasets']['drie']['errors'][0]


def test_unexpected_error_in_one_project_is_contained(monkeypatch, tmp_path, config):
    exports = _exports()
    exports['P3'] = RuntimeError('kapot')
    _fake_exports(monkeypatch, exports)
    manifest = export_service.run(config, ['een', 'drie'], 'auth', str(tmp_path),
                                  ldv=FakeLdv(live={'een': {}, 'drie': {}}))
    assert manifest['datasets']['een']['status'] == 'ok'
    assert 'onverwachte fout' in manifest['projects']['P3']['error']


def test_summary_mentions_errors(monkeypatch, tmp_path, config):
    exports = _exports()
    exports['P3'] = poolparty_client.ExportError('HTTP 404: Project not found')
    _fake_exports(monkeypatch, exports)
    manifest = export_service.run(config, ['een', 'drie'], 'auth', str(tmp_path),
                                  ldv=FakeLdv(live={'een': {}, 'drie': {}}))
    text = export_service.summary_markdown(manifest)
    assert '❌' in text and 'HTTP 404' in text and '✅' in text
