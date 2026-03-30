"""
SQS helper module.
Provides queue creation/lookup and methods to send analytics processing
messages asynchronously so API responses are never blocked.
Credentials are loaded from environment variables — never hardcoded.
"""
import json
import logging

import boto3
from botocore.exceptions import ClientError

from config import Config

logger = logging.getLogger(__name__)

# Cached queue URL to avoid repeated DescribeQueue calls
_QUEUE_URL: str | None = None


def _get_sqs_client():
    """Return a boto3 SQS client using env-based credentials."""
    return boto3.client(
        'sqs',
        region_name=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )


def ensure_queue() -> str:
    """
    Get the URL of the analytics SQS queue, creating it if it does not exist.

    Returns:
        Queue URL string.
    """
    global _QUEUE_URL
    if _QUEUE_URL:
        return _QUEUE_URL

    sqs = _get_sqs_client()
    queue_name = Config.SQS_QUEUE_NAME

    try:
        response = sqs.get_queue_url(QueueName=queue_name)
        _QUEUE_URL = response['QueueUrl']
        logger.info('SQS queue found: %s', _QUEUE_URL)
    except ClientError as exc:
        code = exc.response['Error']['Code']
        if code == 'AWS.SimpleQueueService.NonExistentQueue':
            create_resp = sqs.create_queue(
                QueueName=queue_name,
                Attributes={
                    'MessageRetentionPeriod': '86400',   # 1 day
                    'VisibilityTimeout': '60',
                },
            )
            _QUEUE_URL = create_resp['QueueUrl']
            logger.info('SQS queue created: %s', _QUEUE_URL)
        else:
            logger.error('SQS ensure_queue error: %s', exc)
            raise

    return _QUEUE_URL


def send_analytics_job(user_id: str, date: str, event_type: str = 'record_upsert') -> bool:
    """
    Send an analytics processing job to SQS.
    The Lambda worker will pick this up and compute/store analytics.

    Args:
        user_id: The user's email address.
        date: Health record date (YYYY-MM-DD).
        event_type: Type of event triggering the job (record_upsert / record_delete).
    Returns:
        True if message sent successfully, False otherwise.
    """
    try:
        queue_url = ensure_queue()
        sqs = _get_sqs_client()
        message = {
            'user_id': user_id,
            'date': date,
            'event_type': event_type,
        }
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
        )
        logger.info('Analytics job queued for user=%s date=%s', user_id, date)
        return True
    except Exception as exc:
        logger.error('send_analytics_job error: %s', exc)
        return False


def receive_messages(max_messages: int = 10) -> list:
    """
    Receive and delete messages from the analytics queue.
    Used by the local worker and the Lambda handler.

    Args:
        max_messages: Maximum number of messages to retrieve (1-10).
    Returns:
        List of parsed message body dicts.
    """
    try:
        queue_url = ensure_queue()
        sqs = _get_sqs_client()
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=min(max_messages, 10),
            WaitTimeSeconds=5,
        )
        messages = response.get('Messages', [])
        results = []
        for msg in messages:
            body = json.loads(msg['Body'])
            results.append(body)
            # Delete the message after reading
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=msg['ReceiptHandle'],
            )
        return results
    except Exception as exc:
        logger.error('receive_messages error: %s', exc)
        return []
