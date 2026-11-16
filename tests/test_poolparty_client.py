"""PoolParty-client: retries, foutpagina's, en het geheim blijft uit de meldingen."""
import pytest
import requests

import poolparty_client
from conftest import trig

SECRET = 'Basic c2VjcmV0OnNlY3JldA=='


class Response:
    def __init__(self, status, body=b''):
        self.status_code, self.content = status, body


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def post(self, url, headers, json, timeout):
        self.calls.append((url, headers, json, timeout))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_export_success_sends_request(config):
    session = Session(Response(200, trig()))
    body = poolparty_client.export_project('P1', config, SECRET, session)
    assert body.startswith(b'@prefix')
    url, headers, payload, timeout = session.calls[0]
    assert url == 'https://pp.example/api/projects/P1/export'
    assert headers['Authorization'] == SECRET
    assert payload['format'] == 'TriG' and payload['modules'] == ['concepts', 'void']
    assert timeout == 5


def test_retries_temporary_errors(config):
    session = Session(Response(503, b'busy'), requests.ConnectionError('reset'), Response(200, trig()))
    assert poolparty_client.export_project('P1', config, SECRET, session)
    assert len(session.calls) == 3


def test_gives_up_after_retries_with_readable_reason(config):
    html = b'<!DOCTYPE html><html><head><title>Graph Modeling - Internal Error</title></head></html>'
    session = Session(*[Response(500, html)] * 3)
    with pytest.raises(poolparty_client.ExportError) as e:
        poolparty_client.export_project('P1', config, SECRET, session)
    assert 'na 3 pogingen' in str(e.value) and 'Internal Error' in str(e.value)
    assert SECRET not in str(e.value)


def test_client_errors_are_not_retried(config):
    session = Session(Response(404, b'Project not found'), Response(200, trig()))
    with pytest.raises(poolparty_client.ExportError, match='HTTP 404'):
        poolparty_client.export_project('P1', config, SECRET, session)
    assert len(session.calls) == 1


@pytest.mark.parametrize('body', [b'', b'   \n', b'<!DOCTYPE html><html><title>Login</title></html>'])
def test_rejects_empty_or_html_200(config, body):
    with pytest.raises(poolparty_client.ExportError):
        poolparty_client.export_project('P1', config, SECRET, Session(Response(200, body)))
