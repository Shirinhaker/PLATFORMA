import boto3
import pytest


@pytest.fixture
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="auto",
    )
