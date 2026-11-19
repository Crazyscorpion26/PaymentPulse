from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'healthy'

def test_create_and_retrieve_payment():
    created = client.post('/payments', json={'amount': 42.50, 'currency': 'USD', 'destination': 'GB'})
    assert created.status_code == 201
    body = created.json()
    assert body['transaction_id'].startswith('PP-')
    fetched = client.get(f"/payments/{body['transaction_id']}")
    assert fetched.status_code == 200
    assert len(fetched.json()['events']) == 4

def test_callback_failure_scenario():
    response = client.post('/payments', json={'amount': 10, 'simulate': 'callback_failure'})
    assert response.status_code == 201
    assert response.json()['events'][-1]['status'] == 'FAILED'

def test_metrics_endpoint():
    response = client.get('/metrics')
    assert response.status_code == 200
    assert 'paymentpulse_http_requests_total' in response.text
