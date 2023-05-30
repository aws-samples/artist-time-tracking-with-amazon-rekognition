# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import base64
import json
import logging
import os
import tempfile
from decimal import Decimal
from io import BytesIO

import boto3
from PIL import Image
from PIL import ImageFile

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO').upper())
ImageFile.LOAD_TRUNCATED_IMAGES = True

LABEL_MINIMUM_CONFIDENCE_LEVEL = os.environ['LABEL_MINIMUM_CONFIDENCE_LEVEL']
FACE_MINIMUM_CONFIDENCE_LEVEL = os.environ['FACE_MINIMUM_CONFIDENCE_LEVEL']

s3 = boto3.client('s3')
rek = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')
results_table = dynamodb.Table(os.environ['RESULTS_TABLE'])


def is_face_in_entries(entries, face):
    for entry in entries:
        if entry['name'] == face['name']:
            return True
    return False


def detect_persons(bucket, key):
    response = rek.detect_labels(
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': key,
            }
        },
        MinConfidence=int(LABEL_MINIMUM_CONFIDENCE_LEVEL),
    )
    logger.info(f"labels: {json.dumps(response['Labels'])}")

    person_label = [label for label in response['Labels'] if label['Name'] == 'Person']

    persons = []
    for label in person_label:
        for instance in label['Instances']:
            persons.append(instance)

    return persons


def detect_faces(bucket, key):
    response = rek.detect_faces(
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': key,
            }
        },
    )

    faces = []
    if 'FaceDetails' in response and len(response['FaceDetails']) > 0:
        faces = [face['BoundingBox'] for face in response['FaceDetails']]

    return faces


def identify_faces(bucket, frame, faces, collection):
    identified_persons = []

    with tempfile.NamedTemporaryFile() as temporary_file:
        s3.download_fileobj(bucket, frame, temporary_file)

        with Image.open(temporary_file.name) as im:
            (total_width, total_height) = im.size

            for face in faces:
                left = face['Left'] * total_width
                top = face['Top'] * total_height
                right = left + (face['Width'] * total_width)
                bottom = top + (face['Height'] * total_height)

                crop = im.crop((left, top, right, bottom))

                buffered = BytesIO()
                crop.save(buffered, format="PNG")
                b64_encoded = base64.b64encode(buffered.getvalue())

                try:
                    response = rek.search_faces_by_image(
                        CollectionId=collection,
                        Image={
                            'Bytes': base64.decodebytes(b64_encoded),
                        },
                        FaceMatchThreshold=int(FACE_MINIMUM_CONFIDENCE_LEVEL),
                    )
                except:
                    logger.warn('Unable to identify face in crop. Quality may be too poor.')
                    break

                if 'FaceMatches' in response and len(response['FaceMatches']) > 0:
                    highest_confidence_match = response['FaceMatches'][0]
                    external_id = highest_confidence_match['Face']['ExternalImageId']
                    confidence = highest_confidence_match['Face']['Confidence']
                    [name_with_underscore, role_with_underscore] = external_id.split('-')

                    identified_persons.append({
                        'confidence': confidence,
                        'name': ' '.join(name_with_underscore.split('_')),
                        'role': ' '.join(role_with_underscore.split('_')),
                        'bounding_box': face,
                        'manual': False
                    })

    return identified_persons


def match_face_to_person(persons, identified_persons, timestamp, job_id):
    entries = []
    index = 0

    for person in persons:
        person_bb = {
            'left': person['BoundingBox']['Left'],
            'top': person['BoundingBox']['Top'],
            'right': person['BoundingBox']['Left'] + person['BoundingBox']['Width'],
            'bottom': person['BoundingBox']['Top'] + person['BoundingBox']['Height']
        }

        matches_face = False

        for face in identified_persons:
            face_bb = {
                'left': face['bounding_box']['Left'],
                'top': face['bounding_box']['Top'],
                'right': face['bounding_box']['Left'] + face['bounding_box']['Width'],
                'bottom': face['bounding_box']['Top'] + face['bounding_box']['Height']
            }

            if person_bb['left'] <= face_bb['left'] and person_bb['top'] <= face_bb['top']:
                if not is_face_in_entries(entries, face):
                    face_cp = face.copy()
                    face_cp['video_timestamp'] = f"{timestamp}_{index}"
                    face_cp['job_id'] = job_id
                    entries.append(face_cp)
                    index += 1
                    matches_face = True
                    break

        if not matches_face:
            entries.append({
                'job_id': job_id,
                'confidence': person['Confidence'],
                'name': None,
                'role': None,
                'bounding_box': person['BoundingBox'],
                'video_timestamp': f"{timestamp}_{index}",
                'manual': False
            })
            index += 1

    for face in identified_persons:
        if not is_face_in_entries(entries, face):
            face_cp = face.copy()
            face_cp['video_timestamp'] = f"{timestamp}_{index}"
            face_cp['job_id'] = job_id
            entries.append(face_cp)
            index += 1

    return entries


def handler(event, _context):
    bucket = event['bucket']
    collection = event['collection']
    frame = event['frame']
    job_id = event['job_id']

    timestamp = frame.split("/")[-1]
    timestamp = timestamp.replace('.png', '')
    timestamp = timestamp.replace('.jpg', '')

    persons = detect_persons(bucket, frame)
    faces = detect_faces(bucket, frame)
    logger.info(persons)
    identified_persons = identify_faces(bucket, frame, faces, collection)
    logger.info(identified_persons)
    entries = match_face_to_person(persons, identified_persons, timestamp, job_id)

    if len(entries) == 0:
        entries = [{
            'job_id': job_id,
            'confidence': None,
            'name': None,
            'role': None,
            'bounding_box': None,
            'video_timestamp': f"{timestamp}_0",
            'manual': False
        }]
    logger.info(entries)

    with results_table.batch_writer() as batch:
        for entry in entries:
            item = json.loads(json.dumps(entry), parse_float=Decimal)
            batch.put_item(Item=item)
