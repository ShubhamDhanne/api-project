#!/usr/bin/env python3
"""
provision_aws.py — Create all required AWS resources for HealthTrack.

Run once before the first deployment:
    python deploy/provision_aws.py

Creates:
  - DynamoDB tables: HealthUsers, HealthRecords
  - SQS queue: health-analytics-queue
  - Lambda function: health-analytics-worker (from lambda/lambda_function.py)
  - SQS → Lambda event source mapping

Credentials are read from the .env file in the project root.
"""
import json
import os
import sys
import zipfile
import io
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

REGION        = os.getenv('AWS_REGION', 'eu-north-1')
ACCOUNT_ID    = os.getenv('AWS_ACCOUNT_ID', '')
KEY_ID        = os.getenv('AWS_ACCESS_KEY_ID')
SECRET        = os.getenv('AWS_SECRET_ACCESS_KEY')
QUEUE_NAME    = 'health-analytics-queue'
LAMBDA_NAME   = 'health-analytics-worker'
LAMBDA_ROLE   = f'arn:aws:iam::{ACCOUNT_ID}:role/HealthAnalyticsLambdaRole'

SESSION = boto3.Session(
    aws_access_key_id=KEY_ID,
    aws_secret_access_key=SECRET,
    region_name=REGION,
)


def ensure_dynamodb_tables():
    """Create HealthUsers and HealthRecords tables if they do not exist."""
    ddb = SESSION.resource('dynamodb')

    tables = {
        'HealthUsers': [
            {'AttributeName': 'user_id', 'KeyType': 'HASH'}
        ],
        'HealthRecords': [
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'date', 'KeyType': 'RANGE'},
        ],
    }
    attr_defs = {
        'HealthUsers': [{'AttributeName': 'user_id', 'AttributeType': 'S'}],
        'HealthRecords': [
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'date', 'AttributeType': 'S'},
        ],
    }

    for name, key_schema in tables.items():
        try:
            tbl = ddb.create_table(
                TableName=name,
                KeySchema=key_schema,
                AttributeDefinitions=attr_defs[name],
                BillingMode='PAY_PER_REQUEST',
            )
            tbl.wait_until_exists()
            log.info('Created DynamoDB table: %s', name)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                log.info('Table already exists: %s', name)
            else:
                raise


def ensure_sqs_queue():
    """Create the analytics SQS queue if it does not exist."""
    sqs = SESSION.client('sqs')
    try:
        r = sqs.get_queue_url(QueueName=QUEUE_NAME)
        log.info('SQS queue exists: %s', r['QueueUrl'])
        return r['QueueUrl']
    except ClientError:
        r = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes={'MessageRetentionPeriod': '86400', 'VisibilityTimeout': '60'},
        )
        log.info('Created SQS queue: %s', r['QueueUrl'])
        return r['QueueUrl']


def get_queue_arn(queue_url: str) -> str:
    """Get the ARN of an SQS queue from its URL."""
    sqs = SESSION.client('sqs')
    attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['QueueArn'])
    return attrs['Attributes']['QueueArn']


def create_lambda_package() -> bytes:
    """Package lambda/lambda_function.py into a ZIP for deployment."""
    lambda_src = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'lambda_function.py')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(lambda_src, 'lambda_function.py')
    return buf.getvalue()


def ensure_lambda(queue_arn: str):
    """Create or update the Lambda function and connect it to SQS."""
    lmb = SESSION.client('lambda')
    code = create_lambda_package()

    env_vars = {
        'AWS_REGION': REGION,
        'CALORIE_NINJAS_API_KEY': os.getenv('CALORIE_NINJAS_API_KEY', ''),
    }

    try:
        lmb.get_function(FunctionName=LAMBDA_NAME)
        lmb.update_function_code(FunctionName=LAMBDA_NAME, ZipFile=code)
        lmb.update_function_configuration(
            FunctionName=LAMBDA_NAME,
            Environment={'Variables': env_vars},
        )
        log.info('Updated Lambda function: %s', LAMBDA_NAME)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            lmb.create_function(
                FunctionName=LAMBDA_NAME,
                Runtime='python3.11',
                Role=LAMBDA_ROLE,
                Handler='lambda_function.lambda_handler',
                Code={'ZipFile': code},
                Timeout=60,
                MemorySize=256,
                Environment={'Variables': env_vars},
            )
            log.info('Created Lambda function: %s', LAMBDA_NAME)
        else:
            log.error('Lambda creation failed: %s', e)
            log.warning('Skipping Lambda creation. Create the IAM role first.')
            return

    # Create SQS trigger (idempotent)
    try:
        lmb.create_event_source_mapping(
            EventSourceArn=queue_arn,
            FunctionName=LAMBDA_NAME,
            BatchSize=10,
            FunctionResponseTypes=['ReportBatchItemFailures'],
        )
        log.info('SQS → Lambda event source mapping created.')
    except ClientError as e:
        if 'exists' in str(e).lower() or e.response['Error']['Code'] == 'ResourceConflictException':
            log.info('SQS trigger already exists.')
        else:
            log.warning('Could not create SQS trigger: %s', e)


if __name__ == '__main__':
    log.info('Provisioning AWS resources for HealthTrack...')
    ensure_dynamodb_tables()
    queue_url = ensure_sqs_queue()
    queue_arn = get_queue_arn(queue_url)
    ensure_lambda(queue_arn)
    log.info('All resources provisioned.')
