import pytest
import json
from unittest.mock import MagicMock, patch
from psycopg2.extras import Json
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

    def test_auth_missing_authorization_header(self, client):
        """Request without Authorization header should be rejected"""
        # Arrange & Act
        response = client.get('/rules/test-flag')
        
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
        mock_cur.fetchone.return_value = None
        
        # Act
        response = client.get(
            '/rules/test-flag',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        mock_requests.get.assert_called_once()
        assert response.status_code == 404  # Rule not found, but auth passed

    def test_auth_invalid_key(self, client, mock_requests):
        """Request with invalid key should return 401"""
        # Arrange
        mock_requests.get.return_value.status_code = 401
        
        # Act
        response = client.get(
            '/rules/test-flag',
            headers={'Authorization': 'Bearer invalid_key'}
        )
        
        # Assert
        assert response.status_code == 401

    def test_auth_timeout(self, client, mock_requests):
        """Timeout connecting to auth service should return 504"""
        # Arrange
        mock_requests.get.side_effect = requests.exceptions.Timeout()
        
        # Act
        response = client.get(
            '/rules/test-flag',
            headers={'Authorization': 'Bearer key'}
        )
        
        # Assert
        assert response.status_code == 504

    def test_auth_connection_error(self, client, mock_requests):
        """Connection error to auth service should return 503"""
        # Arrange
        mock_requests.get.side_effect = requests.exceptions.ConnectionError()
        
        # Act
        response = client.get(
            '/rules/test-flag',
            headers={'Authorization': 'Bearer key'}
        )
        
        # Assert
        assert response.status_code == 503


class TestCreateRule:
    """Tests for POST /rules endpoint"""

    def test_create_rule_success(self, client, mock_requests, mock_pool):
        """Successfully create a new rule"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 1,
            'flag_name': 'test-flag',
            'rules': {'type': 'PERCENTAGE', 'value': 50},
            'is_enabled': True
        }
        
        payload = {
            'flag_name': 'test-flag',
            'rules': {'type': 'PERCENTAGE', 'value': 50},
            'is_enabled': True
        }
        
        # Act
        response = client.post(
            '/rules',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['flag_name'] == 'test-flag'

    def test_create_rule_missing_flag_name(self, client, mock_requests):
        """Create rule without flag_name should return 400"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        payload = {'rules': {'type': 'PERCENTAGE', 'value': 50}}
        
        # Act
        response = client.post(
            '/rules',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'obrigatório' in data['error']

    def test_create_rule_missing_rules_object(self, client, mock_requests):
        """Create rule without rules object should return 400"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        payload = {'flag_name': 'test-flag'}
        
        # Act
        response = client.post(
            '/rules',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 400

    def test_create_rule_duplicate_flag(self, client, mock_requests, mock_pool):
        """Create rule for flag that already has a rule should return 409"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = psycopg2.IntegrityError('Duplicate', None, None)
        
        payload = {
            'flag_name': 'existing-flag',
            'rules': {'type': 'PERCENTAGE', 'value': 50}
        }
        
        # Act
        response = client.post(
            '/rules',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'já existe' in data['error']

    def test_create_rule_defaults_enabled_to_true(self, client, mock_requests, mock_pool):
        """Create rule without is_enabled should default to True"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {'id': 1, 'is_enabled': True}
        
        payload = {
            'flag_name': 'new-flag',
            'rules': {'type': 'PERCENTAGE', 'value': 100}
        }
        
        # Act
        response = client.post(
            '/rules',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 201


class TestGetRule:
    """Tests for GET /rules/<flag_name> endpoint"""

    def test_get_rule_success(self, client, mock_requests, mock_pool):
        """Get rule by flag name successfully"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            'id': 1,
            'flag_name': 'test-flag',
            'rules': {'type': 'PERCENTAGE', 'value': 50},
            'is_enabled': True
        }
        
        # Act
        response = client.get(
            '/rules/test-flag',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['flag_name'] == 'test-flag'

    def test_get_rule_not_found(self, client, mock_requests, mock_pool):
        """Get non-existent rule should return 404"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        
        # Act
        response = client.get(
            '/rules/non-existent',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'não encontrada' in data['error']


class TestUpdateRule:
    """Tests for PUT /rules/<flag_name> endpoint"""

    def test_update_rule_success(self, client, mock_requests, mock_pool):
        """Successfully update a rule"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 1
        mock_cur.fetchone.return_value = {
            'id': 1,
            'flag_name': 'test-flag',
            'rules': {'type': 'PERCENTAGE', 'value': 75}
        }
        
        payload = {'rules': {'type': 'PERCENTAGE', 'value': 75}}
        
        # Act
        response = client.put(
            '/rules/test-flag',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 200

    def test_update_rule_not_found(self, client, mock_requests, mock_pool):
        """Update non-existent rule should return 404"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 0
        
        payload = {'is_enabled': False}
        
        # Act
        response = client.put(
            '/rules/non-existent',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 404

    def test_update_rule_empty_body(self, client, mock_requests):
        """Update rule with empty body should return 400"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        
        # Act
        response = client.put(
            '/rules/test-flag',
            data='',
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 400

    def test_update_rule_no_valid_fields(self, client, mock_requests):
        """Update rule with no valid fields should return 400"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        payload = {'invalid_field': 'value'}
        
        # Act
        response = client.put(
            '/rules/test-flag',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 400

    @pytest.mark.parametrize('update_data', [
        {'rules': {'type': 'PERCENTAGE', 'value': 25}},
        {'is_enabled': False},
        {'rules': {'type': 'WHITELIST', 'value': ['user1', 'user2']}, 'is_enabled': True},
    ])
    def test_update_rule_various_fields(self, update_data, client, mock_requests, mock_pool):
        """Update rule with various field combinations"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 1
        mock_cur.fetchone.return_value = {'id': 1, 'flag_name': 'flag'}
        
        # Act
        response = client.put(
            '/rules/test-flag',
            data=json.dumps(update_data),
            content_type='application/json',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 200


class TestDeleteRule:
    """Tests for DELETE /rules/<flag_name> endpoint"""

    def test_delete_rule_success(self, client, mock_requests, mock_pool):
        """Successfully delete a rule"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 1
        
        # Act
        response = client.delete(
            '/rules/test-flag',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 204

    def test_delete_rule_not_found(self, client, mock_requests, mock_pool):
        """Delete non-existent rule should return 404"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.rowcount = 0
        
        # Act
        response = client.delete(
            '/rules/non-existent',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'não encontrada' in data['error']

    def test_delete_rule_database_error(self, client, mock_requests, mock_pool):
        """Handle database error during deletion"""
        # Arrange
        mock_requests.get.return_value.status_code = 200
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = Exception('Database error')
        
        # Act
        response = client.delete(
            '/rules/test-flag',
            headers={'Authorization': 'Bearer valid_key'}
        )
        
        # Assert
        assert response.status_code == 500
