FROM public.ecr.aws/lambda/python:3.12

RUN pip install --no-cache-dir boto3 numpy opencv-python-headless rawpy

COPY lambda/processor.py ${LAMBDA_TASK_ROOT}/
COPY processors/ ${LAMBDA_TASK_ROOT}/processors/

CMD ["processor.lambda_handler"]
