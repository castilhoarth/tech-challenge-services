from unittest.mock import patch

from botocore.exceptions import ClientError

from init_dynamodb import main


@patch.dict(
    "os.environ",
    {
        "AWS_DYNAMODB_ENDPOINT": "http://localhost:8000",
        "AWS_DYNAMODB_TABLE": "ToggleMasterAnalytics",
        "AWS_REGION": "us-east-1",
    },
)
@patch("init_dynamodb.boto3.client")
def test_creates_missing_table_and_waits_until_available(mock_client_factory):
    dynamodb = mock_client_factory.return_value
    dynamodb.describe_table.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}},
        "DescribeTable",
    )

    main()

    dynamodb.create_table.assert_called_once_with(
        TableName="ToggleMasterAnalytics",
        AttributeDefinitions=[{"AttributeName": "event_id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.get_waiter.assert_called_once_with("table_exists")
    dynamodb.get_waiter.return_value.wait.assert_called_once_with(
        TableName="ToggleMasterAnalytics",
        WaiterConfig={"Delay": 1, "MaxAttempts": 30},
    )


@patch.dict(
    "os.environ",
    {
        "AWS_DYNAMODB_ENDPOINT": "http://localhost:8000",
        "AWS_DYNAMODB_TABLE": "ToggleMasterAnalytics",
        "AWS_REGION": "us-east-1",
    },
)
@patch("init_dynamodb.boto3.client")
def test_existing_table_is_not_recreated(mock_client_factory):
    dynamodb = mock_client_factory.return_value

    main()

    dynamodb.create_table.assert_not_called()
    dynamodb.get_waiter.return_value.wait.assert_called_once()
