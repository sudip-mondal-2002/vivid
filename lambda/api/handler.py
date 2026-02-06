"""Lambda handler - serves frontend and API endpoints."""
import os
import json
import uuid
import boto3
from datetime import datetime

s3 = boto3.client('s3')
BUCKET = os.environ.get('BUCKET_NAME')


def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    path = event.get('rawPath', '/')
    
    # Serve frontend
    if method == 'GET':
        if path in ['/', '/index.html']:
            return serve_file('index.html', 'text/html')
        elif path == '/style.css':
            return serve_file('style.css', 'text/css')
        elif path == '/app.js':
            return serve_file('app.js', 'application/javascript')
        elif path.startswith('/status/'):
            return get_status(path.split('/')[-1])
        elif path.startswith('/result/'):
            return get_result(path.split('/')[-1])
    
    # API endpoints
    if method == 'POST' and path == '/upload':
        return create_upload(event)
    
    if method == 'OPTIONS':
        return response(200, '')
    
    return response(404, {'error': 'Not found'})


def serve_file(name, content_type):
    try:
        path = os.path.join(os.path.dirname(__file__), 'frontend', name)
        with open(path, 'r') as f:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': content_type, 'Access-Control-Allow-Origin': '*'},
                'body': f.read()
            }
    except:
        return response(404, {'error': 'File not found'})


def create_upload(event):
    try:
        body = json.loads(event.get('body', '{}'))
    except:
        body = {}
    
    task_id = str(uuid.uuid4())[:8]
    filename = body.get('filename', 'image.CR2')
    preset = body.get('preset', 'standard')
    fmt = body.get('format', 'jpg')
    
    # Only accept CR2 files
    if not filename.lower().endswith('.cr2'):
        return response(400, {'error': 'Only Canon CR2 RAW files are supported.'})
    
    # Pre-signed upload URL (no metadata - causes signature issues)
    key = f"uploads/{task_id}/{filename}"
    url = s3.generate_presigned_url('put_object', Params={
        'Bucket': BUCKET,
        'Key': key,
        'ContentType': 'application/octet-stream'
    }, ExpiresIn=3600)
    
    # Store preset/format in status file (processor reads from here)
    s3.put_object(
        Bucket=BUCKET,
        Key=f"status/{task_id}.json",
        Body=json.dumps({
            'task_id': task_id,
            'stage': 'pending',
            'percent': 0,
            'message': 'Waiting for upload',
            'preset': preset,
            'format': fmt
        })
    )
    
    return response(200, {'task_id': task_id, 'upload_url': url})


def get_status(task_id):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=f"status/{task_id}.json")
        return response(200, json.loads(obj['Body'].read()))
    except:
        return response(404, {'error': 'Not found'})


def get_result(task_id):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=f"status/{task_id}.json")
        status = json.loads(obj['Body'].read())
        
        if status.get('stage') != 'complete':
            return response(400, {'error': 'Not ready'})
        
        # Enhanced image URL
        download_url = s3.generate_presigned_url('get_object', Params={
            'Bucket': BUCKET,
            'Key': status['result_key']
        }, ExpiresIn=3600)
        
        # Original preview URL (for side-by-side comparison)
        original_url = None
        if status.get('original_key'):
            original_url = s3.generate_presigned_url('get_object', Params={
                'Bucket': BUCKET,
                'Key': status['original_key']
            }, ExpiresIn=3600)
        
        return response(200, {'download_url': download_url, 'original_url': original_url})
    except:
        return response(404, {'error': 'Not found'})


def response(code, body):
    return {
        'statusCode': code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Allow-Headers': '*'
        },
        'body': json.dumps(body) if isinstance(body, dict) else body
    }
