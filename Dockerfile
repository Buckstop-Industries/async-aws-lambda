FROM public.ecr.aws/lambda/python:3.13

# Copy the async-aws-lambda package source
COPY src/async_aws_lambda /var/task/async_aws_lambda

# Copy application code
COPY examples/sam-example/handler.py ${LAMBDA_TASK_ROOT}
COPY examples/sam-example/requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies (async-aws-lambda will be available via PYTHONPATH)
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Set PYTHONPATH to include the package
ENV PYTHONPATH=/var/task:$PYTHONPATH

# Set the CMD to your handler
CMD [ "handler.handler" ]
