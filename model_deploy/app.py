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

from aws_cdk import App, Environment, DefaultStackSynthesizer
from deploy_endpoint.deploy_endpoint_stack import DeployEndpointStack
from config.constants import (
    DEPLOY_ACCOUNT,
    DEFAULT_DEPLOYMENT_REGION,
    AMAZON_DATAZONE_SCOPENAME,
    AMAZON_DATAZONE_PROJECT
)
import os

app = App()

dev_env = Environment(
    account=DEPLOY_ACCOUNT,
    region=DEFAULT_DEPLOYMENT_REGION
)

# Use DefaultStackSynthesizer with just the deploy role specified
synthesizer = DefaultStackSynthesizer(
    deploy_role_arn=os.environ.get('SAGEMAKER_PIPELINE_ROLE_ARN')
)

DeployEndpointStack(
    app, 
    f"sagemaker-{AMAZON_DATAZONE_PROJECT}", 
    env=dev_env,
    synthesizer=synthesizer
)

app.synth()
