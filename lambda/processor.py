"""S3-triggered Lambda for image processing."""
import os
import json
import boto3
from urllib.parse import unquote_plus

from processors import EnhancerFactory, PresetType, OutputFormat

s3 = boto3.client('s3')
BUCKET = os.environ.get('BUCKET_NAME')


def lambda_handler(event, context):
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        
        # Extract task_id from key: uploads/{task_id}/{filename}
        parts = key.split('/')
        if len(parts) < 3 or parts[0] != 'uploads':
            continue
        
        task_id = parts[1]
        
        try:
            process_image(bucket, key, task_id)
        except Exception as e:
            update_status(task_id, 'error', 0, str(e))
            raise


def process_image(bucket, key, task_id):
    update_status(task_id, 'processing', 10, 'Downloading image...')
    
    # Get preset/format from status file
    try:
        status_obj = s3.get_object(Bucket=BUCKET, Key=f"status/{task_id}.json")
        status = json.loads(status_obj['Body'].read())
        preset = status.get('preset', 'standard')
        fmt = status.get('format', 'jpg')
    except:
        preset = 'standard'
        fmt = 'jpg'
    
    # Download file bytes
    response = s3.get_object(Bucket=bucket, Key=key)
    file_bytes = response['Body'].read()
    
    update_status(task_id, 'processing', 30, 'Processing image...')
    
    # Get enhancer and process
    preset_type = PresetType[preset.upper()] if preset.upper() in PresetType.__members__ else PresetType.STANDARD
    output_format = OutputFormat[fmt.upper()] if fmt.upper() in OutputFormat.__members__ else OutputFormat.JPG
    
    def progress_cb(stage, percent, message):
        update_status(task_id, 'processing', 30 + int(percent * 0.6), message)
    
    enhancer = EnhancerFactory.get_enhancer(preset_type, file_bytes, progress_cb)
    
    # Save original preview (RAW converted to viewable JPG, no enhancements)
    update_status(task_id, 'processing', 50, 'Creating original preview...')
    original_preview = enhancer.get_original_preview()
    original_key = f"originals/{task_id}.jpg"
    s3.put_object(
        Bucket=bucket,
        Key=original_key,
        Body=original_preview,
        ContentType='image/jpeg'
    )
    
    # Process with enhancements
    update_status(task_id, 'processing', 60, 'Applying enhancements...')
    result_bytes = enhancer.process(output_format)
    
    update_status(task_id, 'processing', 95, 'Uploading result...')
    
    # Upload result
    result_key = f"results/{task_id}.{fmt}"
    s3.put_object(
        Bucket=bucket,
        Key=result_key,
        Body=result_bytes,
        ContentType=f'image/{fmt}'
    )
    
    update_status(task_id, 'complete', 100, 'Done!', result_key, original_key)


def update_status(task_id, stage, percent, message, result_key=None, original_key=None):
    data = {
        'task_id': task_id,
        'stage': stage,
        'percent': percent,
        'message': message
    }
    if result_key:
        data['result_key'] = result_key
    if original_key:
        data['original_key'] = original_key
    
    s3.put_object(
        Bucket=BUCKET,
        Key=f"status/{task_id}.json",
        Body=json.dumps(data),
        ContentType='application/json'
    )
