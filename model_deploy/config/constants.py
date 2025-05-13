    # Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import boto3
import os
from dotenv import load_dotenv
print("DEBUG: constants.py is being executed")

load_dotenv()  # take environment variables from GitHub Action

DEFAULT_DEPLOYMENT_REGION = os.getenv("AWS_REGION", "us-west-2")

DEPLOY_ACCOUNT = os.getenv("DEPLOY_ACCOUNT", "643732685158")

PROJECT_NAME = os.getenv("SAGEMAKER_PROJECT_NAME", "My_Project_m93fcul5-marketing")
PROJECT_ID = os.getenv("SAGEMAKER_PROJECT_ID", "aqaa5fdrbjnlao")
MODEL_PACKAGE_GROUP_NAME = os.getenv("MODEL_PACKAGE_GROUP_NAME", "git-abalone-smus")
MODEL_BUCKET_ARN = "arn:aws:s3:::amazon-sagemaker-643732685158-us-west-2-f16345659560"
print(f"DEBUG: In constants.py, MODEL_BUCKET_ARN = {MODEL_BUCKET_ARN}")
MODEL_BUCKET_NAME = os.getenv("MODEL_BUCKET_NAME", "amazon-sagemaker-643732685158-us-west-2-f16345659560")
ECR_REPO_ARN = os.getenv("ECR_REPO_ARN", None)
AMAZON_DATAZONE_DOMAIN = os.getenv("AMAZON_DATAZONE_DOMAIN", "dzd_d2hu7wi9b2nro0")
AMAZON_DATAZONE_SCOPENAME = os.getenv("AMAZON_DATAZONE_SCOPENAME", "dev")
SAGEMAKER_DOMAIN_ARN = os.getenv("SAGEMAKER_DOMAIN_ARN", "arn:aws:sagemaker:us-west-2:643732685158:domain/d-yzd7xzpwhgk9")
AMAZON_DATAZONE_PROJECT = os.getenv("AMAZON_DATAZONE_PROJECT", "aqaa5fdrbjnlao")