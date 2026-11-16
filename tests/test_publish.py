"""Publicatieservice: alleen goedgekeurde datasets, controle na de import, sync van alle services, rapport-asset."""
import json

import export_service
import poolparty_client
import publish_service
from conftest import FakeLdv, trig


def _export(monkeypatch, tmp_path, config, names=('een', 'twee', 'drie'), fail=()):
    exports = {'P1': trig('https://ex.org/p1'), 'P2': trig('https://ex.org/p2'), 'P3': trig('https://ex.org/p3')}
    for code in fail:
        exports[code] = poolparty_client.ExportError('HTTP 500')

    def fake(code, cfg, auth):
        if isinstance(exports[code], Exception):
            raise exports[code]
        return exports[code]
    monkeypatch.setattr(poolparty_client, 'export_project', fake)
    return export_service.run(config, list(names), 'auth', str(tmp_path),
                              ldv=FakeLdv(live={n: {} for n in names}))


def test_publishes_ok_datasets_and_syncs_all_services(monkeypatch, tmp_path, config):
    manifest = _export(monkeypatch, tmp_path, config, fail=('P3',))
    ldv = FakeLdv(live={'een': {}, 'twee': {}}, services={'een': ['een-jena', 'een-virtuoso'], 'twee': []})
    results = {name: publish_service.publish_dataset(ldv, config, name, manifest['datasets'][name], str(tmp_path), False)
               for name in ('een', 'twee')}

    assert ldv.imports == ['een', 'twee']
    assert all(r['status'] == 'ok' for r in results.values())
    assert ldv.synced == [('een', 'een-jena'), ('een', 'een-virtuoso')]
    assert [a[:2] for a in ldv.assets] == [('een', 'etl-rapport.json'), ('twee', 'etl-rapport.json')]
    report = json.loads(ldv.assets[0][2])
    assert report['status'] == 'ok' and report['graphs']


def test_failed_export_is_never_imported(monkeypatch, tmp_path, config):
    _export(monkeypatch, tmp_path, config, fail=('P3',))
    ldv = FakeLdv(live={'een': {}, 'twee': {}, 'drie': {}})
    monkeypatch.setenv('CACHE_PATH', str(tmp_path))
    monkeypatch.setenv('TRIPLYDB_TOKEN', 'x')
    monkeypatch.setattr(publish_service.ldv_client, 'Ldv', lambda *a, **k: ldv)
    monkeypatch.setattr(publish_service.common, 'load_config', lambda: config)
    assert publish_service.main([]) == 0           # niets mislukt bij de publicatie zelf; 'drie' wordt overgeslagen
    assert 'drie' not in ldv.imports and ldv.imports == ['een', 'twee']


def test_missing_graph_after_import_fails_and_skips_sync(monkeypatch, tmp_path, config):
    manifest = _export(monkeypatch, tmp_path, config, names=('een',))
    ldv = FakeLdv(live={'een': {}}, services={'een': ['een-jena']}, drop_graph='https://ex.org/p1/thesaurus')
    result = publish_service.publish_dataset(ldv, config, 'een', manifest['datasets']['een'], str(tmp_path), False)
    assert result['status'] == 'failed'
    assert 'niet in de LDV' in result['errors'][0]
    assert ldv.synced == []
    assert json.loads(ldv.assets[0][2])['status'] == 'failed'     # het rapport vertelt dat het misging


def test_import_error_fails_dataset(monkeypatch, tmp_path, config):
    manifest = _export(monkeypatch, tmp_path, config, names=('een',))
    ldv = FakeLdv(live={'een': {}}, fail_import={'een'})
    result = publish_service.publish_dataset(ldv, config, 'een', manifest['datasets']['een'], str(tmp_path), False)
    assert result['status'] == 'failed' and 'boom' in result['errors'][0]


def test_checksum_mismatch_blocks_import(monkeypatch, tmp_path, config):
    manifest = _export(monkeypatch, tmp_path, config, names=('een',))
    with open(tmp_path / 'een.nq.gz', 'ab') as f:
        f.write(b'x')
    ldv = FakeLdv(live={'een': {}})
    result = publish_service.publish_dataset(ldv, config, 'een', manifest['datasets']['een'], str(tmp_path), False)
    assert result['status'] == 'failed' and 'checksum' in result['errors'][0]
    assert ldv.imports == []


def test_dry_run_changes_nothing(monkeypatch, tmp_path, config):
    manifest = _export(monkeypatch, tmp_path, config, names=('een',))
    ldv = FakeLdv(live={'een': {}}, services={'een': ['s']})
    result = publish_service.publish_dataset(ldv, config, 'een', manifest['datasets']['een'], str(tmp_path), True)
    assert result['status'] == 'dry-run'
    assert ldv.imports == [] and ldv.synced == [] and ldv.assets == []
