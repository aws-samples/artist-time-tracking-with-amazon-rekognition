# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import os
import json
from datetime import datetime
from decimal import Decimal

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())

dynamodb = boto3.resource('dynamodb')
jobs_table = dynamodb.Table(os.environ['JOBS_TABLE'])


def handler(event, _context):
    video = event['video']
    collection = event['collection']
    bucket = event['bucket']
    job_id = event['job_id']
    duration = event['duration']
    job_id_uuid = job_id.split(':')[-1]
    now = datetime.now()

    logger.info('Recording job')
    jobs_table.put_item(Item=json.loads(json.dumps({
        'job_id': job_id_uuid,
        'collection_id': collection,
        'filepath': video,
        'video_duration': duration * 1000,
        'job_date': now.isoformat()

    }), parse_float=Decimal))

    return {
        'video': video,
        'collection': collection,
        'bucket': bucket,
        'job_id': job_id_uuid,
        'frames': event['frames']
    }
