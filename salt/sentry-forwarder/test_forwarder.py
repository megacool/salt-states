from collections import defaultdict

import pytest
import responses

from sentry_forwarder import app


@responses.activate
def test_forwards_requests(client):
    responses.add(responses.POST, 'https://sentry.io/foo/bar/')
    app.config['SAMPLING_RATE'] = 1
    response = client.post('/foo/bar', data=b'foodata', headers={
        'X-Sentry-Auth': 'test config',
    })
    assert response.status_code == 200
    assert responses.calls[0].request.headers['X-Sentry-Auth'] == 'test config'


@responses.activate
def test_samples(client):
    responses.add(responses.POST, 'https://sentry.io/foo/bar/')

    app.config['SAMPLING_RATE'] = 10
    response_codes = defaultdict(int)
    trials = 200
    for _ in range(trials):
        response = client.post('/foo/bar', data=b'foo')
        response_codes[response.status_code] += 1

    assert len(response_codes) == 2, 'should only have 200 and 202 responses'
    # Parameters chosen for the test to have a success rate of 99.99%
    assert 2 <= response_codes[200] <= 38
    assert trials - response_codes[202] == response_codes[200]


@responses.activate
def test_user_agent_specific_sampling_rate(client):
    ua = 'my-ua/1.0'
    app.config['USER_AGENT_SAMPLING_RATES'] = {
        ua: 2,
    }
    responses.add(responses.POST, 'https://sentry.io/foo/bar/')

    app.config['SAMPLING_RATE'] = 10
    response_codes = defaultdict(int)
    trials = 200
    for _ in range(trials):
        response = client.post('/foo/bar', data=b'foo', headers={
            'User-agent': ua,
        })
        response_codes[response.status_code] += 1

    assert len(response_codes) == 2, 'should only have 200 and 202 responses'
    # Parameters chosen for the test to have a success rate of 99.99%
    assert 72 <= response_codes[200] <= 128
    assert trials - response_codes[202] == response_codes[200]


@responses.activate
def test_reports_error(client):
    app.config['SAMPLING_RATE'] = 1
    response = client.post('/foo/bar')
    assert response.status_code == 503


@responses.activate
def test_compressed_request(client):
    app.config['SAMPLING_RATE'] = 1
    responses.add(responses.POST, 'https://sentry.io/foo/bar/')
    response = client.post('/foo/bar', headers={
        'Content-Encoding': 'gzip',
    }, data=b'\x00')
    assert responses.calls[0].request.headers['Content-Encoding'] == 'gzip'



@responses.activate
def test_query_parameters(client):
    app.config['SAMPLING_RATE'] = 1
    responses.add(responses.POST, 'https://sentry.io/foo/bar/')
    response = client.post('/foo/bar?auth=foo')
    assert responses.calls[0].request.url == 'https://sentry.io/foo/bar/?auth=foo'


def test_root(client):
    assert client.get('/').status_code == 200


@pytest.fixture
def client():
    return app.test_client()
