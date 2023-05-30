# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import os
import tempfile

import boto3
import cv2

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())

rekognition = boto3.client('rekognition')
s3 = boto3.client('s3')


class ResourcePending(Exception):
    pass


class ResourceFailed(Exception):
    pass


def raise_if_not_succeeded(job_status):
    # Job status valid values: IN_PROGRESS | SUCCEEDED | FAILED
    logger.info(f'Job status: {job_status}')
    if job_status == 'IN_PROGRESS':
        raise ResourcePending
    if job_status == 'FAILED':
        raise ResourceFailed


def get_timestamps(job_id):
    logger.info(f'Getting Rekognition segments')
    next_t = ''
    finished = False
    timestamps = []
    while not finished:
        response = rekognition.get_segment_detection(JobId=job_id, NextToken=next_t)
        for segment in response['Segments']:
            if segment['Type'] == 'SHOT':
                timestamps.append(segment['StartTimestampMillis'])
        if 'NextToken' in response:
            next_t = response['NextToken']
        else:
            finished = True
    return timestamps


def extract_frames(timestamps, s3_bucket, video, collection, job_id):
    frames = []
    episode_name = video.split('/')[-1].replace('.mp4', '')
    job_id_uuid = job_id.split(':')[-1]
    with tempfile.NamedTemporaryFile() as temporary_file:
        logger.info(f'Downloading video file')
        s3.download_fileobj(s3_bucket, video, temporary_file)
        cap = cv2.VideoCapture(temporary_file.name)
        frame_num = 1
        while cap.isOpened():
            frame_exists, frame = cap.read()
            if frame_exists:
                frame_timestamp = int(cap.get(cv2.CAP_PROP_POS_MSEC))
                if frame_timestamp in timestamps:
                    logging.info(f'Saving frame {frame_num} ({frame_timestamp})')
                    jpg_image = cv2.imencode('.jpg', frame)[1].tobytes()
                    s3_key = f'{collection}/results/{episode_name}/{job_id_uuid}/frames/{frame_timestamp}.jpg'
                    s3.put_object(Bucket=s3_bucket, Key=s3_key, Body=jpg_image)
                    frames.append(s3_key)
                    frame_num += 1
            else:
                break
        cap.release()
    return frames


def handler(event, _context):
    response = rekognition.get_segment_detection(JobId=event['rekognition_job_id'])
    raise_if_not_succeeded(response['JobStatus'])
    duration = response['VideoMetadata'][0]['DurationMillis']
    timestamps = get_timestamps(event['rekognition_job_id'])
    frames = extract_frames(timestamps, event['bucket'], event['video'], event['collection'], event['job_id'])
    return {
        'frames': frames,
        'video': event['video'],
        'bucket': event['bucket'],
        'collection': event['collection'],
        'job_id': event['job_id'],
        'duration': duration
    }
