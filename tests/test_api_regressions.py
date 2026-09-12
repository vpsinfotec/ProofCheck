import asyncio
from dataclasses import replace
import io
import threading

import httpx
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from proofcheck.web import app as module, auth
from proofcheck.web.app import app


def uploads(excel_path, pdf_path):
    return {'excel': ('data.xlsx', open(excel_path, 'rb').read()),
            'pdf': ('doc.pdf', open(pdf_path, 'rb').read())}


@pytest.mark.parametrize('field,value', [('header_row','0'),('fuzzy_threshold','101'),
    ('ocr_dpi','10000'),('ocr_lang','eng --tessdata-dir /tmp'),('all_columns','perhaps'),('ocr_psm','9')])
def test_invalid_config_rejected(excel_path, pdf_path, field, value):
    with TestClient(app) as client:
        response = client.post('/api/check', files=uploads(excel_path,pdf_path), data={'columns':'Name', field:value})
    assert response.status_code == 422
    assert isinstance(response.json()['error'], str)


def test_json_column_names_support_commas(tmp_path, pdf_path):
    wb = Workbook(); wb.active.append(['Last, First']); wb.active.append(['Priya Nair'])
    buffer = io.BytesIO(); wb.save(buffer)
    with TestClient(app) as client:
        response = client.post('/api/check', files={'excel': ('data.xlsx', buffer.getvalue()), 'pdf': ('doc.pdf', open(pdf_path,'rb').read())}, data={'columns_json': '["Last, First"]'})
    assert response.status_code == 200
    assert response.json()['summary']['exact'] == 1
    assert response.json()['timings']['match'] >= 0


def test_empty_file_rejected_and_no_temp_leak(tmp_path, monkeypatch, pdf_path):
    monkeypatch.setattr(module.tempfile, 'tempdir', str(tmp_path))
    with TestClient(app) as client:
        response = client.post('/api/check', files={'excel': ('empty.xlsx', b''), 'pdf': ('doc.pdf', open(pdf_path,'rb').read())}, data={'columns':'Name'})
    assert response.status_code == 400
    assert not list(tmp_path.glob('tmp*.xlsx'))


def test_reports_require_owner_and_logout_hides_them(excel_path,pdf_path,monkeypatch):
    monkeypatch.setenv('PROOFCHECK_AUTH', 'on')
    auth.register_user('alice', 'password123')
    auth.register_user('bob', 'password123')
    with TestClient(app) as client:
        client.post('/api/auth/login', json={'username':'alice','password':'password123'})
        result = client.post('/api/check', files=uploads(excel_path,pdf_path), data={'columns':'Name'}).json()
        url = result['report_urls']['html']
        assert client.get(url).status_code == 200
        client.post('/api/auth/logout')
        assert client.get(url).status_code == 401
        client.post('/api/auth/login',json={'username':'bob','password':'password123'})
        assert client.get(url).status_code == 404


@pytest.mark.parametrize('token', ['é.foo', 'a.ø', 'a.!', 'a.' + 'x' * 5000])
def test_malformed_tokens_do_not_crash(token):
    assert auth.verify_token(token) is None


def test_registration_trims_token_identity(monkeypatch):
    monkeypatch.setenv('PROOFCHECK_AUTH','on'); monkeypatch.setenv('PROOFCHECK_ALLOW_REGISTER','on')
    with TestClient(app) as client:
        result = client.post('/api/auth/register',json={'username':'  alice  ','password':'password123'})
        assert result.status_code == 201 and result.json()['username'] == 'alice'
        assert client.get('/api/auth/me').json()['username'] == 'alice'


def test_internal_error_is_generic(excel_path,pdf_path,monkeypatch):
    def fail(*a,**kw): raise RuntimeError('PRIVATE /secret/server/path')
    monkeypatch.setattr(module,'pipeline_run',fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        result = client.post('/api/check', files=uploads(excel_path,pdf_path),data={'columns':'Name'})
    assert result.status_code == 500 and 'PRIVATE' not in result.text


def test_long_check_keeps_health_responsive_and_rejects_excess(excel_path,pdf_path,monkeypatch):
    entered = threading.Event(); release = threading.Event()
    original = module.pipeline_run
    def slow(config):
        entered.set()
        assert release.wait(5)
        return original(config)
    monkeypatch.setattr(module, 'pipeline_run', slow)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            first = asyncio.create_task(client.post('/api/check',files=uploads(excel_path,pdf_path),data={'columns':'Name'}))
            assert await asyncio.to_thread(entered.wait, 3)
            try:
                health = await asyncio.wait_for(client.get('/api/health'), timeout=1)
                assert health.status_code == 200
            finally:
                release.set()
            assert (await first).status_code == 200
    asyncio.run(exercise())


def test_declared_oversize_rejected_before_parser():
    with TestClient(app) as client:
        result = client.post('/api/check', content=b'', headers={'Content-Length':str(module.MAX_UPLOAD_BYTES * 2 + 2 * 1024 * 1024)})
    assert result.status_code == 413


def test_second_upload_failure_cleans_first(excel_path,monkeypatch,tmp_path):
    monkeypatch.setattr(module.tempfile,'tempdir',str(tmp_path))
    monkeypatch.setattr(module,'MAX_UPLOAD_BYTES',10000)
    with TestClient(app) as client:
        result=client.post('/api/check', files={'excel':('data.xlsx',open(excel_path,'rb').read()),'pdf':('big.pdf',b'x'*10001)},data={'columns':'Name'})
    assert result.status_code == 413 and not list(tmp_path.glob('tmp*.xlsx')) and not list(tmp_path.glob('tmp*.pdf'))


def test_chunked_oversize_is_413(monkeypatch):
    monkeypatch.setattr(module, 'MAX_UPLOAD_BYTES', 10)
    async def exercise():
        async def chunks():
            yield b'--x\r\nContent-Disposition: form-data; name="excel"; filename="huge.xlsx"\r\n\r\n'
            for _ in range(3):
                yield b'x' * (512 * 1024)
            yield b'\r\n--x--\r\n'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            result = await client.post('/api/check',content=chunks(),headers={'Content-Type':'multipart/form-data; boundary=x'})
            assert result.status_code == 413
    asyncio.run(exercise())


def test_capacity_rejected_before_reading_body():
    from proofcheck.web.middleware import ResourceLimitsMiddleware
    called = []
    async def inner(scope, receive, send): called.append('inner')
    middleware = ResourceLimitsMiddleware(inner, upload_limit=lambda: 100, max_checks=1)
    middleware.slots.acquire()
    async def exercise():
        messages=[]
        async def receive(): raise AssertionError('Busy request must not read uploads')
        async def send(message): messages.append(message)
        await middleware({'type':'http','method':'POST','path':'/api/check','headers':[], 'query_string':b'', 'server':('test',80),'scheme':'http'},receive,send)
        assert messages[0]['status'] == 429 and not called
    try: asyncio.run(exercise())
    finally: middleware.slots.release()
