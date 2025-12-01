FROM public.ecr.aws/lambda/python:3.13

# Copy the async-aws-lambda package
COPY async_aws_lambda /var/task/async_aws_lambda
COPY pyproject.toml /var/task/pyproject.toml

# Copy application code
COPY examples/sam-example/handler.py ${LAMBDA_TASK_ROOT}
COPY examples/sam-example/requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt && \
    pip install --no-cache-dir -e /var/task

# Set the CMD to your handler
CMD [ "handler.handler" ]
