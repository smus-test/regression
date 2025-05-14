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

import importlib
from aws_cdk import (
    Aws,
    CfnParameter,
    Stack,
    Tags,
    aws_iam as iam,
    aws_kms as kms,
    aws_sagemaker as sagemaker,
    aws_s3 as s3,
    aws_lambda as lambda_,  # Add this line
    aws_events as events,
    aws_events_targets as targets,
    CfnOutput,
    Duration,
)

import constructs

from .get_approved_package import get_approved_package

from config.constants import (
    PROJECT_NAME,
    PROJECT_ID,
    MODEL_PACKAGE_GROUP_NAME,
    DEPLOY_ACCOUNT,
    ECR_REPO_ARN,
    MODEL_BUCKET_ARN,
    MODEL_BUCKET_NAME,
    AMAZON_DATAZONE_DOMAIN,
    AMAZON_DATAZONE_SCOPENAME,
    SAGEMAKER_DOMAIN_ARN,
    AMAZON_DATAZONE_PROJECT
)

from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from yamldataclassconfig import create_file_path_field
from config.config_mux import StageYamlDataClassConfig


@dataclass
class EndpointConfigProductionVariant(StageYamlDataClassConfig):
    """
    Endpoint Config Production Variant Dataclass
    a dataclass to handle mapping yml file configs to python class for endpoint configs
    """

    initial_instance_count: int = 1
    initial_variant_weight: int = 1
    instance_type: str = "ml.m5.2xlarge"
    variant_name: str = "AllTraffic"

    FILE_PATH: Path = create_file_path_field(
        "endpoint-config.yml", path_is_absolute=True
    )

    def get_endpoint_config_production_variant(self, model_name):
        """
        Function to handle creation of cdk glue job. It use the class fields for the job parameters.

        Parameters:
            model_name: name of the sagemaker model resource the sagemaker endpoint would use

        Returns:
            CfnEndpointConfig: CDK SageMaker CFN Endpoint Config resource
        """

        production_variant = sagemaker.CfnEndpointConfig.ProductionVariantProperty(
            initial_instance_count=self.initial_instance_count,
            initial_variant_weight=self.initial_variant_weight,
            instance_type=self.instance_type,
            variant_name=self.variant_name,
            model_name=model_name,
        )

        return production_variant


class DeployEndpointStack(Stack):
    """
    Deploy Endpoint Stack
    Deploy Endpoint stack which provisions SageMaker Model Endpoint resources.
    """

    def __init__(
        self,
        scope: constructs,
        id: str,
        **kwargs,
    ):

        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("sagemaker:project-id", PROJECT_ID)
        Tags.of(self).add("sagemaker:project-name", PROJECT_NAME)
        Tags.of(self).add("sagemaker:deployment-stage", Stack.of(self).stack_name)
        Tags.of(self).add("AmazonDataZoneDomain", AMAZON_DATAZONE_DOMAIN)
        Tags.of(self).add("AmazonDataZoneScopeName", AMAZON_DATAZONE_SCOPENAME)
        Tags.of(self).add("sagemaker:domain-arn", SAGEMAKER_DOMAIN_ARN)
        Tags.of(self).add("AmazonDataZoneProject", AMAZON_DATAZONE_PROJECT)
    
    
        model_bucket = s3.Bucket.from_bucket_arn(
            self, 
            "ModelBucket",
            bucket_arn=MODEL_BUCKET_ARN
        )

        # iam role that would be used by the model endpoint to run the inference
        model_execution_policy = iam.ManagedPolicy(
            self,
            "ModelExecutionPolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=[
                            "s3:Put*",
                            "s3:Get*",
                            "s3:List*",
                        ],
                        effect=iam.Effect.ALLOW,
                        resources=[
                            model_bucket.bucket_arn,
                            f"{model_bucket.bucket_arn}/*",
                        ],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "kms:Encrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:Decrypt",
                            "kms:DescribeKey",
                        ],
                        effect=iam.Effect.ALLOW,
                        resources=[f"arn:aws:kms:{Aws.REGION}:{DEPLOY_ACCOUNT}:key/*"],
                    ),
                ]
            ),
        )

        if ECR_REPO_ARN:
            model_execution_policy.add_statements(
                iam.PolicyStatement(
                    actions=["ecr:Get*"],
                    effect=iam.Effect.ALLOW,
                    resources=[ECR_REPO_ARN],
                )
            )

        model_execution_role = iam.Role(
            self,
            "ModelExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                model_execution_policy,
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                ),
            ],
        )

        # create kms key to be used by the assets bucket
        kms_key = kms.Key(
            self,
            "endpoint-kms-key",
            description="key used for encryption of data in Amazon SageMaker Endpoint",
            enable_key_rotation=True,
            policy=iam.PolicyDocument(
                statements=[
                    # Allow root account full access to the key
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        principals=[iam.AccountRootPrincipal()],
                        actions=["kms:*"],
                        resources=["*"]
                    )
                ]
            ),
        )

        # Create Lambda role
        lambda_role = iam.Role(
            self,
            "ModelDeploymentLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*"
                ]
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateModel", "sagemaker:CreateEndpointConfig",
                    "sagemaker:CreateEndpoint", "sagemaker:UpdateEndpoint",
                    "sagemaker:DeleteModel", "sagemaker:DeleteEndpointConfig",
                    "sagemaker:DeleteEndpoint", "sagemaker:DescribeModel",
                    "sagemaker:DescribeEndpointConfig", "sagemaker:DescribeEndpoint",
                    "sagemaker:ListModelPackages", "sagemaker:DescribeModelPackageGroup",
                    "sagemaker:DescribeModelPackage",
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:model/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint-config/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:model-package-group/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:model-package/*"
                ]
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                effect=iam.Effect.ALLOW,
                resources=[model_execution_role.role_arn],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                effect=iam.Effect.ALLOW,
                resources=[MODEL_BUCKET_ARN, f"{MODEL_BUCKET_ARN}/*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["kms:Decrypt", "kms:GenerateDataKey*", "kms:DescribeKey"],
                effect=iam.Effect.ALLOW,
                resources=[kms_key.key_arn],
            )
        )
        # Add these statements to the lambda_role.add_to_policy section in your stack

        # Permission to add tags to SageMaker resources
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:AddTags",
                    "sagemaker:ListTags",
                    "sagemaker:DeleteTags"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:model/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint-config/*"
                ]
            )
        )
        
        # Permission to use ECR images (if using SageMaker containers)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:BatchCheckLayerAvailability"
                ],
                effect=iam.Effect.ALLOW,
                resources=["*"]  # You might want to restrict this to specific ECR repositories
            )
        )
        
        # Additional SageMaker permissions that might be needed
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:InvokeEndpoint",
                    "sagemaker:DescribeTrainingJob",
                    "sagemaker:DescribeModelPackageGroup",
                    "sagemaker:ListModelPackages"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:*"
                ]
            )
        )
        
        # CloudWatch Logs permissions (already included but showing for completeness)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*"
                ]
            )
        )

        
    
        # Create Lambda function
        endpoint_config_production_variant = EndpointConfigProductionVariant()
        endpoint_config_production_variant.load_for_stack(self)

        deploy_function = lambda_.Function(
            self,
            "ModelDeploymentFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda"),
            role=lambda_role,
            environment={
                "MODEL_PACKAGE_GROUP_NAME": MODEL_PACKAGE_GROUP_NAME,
                "ENDPOINT_NAME": f"{MODEL_PACKAGE_GROUP_NAME[:20]}-{AMAZON_DATAZONE_PROJECT[:20]}-{AMAZON_DATAZONE_SCOPENAME[:20]}",
                "EXECUTION_ROLE_ARN": model_execution_role.role_arn,
                "KMS_KEY_ID": kms_key.key_id,
                "INSTANCE_TYPE": endpoint_config_production_variant.instance_type,
                "INITIAL_INSTANCE_COUNT": str(endpoint_config_production_variant.initial_instance_count),
                "INITIAL_VARIANT_WEIGHT": str(endpoint_config_production_variant.initial_variant_weight),
                "VARIANT_NAME": endpoint_config_production_variant.variant_name
            },
            timeout=Duration.minutes(15),
            memory_size=1024,
        )
        # Create IAM role for EventBridge
        events_role = iam.Role(
            self,
            "EventBridgeInvokeRole",
            assumed_by=iam.ServicePrincipal("events.amazonaws.com"),
            description="Role for EventBridge to invoke Lambda function"
        )
        
        # Add permissions to invoke Lambda
        events_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[deploy_function.function_arn]
            )
        )
        
        # Create EventBridge Rule using L1 construct
        rule = events.CfnRule(
            self,
            "ModelApprovalRule",
            description="Rule to trigger Lambda on SageMaker model approval",
            event_pattern={
                "source": ["aws.sagemaker"],
                "detail-type": ["SageMaker Model Package State Change"],
                "detail": {
                    "ModelPackageGroupName": [MODEL_PACKAGE_GROUP_NAME],
                    "ModelApprovalStatus": ["Approved"]
                }
            },
            targets=[{
                "id": "LambdaTarget",
                "arn": deploy_function.function_arn,
                "roleArn": events_role.role_arn
            }]
        )

        # Output the Lambda function name and ARN
        self.lambda_function_name = deploy_function.function_name
        self.lambda_function_arn = deploy_function.function_arn
