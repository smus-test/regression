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

from deploy_endpoint.deploy_endpoint_stack import DeployEndpointStack
from config.constants import (
    DEFAULT_DEPLOYMENT_REGION,
    DEPLOY_ACCOUNT,
    PROJECT_ID,
    PROJECT_NAME,
    AMAZON_DATAZONE_DOMAIN,
    AMAZON_DATAZONE_SCOPENAME,
    AMAZON_DATAZONE_PROJECT
)
import aws_cdk as cdk

app = cdk.App()

dev_env = cdk.Environment(account=DEPLOY_ACCOUNT, region=DEFAULT_DEPLOYMENT_REGION)

DeployEndpointStack(app, f"{AMAZON_DATAZONE_SCOPENAME}-{DEPLOY_ACCOUNT}-{AMAZON_DATAZONE_PROJECT}", env=dev_env)

app.synth()
