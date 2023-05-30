# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import os
import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())

rekognition = boto3.client('rekognition')


def start_segment_detection(s3_bucket, s3_key):
    confidence = float(os.environ['MIN_SEGMENT_CONFIDENCE'])
    logger.info(f'Starting Rekognition segment detection (shot) with confidence {confidence}')
    response = rekognition.start_segment_detection(
        Video={'S3Object': {'Bucket': s3_bucket, 'Name': s3_key}},
        SegmentTypes=['SHOT'],
        Filters={
            'ShotFilter': {'MinSegmentConfidence': confidence},
        }
    )
    rekognition_job_id = response['JobId']
    logger.info(f'Rekognition job id: {rekognition_job_id}')
    return rekognition_job_id


def handler(event, _context):
    return {
        'rekognition_job_id': start_segment_detection(event['bucket'], event['video']),
        'video': event['video'],
        'bucket': event['bucket'],
        'collection': event['collection'],
        'job_id': event['job_id'],
    }
