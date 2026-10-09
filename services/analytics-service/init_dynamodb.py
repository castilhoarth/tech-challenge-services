import logging
import os
import time

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

log = logging.getLogger(__name__)


def main():
    endpoint = os.environ["AWS_DYNAMODB_ENDPOINT"]
    table_name = os.environ["AWS_DYNAMODB_TABLE"]
    region = os.environ.get("AWS_REGION", "us-east-1")

    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    for attempt in range(30):
        try:
            dynamodb.list_tables()
            break
        except EndpointConnectionError:
            if attempt == 29:
                raise
            time.sleep(2)

    try:
        dynamodb.describe_table(TableName=table_name)
        log.info("DynamoDB table %s already exists", table_name)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise

        dynamodb.create_table(
            TableName=table_name,
            AttributeDefinitions=[{"AttributeName": "event_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        log.info("Created DynamoDB table %s", table_name)

    dynamodb.get_waiter("table_exists").wait(
        TableName=table_name,
        WaiterConfig={"Delay": 1, "MaxAttempts": 30},
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
