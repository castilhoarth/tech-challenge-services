import pytest
import json
from unittest.mock import MagicMock, patch
import psycopg2
import requests
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import app


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def mock_pool():
    """Mock database connection pool"""
    with patch('app.pool') as mock:
        yield mock


@pytest.fixture
def mock_requests():
    """Mock requests library for auth service calls"""
    with patch('app.requests') as mock:
        yield mock


class TestHealthEndpoint:
    """Tests for the health check endpoint"""

    def test_health_returns_ok(self, client):
        """Health endpoint should return OK status"""
        # Arrange & Act
        response = client.get('/health')
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestAuthMiddleware:
    """Tests for the require_auth middleware"""

    def test_auth_missing_authorization_header(self, client, mock_requests):
        """Request without Authorization header should be rejected"""
        # Arrange & Act
        response = client.get('/flags')
        
        # Assert
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Authorization header obrigatório' in data['error']

    def test_auth_valid_key(self, client, mock_requests, mock_pool):
        """Request with valid authorization header should pass"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        
        # Act
        response = client.get('/flags', headers={'Authorization': 'Bearer valid_key'})
        
        # Assert
        mock_requests.get.assert_called_once()
        assert response.status_code == 200

    def test_auth_invalid_key(self, client, mock_requests):
        """Request with invalid key should return 401"""
        # Arrange
        mock_requests.get.return_value.status_code = 401
        
        # Act
        response = client.get('/flags', headers={'Authorization': 'Bearer invalid_key'})
        
        # Assert
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'inválida' in data['error']

    def test_auth_timeout(self, client, mock_requests):
        """Timeout connecting to auth service should return 504"""
        # Arrange
        mock_requests.get.side_effect = requests.exceptions.Timeout()
        
        # Act
        response = client.get('/flags', headers={'Authorization': 'Bearer key'})
        
        # Assert
        assert response.status_code == 504

    def test_auth_service_unavailable(self, client, mock_requests):
        """Connection error to auth service should return 503"""
        # Arrange
        mock_requests.get.side_effect = requests.exceptions.ConnectionError()
        
        # Act
        response = client.get('/flags', headers={'Authorization': 'Bearer key'})
        
        # Assert
        assert response.status_code == 503


class TestCreateFlag:
    """Tests for POST /flags endpoint"""

    def test_create_flag_success(self, client, mock_requests, mock_pool):
        """Successfully create a new flag"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 1,
            'name': 'test-flag',
            'description': 'Test flag',
            'is_enabled': True
        }
        
        payload = {
            'name': 'test-flag',
            'description': 'Test flag',
            'is_enabled': True
        }
        
        # Act
        response = client.post(
            '/flags',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['name'] == 'test-flag'

    def test_create_flag_missing_name(self, client, mock_requests):
        """Create flag without name should return 400"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        payload = {'description': 'Test flag'}
        
        # Act
        response = client.post(
            '/flags',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 400

    def test_create_flag_duplicate_name(self, client, mock_requests, mock_pool):
        """Create flag with duplicate name should return 409"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = psycopg2.IntegrityError('Duplicate', None, None)
        
        payload = {'name': 'existing-flag', 'description': 'Test'}
        
        # Act
        response = client.post(
            '/flags',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'já existe' in data['error']

    def test_create_flag_defaults_enabled_to_false(self, client, mock_requests, mock_pool):
        """Create flag without is_enabled should default to False"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'name': 'flag', 'is_enabled': False}
        
        payload = {'name': 'new-flag'}
        
        # Act
        response = client.post(
            '/flags',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 201


class TestGetFlags:
    """Tests for GET /flags endpoint"""

    def test_get_flags_success(self, client, mock_requests, mock_pool):
        """Get all flags successfully"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {'id': 1, 'name': 'flag1', 'is_enabled': True},
            {'id': 2, 'name': 'flag2', 'is_enabled': False}
        ]
        
        # Act
        response = client.get('/flags', headers={'Authorization': 'Bearer valid_key'})
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2

    def test_get_flags_empty_list(self, client, mock_requests, mock_pool):
        """Get flags when none exist"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        
        # Act
        response = client.get('/flags', headers={'Authorization': 'Bearer valid_key'})
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 0


class TestGetFlagByName:
    """Tests for GET /flags/<name> endpoint"""

    def test_get_flag_by_name_success(self, client, mock_requests, mock_pool):
        """Get flag by name successfully"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 1,
            'name': 'test-flag',
            'description': 'Test flag',
            'is_enabled': True
        }
        
        # Act
        response = client.get(
            '/flags/test-flag',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == 'test-flag'

    def test_get_flag_not_found(self, client, mock_requests, mock_pool):
        """Get non-existent flag should return 404"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        
        # Act
        response = client.get(
            '/flags/non-existent',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 404


class TestUpdateFlag:
    """Tests for PUT /flags/<name> endpoint"""

    def test_update_flag_success(self, client, mock_requests, mock_pool):
        """Successfully update a flag"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 1
        mock_cur.fetchone.return_value = {
            'id': 1,
            'name': 'test-flag',
            'is_enabled': False
        }
        
        payload = {'is_enabled': False}
        
        # Act
        response = client.put(
            '/flags/test-flag',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 200

    def test_update_flag_not_found(self, client, mock_requests, mock_pool):
        """Update non-existent flag should return 404"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 0
        
        payload = {'is_enabled': True}
        
        # Act
        response = client.put(
            '/flags/non-existent',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 404

    def test_update_flag_empty_body(self, client, mock_requests):
        """Update flag with empty body should return 400"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        
        # Act
        response = client.put(
            '/flags/test-flag',
            data='',
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 400

    def test_update_flag_no_valid_fields(self, client, mock_requests):
        """Update flag with no valid fields should return 400"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        payload = {'invalid_field': 'value'}
        
        # Act
        response = client.put(
            '/flags/test-flag',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 400

    @pytest.mark.parametrize('update_data', [
        {'description': 'Updated description'},
        {'is_enabled': True},
        {'description': 'New desc', 'is_enabled': False},
    ])
    def test_update_flag_various_fields(self, update_data, client, mock_requests, mock_pool):
        """Update flag with various field combinations"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 1
        mock_cur.fetchone.return_value = {'id': 1, 'name': 'flag'}
        
        # Act
        response = client.put(
            '/flags/test-flag',
            data=json.dumps(update_data),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 200
