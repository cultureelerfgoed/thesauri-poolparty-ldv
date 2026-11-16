"""Exporteer een PoolParty-project als TriG, met time-out, retries en controle op foutpagina's.

De Authorization-header komt uit POOLPARTY_AUTH en verschijnt nooit in een log of foutmelding.
"""
import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

# tijdelijke fouten: opnieuw proberen. Andere 4xx (verkeerde code, geen rechten) niet: dat lost zichzelf niet op.
RETRY_STATUS = {429, 500, 502, 503, 504}
_TITLE = re.compile(rb'<title>\s*(.*?)\s*</title>', re.I | re.S)


class ExportError(Exception):
    """De export van een project is mislukt; de reden staat in de melding."""


def _describe(response) -> str:
    """Korte, leesbare reden: bij een HTML-foutpagina de titel, anders het begin van de tekst."""
    body = response.content or b''
    title = _TITLE.search(body[:5000])
    text = title.group(1) if title else body[:300]
    text = re.sub(rb'\s+', b' ', text).decode('utf-8', 'replace').strip()
    return f'HTTP {response.status_code}' + (f': {text}' if text else '')


def looks_like_html(body: bytes) -> bool:
    head = body[:500].lstrip().lower()
    return head.startswith((b'<!doctype html', b'<html'))


def export_project(project_code: str, config: dict, auth: str, session=None) -> bytes:
    """Geef de TriG-export van één project terug, of gooi ExportError."""
    pp = config['poolparty']
    url = pp['export_url'].format(project=project_code)
    headers = {'Authorization': auth, 'Content-Type': 'application/json', 'Accept': '*/*'}
    payload = {'prettyPrint': False, 'format': 'TriG', 'modules': list(pp['modules'])}
    retries, backoff, timeout = int(pp.get('retries', 4)), float(pp.get('backoff', 15)), float(pp.get('timeout', 900))
    http = session or requests

    for attempt in range(1, retries + 1):
        reason = None
        try:
            response = http.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as e:
            reason = f'{type(e).__name__}: {e}'
        else:
            if response.status_code == 200:
                body = response.content or b''
                if not body.strip():
                    raise ExportError('PoolParty gaf een lege export (HTTP 200 zonder inhoud).')
                if looks_like_html(body):
                    raise ExportError(f'PoolParty gaf een HTML-pagina in plaats van TriG: {_describe(response)}')
                return body
            if response.status_code not in RETRY_STATUS:
                raise ExportError(_describe(response))
            reason = _describe(response)
        if attempt == retries:
            raise ExportError(f'na {retries} pogingen: {reason}')
        wait = backoff * attempt
        logger.warning('Export %s, poging %d/%d mislukt (%s); %.0fs wachten.', project_code, attempt, retries, reason, wait)
        time.sleep(wait)
    raise ExportError('geen pogingen gedaan (retries < 1)')
