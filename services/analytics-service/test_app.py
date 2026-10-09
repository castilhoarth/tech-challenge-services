import pytest
import json
import uuid
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError
import sys
import os

# Add the service directory to the path for imports
sys.path.insert(0, os.path.dirname(__file__))

from app import app, process_message, sqs_worker_loop


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for testing"""
    with patch('app.sqs_client') as mock:
        yield mock


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDB client for testing"""
    with patch('app.dynamodb_client') as mock:
        yield mock


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def sample_message():
    """Sample SQS message for testing"""
    return {
        'MessageId': str(uuid.uuid4()),
        'Body': json.dumps({
            'user_id': 'user123',
            'flag_name': 'feature-flag',
            'result': True,
            'timestamp': '2026-08-04T10:00:00Z'
        }),
        'ReceiptHandle': 'receipt-handle-123'
    }


class TestHealthEndpoint:
    """Tests for the health check endpoint"""

    def test_health_returns_ok_status(self, client):
        """Health endpoint should return OK status"""
        # Arrange & Act
        response = client.get('/health')
        
        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'

    def test_health_returns_json_content_type(self, client):
        """Health endpoint should return JSON content type"""
        # Arrange & Act
        response = client.get('/health')
        
        # Assert
        assert response.content_type == 'application/json'


# Pipeline failure scenario:
# Uncomment this test to make the analytics pipeline fail during its pytest step.
# Re-comment it after validating the failure behavior.

#def test_pipeline_failure_scenario():
     #assert False, "Intentional failure for pipeline validation"

class TestProcessMessage:
    """Tests for the process_message function"""

    def test_process_message_successful_flow(self, sample_message, mock_dynamodb_client, mock_sqs_client):
        """Successfully process message and insert to DynamoDB"""
        # Arrange
        mock_dynamodb_client.put_item.return_value = {}
        mock_sqs_client.delete_message.return_value = {}
        
        # Act
        process_message(sample_message)
        
        # Assert
        mock_dynamodb_client.put_item.assert_called_once()
        mock_sqs_client.delete_message.assert_called_once()
        call_args = mock_dynamodb_client.put_item.call_args
        assert call_args[1]['TableName'] is not None
        assert 'Item' in call_args[1]

    def test_process_message_invalid_json_body(self, sample_message, mock_dynamodb_client, mock_sqs_client):
        """Handle invalid JSON in message body gracefully"""
        # Arrange
        sample_message['Body'] = 'invalid json {'
        
        # Act & Assert - should not raise exception
        process_message(sample_message)
        
        # Message should not be deleted on JSON decode error
        mock_sqs_client.delete_message.assert_not_called()
        mock_dynamodb_client.put_item.assert_not_called()

    def test_process_message_dynamodb_client_error(self, sample_message, mock_dynamodb_client, mock_sqs_client):
        """Handle DynamoDB ClientError gracefully"""
        # Arrange
        error = ClientError({'Error': {'Code': 'ItemSizeLimitExceeded'}}, 'PutItem')
        mock_dynamodb_client.put_item.side_effect = error
        
        # Act & Assert - should not raise exception
        process_message(sample_message)
        
        # Message should not be deleted on DynamoDB error
        mock_sqs_client.delete_message.assert_not_called()

    def test_process_message_unexpected_error(self, sample_message, mock_dynamodb_client, mock_sqs_client):
        """Handle unexpected errors gracefully"""
        # Arrange
        mock_dynamodb_client.put_item.side_effect = RuntimeError('Unexpected error')
        
        # Act & Assert - should not raise exception
        process_message(sample_message)
        
        # Message should not be deleted on unexpected error
        mock_sqs_client.delete_message.assert_not_called()

    @pytest.mark.parametrize('user_id,flag_name,result', [
        ('user1', 'flag1', True),
        ('user2', 'flag2', False),
        ('user-special', 'flag-with-dashes', True),
        ('', '', True),  # Edge case: empty strings
    ])
    def test_process_message_various_payloads(self, mock_dynamodb_client, mock_sqs_client, user_id, flag_name, result):
        """Process messages with various payload values"""
        # Arrange
        message = {
            'MessageId': str(uuid.uuid4()),
            'Body': json.dumps({
                'user_id': user_id,
                'flag_name': flag_name,
                'result': result,
                'timestamp': '2026-08-04T10:00:00Z'
            }),
            'ReceiptHandle': 'receipt-handle-test'
        }
        mock_dynamodb_client.put_item.return_value = {}
        mock_sqs_client.delete_message.return_value = {}
        
        # Act
        process_message(message)
        
        # Assert
        mock_dynamodb_client.put_item.assert_called_once()
        mock_sqs_client.delete_message.assert_called_once()


class TestSQSWorkerLoop:
    """Tests for the SQS worker loop"""

    def test_worker_receives_messages(self, mock_sqs_client, mock_dynamodb_client):
        """Worker should receive and process messages from SQS"""
        # Arrange
        messages = [
            {
                'MessageId': str(uuid.uuid4()),
                'Body': json.dumps({
                    'user_id': 'user1',
                    'flag_name': 'flag1',
                    'result': True,
                    'timestamp': '2026-08-04T10:00:00Z'
                }),
                'ReceiptHandle': 'handle1'
            }
        ]
        
        # Make receive_message return messages once, then interrupt the infinite loop.
        mock_sqs_client.receive_message.side_effect = [
            {'Messages': messages},
            KeyboardInterrupt()
        ]
        mock_dynamodb_client.put_item.return_value = {}
        mock_sqs_client.delete_message.return_value = {}
        
        # Act & Assert
        with pytest.raises(KeyboardInterrupt):
            sqs_worker_loop()
        
        mock_dynamodb_client.put_item.assert_called_once()

    def test_worker_handles_empty_response(self, mock_sqs_client):
        """Worker should handle empty message responses"""
        # Arrange
        mock_sqs_client.receive_message.side_effect = [
            {},  # Empty response (no 'Messages' key)
            KeyboardInterrupt()
        ]
        
        # Act & Assert
        with pytest.raises(KeyboardInterrupt):
            sqs_worker_loop()

    def test_worker_handles_client_error(self, mock_sqs_client):
        """Worker should handle ClientError and retry"""
        # Arrange
        error = ClientError({'Error': {'Code': 'ServiceUnavailable'}}, 'ReceiveMessage')
        mock_sqs_client.receive_message.side_effect = [
            error,
            KeyboardInterrupt()
        ]
        
        # Act & Assert
        with patch('app.time.sleep'):
            with pytest.raises(KeyboardInterrupt):
                sqs_worker_loop()

    def test_worker_handles_generic_exception(self, mock_sqs_client):
        """Worker should handle generic exceptions and retry"""
        # Arrange
        mock_sqs_client.receive_message.side_effect = [
            RuntimeError('Generic error'),
            KeyboardInterrupt()
        ]
        
        # Act & Assert
        with patch('app.time.sleep'):
            with pytest.raises(KeyboardInterrupt):
                sqs_worker_loop()


class TestMessageProcessingIntegration:
    """Integration tests for message processing"""

    def test_process_multiple_messages_in_batch(self, mock_sqs_client, mock_dynamodb_client):
        """Process multiple messages in a single batch"""
        # Arrange
        messages = [
            {
                'MessageId': f'msg-{i}',
                'Body': json.dumps({
                    'user_id': f'user{i}',
                    'flag_name': f'flag{i}',
                    'result': i % 2 == 0,
                    'timestamp': '2026-08-04T10:00:00Z'
                }),
                'ReceiptHandle': f'handle-{i}'
            }
            for i in range(3)
        ]
        
        mock_sqs_client.receive_message.side_effect = [
            {'Messages': messages},
            KeyboardInterrupt()
        ]
        mock_dynamodb_client.put_item.return_value = {}
        mock_sqs_client.delete_message.return_value = {}
        
        # Act & Assert
        with pytest.raises(KeyboardInterrupt):
            sqs_worker_loop()
        
        assert mock_dynamodb_client.put_item.call_count == 3

    def test_partial_message_failure_continues_processing(self, mock_sqs_client, mock_dynamodb_client):
        """Worker continues processing even if one message fails"""
        # Arrange
        message_1 = {
            'MessageId': 'msg-1',
            'Body': json.dumps({
                'user_id': 'user1',
                'flag_name': 'flag1',
                'result': True,
                'timestamp': '2026-08-04T10:00:00Z'
            }),
            'ReceiptHandle': 'handle-1'
        }
        
        message_2 = {
            'MessageId': 'msg-2',
            'Body': 'invalid json',
            'ReceiptHandle': 'handle-2'
        }
        
        message_3 = {
            'MessageId': 'msg-3',
            'Body': json.dumps({
                'user_id': 'user3',
                'flag_name': 'flag3',
                'result': False,
                'timestamp': '2026-08-04T10:00:00Z'
            }),
            'ReceiptHandle': 'handle-3'
        }
        
        mock_sqs_client.receive_message.side_effect = [
            {'Messages': [message_1, message_2, message_3]},
            KeyboardInterrupt()
        ]
        mock_dynamodb_client.put_item.return_value = {}
        mock_sqs_client.delete_message.return_value = {}
        
        # Act & Assert
        with pytest.raises(KeyboardInterrupt):
            sqs_worker_loop()
        
        # Should process message 1 and 3 successfully (message 2 fails JSON decode)
        assert mock_dynamodb_client.put_item.call_count == 2
        assert mock_sqs_client.delete_message.call_count == 2
