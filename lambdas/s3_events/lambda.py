# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import os
import re

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'WARNING').upper())

step_functions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
rekognition = boto3.client('rekognition')
collections_table = dynamodb.Table(os.environ['COLLECTIONS_TABLE'])
faces_table = dynamodb.Table(os.environ['FACES_TABLE'])

VIDEO_FILE_FORMAT_PATTERN = re.compile(r'[a-zA-Z0-9_.\-:]+\/episodes\/[a-zA-Z0-9_.\-:]+\.mp4')
FACE_FILE_FORMAT_PATTERN = re.compile(
    r'[a-zA-Z0-9_.\-:]+\/faces\/[a-zA-Z0-9_.\-:]+-[a-zA-Z0-9_.\-:]+\/[a-zA-Z0-9_.\-:]+\.[a-zA-Z0-9_-]{3}')
OBJECT_CREATED_EVENT_TYPE_PATTERN = re.compile(r'ObjectCreated:.*')
OBJECT_REMOVED_EVENT_TYPE_PATTERN = re.compile(r'ObjectRemoved:.*')


def delete_entry_in_face_collection(series_name, object_key):
    logger.info('Getting face_id')
    response = faces_table.query(
        IndexName='filepath_index',
        KeyConditionExpression=Key('filepath').eq(object_key)
    )
    if len(response['Items']) == 1:
        face_id = response['Items'][0]['face_id']

        logger.info('Deleting face')
        rekognition.delete_faces(
            CollectionId=series_name,
            FaceIds=[face_id]
        )
        faces_table.delete_item(Key={'face_id': face_id})
        return face_id


def create_new_entry_in_face_collection(artist_name, artist_role, series_name, bucket, object_key):
    logger.info('Checking collection')
    response = collections_table.get_item(Key={'collection_id': series_name})
    if 'Item' not in response:
        logger.info('Creating collection')

        rekognition.create_collection(CollectionId=series_name)
        collections_table.put_item(Item={'collection_id': series_name})

    logger.info(f'Indexing new face for {artist_name}')
    response = rekognition.index_faces(
        CollectionId=series_name,
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': object_key,
            }
        },
        ExternalImageId=f"{artist_name}-{artist_role}",
        MaxFaces=1
    )

    face_records = response.get('FaceRecords', [])

    if len(face_records) > 0:
        face_id = face_records[0].get('Face', {}).get('FaceId')
        faces_table.put_item(Item={
            'face_id': face_id,
            'name': ' '.join(artist_name.split('_')),
            'role': ' '.join(artist_role.split('_')),
            'series_name': ' '.join(series_name.split('_')),
            'filepath': object_key,
        })
        return face_id


def start_state_machine_execution(bucket, object_key):
    state_machine_arn = os.environ['STATE_MACHINE_ARN']
    logger.info(f'Starting state machine {state_machine_arn}')
    collection = object_key.split('/')[0]
    return step_functions.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps({
            'bucket': bucket,
            'video': object_key,
            'collection': collection
        })
    )


def handler(event, _context):
    if 'Records' in event:
        for record in event['Records']:
            event_type = record['eventName']
            bucket = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']

            logger.info(f'{event_type}, {bucket}, {object_key}')

            # New episode video file (.mp4)
            if VIDEO_FILE_FORMAT_PATTERN.match(object_key) and re.fullmatch(OBJECT_CREATED_EVENT_TYPE_PATTERN,
                                                                            event_type):
                start_state_machine_execution(bucket, object_key)
                return

            # Face collection
            if not FACE_FILE_FORMAT_PATTERN.match(object_key):
                logger.info(f"S3 object key doesn't conform to the required format: {object_key}")
                return {
                    'statusCode': 400,
                    'body': "S3 object key doesn't conform to the required format: {series_name}/faces/{artist_name}-{"
                            "role}/{filename}.{extension}"
                }

            (series_name, folder, artist_name_and_role, filename) = object_key.split('/')
            (artist_name, artist_role) = artist_name_and_role.split('-')

            if re.fullmatch(OBJECT_CREATED_EVENT_TYPE_PATTERN, event_type):
                logger.info('Adding entry to Face Collection')
                face_id = create_new_entry_in_face_collection(
                    artist_name,
                    artist_role,
                    series_name,
                    bucket,
                    object_key,
                )
                if face_id:
                    return {'statusCode': 201, 'body': f'Face {face_id} added to Face Collection {series_name}'}

            if re.fullmatch(OBJECT_REMOVED_EVENT_TYPE_PATTERN, event_type):
                logger.info('Deleting entry from Face Collection')
                face_id = delete_entry_in_face_collection(series_name, object_key)
                if face_id:
                    return {'statusCode': 200, 'body': f'Face {face_id} deleted from Face Collection {series_name}'}
