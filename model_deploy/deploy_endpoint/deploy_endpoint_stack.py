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

import os
from aws_cdk import (
    Duration, 
    Stack,
    CfnOutput,
    Aws,
    aws_iam as iam,
    aws_kms as kms,
    aws_sagemaker as sagemaker,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_events as events,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    Tags
)
from constructs import Construct
from dataclasses import dataclass
from pathlib import Path
from yamldataclassconfig import create_file_path_field
from config.config_mux import StageYamlDataClassConfig

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

@dataclass
class EndpointConfigProductionVariant(StageYamlDataClassConfig):
    initial_instance_count: int = None
    initial_variant_weight: int = None
    instance_type: str = None
    variant_name: str = None
    
    def load_for_stack(self, stack):
        try:
            # Use AMAZON_DATAZONE_SCOPENAME for environment
            env = AMAZON_DATAZONE_SCOPENAME.lower()  # Ensure lowercase for consistency
            print(f"Current environment from AMAZON_DATAZONE_SCOPENAME: {env}")

            # Use relative path from the current file
            config_path = os.path.join(
                os.path.dirname(__file__),
                f"../config/dev/endpoint-config.yml"
            )
            config_path = os.path.abspath(config_path)
            
            print(f"Current file location: {__file__}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Looking for config file at: {config_path}")
            
            if not os.path.exists(config_path):
                print(f"Config directory contents: {os.listdir(os.path.dirname(os.path.dirname(config_path)))}")
                raise FileNotFoundError(f"Config file not found at {config_path}")
                
            self.FILE_PATH = Path(config_path)
            super().load_for_stack(stack)
            
            # Validate that all required values are present
            missing_values = [field for field in ['initial_instance_count', 'initial_variant_weight', 'instance_type', 'variant_name'] 
                              if getattr(self, field) is None]
            
            if missing_values:
                raise ValueError(f"Missing required values in config file: {', '.join(missing_values)}")
                
            print(f"Successfully loaded config from {env} environment: {vars(self)}")
                
        except Exception as e:
            print(f"Error loading endpoint config: {str(e)}")
            print(f"AMAZON_DATAZONE_SCOPENAME: {AMAZON_DATAZONE_SCOPENAME}")
            import traceback
            print(traceback.format_exc())
            raise

            
    def get_endpoint_config_production_variant(self, model_name):
        # Validate all required values are present before creating the config
        if any(v is None for v in [
            self.initial_instance_count,
            self.initial_variant_weight,
            self.instance_type,
            self.variant_name
        ]):
            raise ValueError("Cannot create endpoint config: missing required values")
            
        return sagemaker.CfnEndpointConfig.ProductionVariantProperty(
            initial_instance_count=self.initial_instance_count,
            initial_variant_weight=self.initial_variant_weight,
            instance_type=self.instance_type,
            variant_name=self.variant_name,
            model_name=model_name,
        )

class DeployEndpointStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Add stack level tags
        Tags.of(self).add("sagemaker:project-id", PROJECT_ID)
        Tags.of(self).add("sagemaker:project-name", PROJECT_NAME)
        Tags.of(self).add("sagemaker:deployment-stage", self.stack_name)
        Tags.of(self).add("AmazonDataZoneDomain", AMAZON_DATAZONE_DOMAIN)
        Tags.of(self).add("AmazonDataZoneScopeName", AMAZON_DATAZONE_SCOPENAME)
        Tags.of(self).add("sagemaker:domain-arn", SAGEMAKER_DOMAIN_ARN)
        Tags.of(self).add("AmazonDataZoneProject", AMAZON_DATAZONE_PROJECT)

        try:
            # Create and load endpoint config
            endpoint_config = EndpointConfigProductionVariant()
            endpoint_config.load_for_stack(self)
            print(f"Loaded endpoint config: {vars(endpoint_config)}")
        except Exception as e:
            raise ValueError(f"Failed to load endpoint configuration: {str(e)}")


        # Get model bucket
        model_bucket = s3.Bucket.from_bucket_arn(self, "ModelBucket", bucket_arn=MODEL_BUCKET_ARN)

        # Create KMS key
        kms_key = self.create_kms_key()

        # Create IAM roles
        model_execution_role = self.create_model_execution_role(model_bucket, kms_key)
        lambda_role = self.create_lambda_role(model_bucket, kms_key, model_execution_role)
        
        deploy_function = self.create_deploy_lambda(
            lambda_role, 
            model_execution_role, 
            kms_key, 
            endpoint_config
        )
        check_status_function = self.create_check_status_lambda(lambda_role)
        
        # Create Step Functions workflow
        state_machine = self.create_deployment_workflow(deploy_function, check_status_function)

        # Create EventBridge rule
        self.create_eventbridge_rule(state_machine)

        # Create outputs
        self.create_outputs(deploy_function,check_status_function, state_machine)

    def create_kms_key(self):
        return kms.Key(
            self,
            "endpoint-kms-key",
            description="Key for SageMaker Endpoint encryption",
            enable_key_rotation=True,
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        principals=[iam.AccountRootPrincipal()],
                        actions=["kms:*"],
                        resources=["*"]
                    )
                ]
            ),
        )

    def create_model_execution_role(self, model_bucket, kms_key):
        model_execution_policy = iam.ManagedPolicy(
            self,
            "ModelExecutionPolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["s3:Put*", "s3:Get*", "s3:List*"],
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
                        resources=[kms_key.key_arn],
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

        return iam.Role(
            self,
            "ModelExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                model_execution_policy,
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
            ],
        )

    def create_lambda_role(self, model_bucket, kms_key, model_execution_role):
        lambda_role = iam.Role(
            self,
            "ModelDeploymentLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # Add necessary permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateModel",
                    "sagemaker:CreateEndpointConfig",
                    "sagemaker:CreateEndpoint",
                    "sagemaker:UpdateEndpoint",
                    "sagemaker:DeleteModel",
                    "sagemaker:DeleteEndpointConfig",
                    "sagemaker:DeleteEndpoint",
                    "sagemaker:DescribeModel",
                    "sagemaker:DescribeEndpointConfig",
                    "sagemaker:DescribeEndpoint",
                    "sagemaker:AddTags",
                    "sagemaker:ListTags",
                    "sagemaker:DeleteTags"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:*"
                ]
            )
        )

        # Add KMS permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:CreateGrant",
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:Encrypt",
                    "kms:GenerateDataKey*",
                    "kms:ReEncrypt*",
                    "kms:ListGrants",
                    "kms:RevokeGrant"
                ],
                effect=iam.Effect.ALLOW,
                resources=[kms_key.key_arn]
            )
        )

        # Add other necessary permissions
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            effect=iam.Effect.ALLOW,
            resources=[model_execution_role.role_arn],
        ))

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/{self.stack_name[:30]}-*",
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/{self.stack_name[:30]}-*:*"
            ]
            )
        )

        return lambda_role

    def create_deploy_lambda(self, lambda_role, model_execution_role, kms_key, endpoint_config):
        return lambda_.Function(
            self,
            "ModelDeploymentFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/deploy_endpoint"),
            role=lambda_role,
            function_name=f"{self.stack_name[:30]}-deploy-endpoint", 
            environment={
                # Model deployment configuration
                "MODEL_PACKAGE_GROUP_NAME": MODEL_PACKAGE_GROUP_NAME,
                "ENDPOINT_NAME": f"{MODEL_PACKAGE_GROUP_NAME[:20]}-{AMAZON_DATAZONE_PROJECT[:20]}-{AMAZON_DATAZONE_SCOPENAME[:20]}",
                "EXECUTION_ROLE_ARN": model_execution_role.role_arn,
                "KMS_KEY_ID": kms_key.key_id,
                "INSTANCE_TYPE": endpoint_config.instance_type,
                "INITIAL_INSTANCE_COUNT": str(endpoint_config.initial_instance_count),
                "INITIAL_VARIANT_WEIGHT": str(endpoint_config.initial_variant_weight),
                "VARIANT_NAME": endpoint_config.variant_name,
                
                # Tags as environment variables
                "SAGEMAKER_PROJECT_NAME": PROJECT_NAME,
                "SAGEMAKER_PROJECT_ID": PROJECT_ID,
                "AMAZON_DATAZONE_DOMAIN": AMAZON_DATAZONE_DOMAIN,
                "AMAZON_DATAZONE_SCOPENAME": AMAZON_DATAZONE_SCOPENAME,
                "SAGEMAKER_DOMAIN_ARN": SAGEMAKER_DOMAIN_ARN,
                "AMAZON_DATAZONE_PROJECT": AMAZON_DATAZONE_PROJECT,
                "DEPLOYMENT_STAGE": self.stack_name
            },
            timeout=Duration.minutes(15),
            memory_size=1024,
        )
        
    def create_check_status_lambda(self, lambda_role):
        return lambda_.Function(
            self,
            "CheckEndpointStatusFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("lambda/check_endpoint_status"),
            role=lambda_role,
            function_name=f"{self.stack_name[:30]}-check-endpoint",
            timeout=Duration.minutes(5),
            memory_size=128,
        )
    
    def create_deployment_workflow(self, deploy_function, check_status_function):
        # Create Lambda task for deployment
        deploy_task = sfn_tasks.LambdaInvoke(
            self, "DeployModel",
            lambda_function=deploy_function,
            output_path="$.Payload"
        )
       
        # Create Lambda task for status checking
        check_status = sfn_tasks.LambdaInvoke(
            self, "CheckEndpointStatus",
            lambda_function=check_status_function,
            output_path="$.Payload"
        )

        # Create wait state
        wait = sfn.Wait(
            self, "WaitForEndpoint",
            time=sfn.WaitTime.duration(Duration.seconds(30))
        )

        # Create choice state
        choice = sfn.Choice(self, "CheckDeploymentStatus")

        # Create success and fail states
        succeed = sfn.Succeed(self, "DeploymentSucceeded")
        fail = sfn.Fail(
            self, 
            "DeploymentFailed",
            cause="Endpoint deployment failed",
            error="$.failureReason"
        )


        # Create workflow
        definition = deploy_task\
            .next(check_status)\
            .next(
                choice
                .when(
                    sfn.Condition.string_equals("$.endpointStatus", "InService"),
                    succeed
                )
                .when(
                    sfn.Condition.string_equals("$.endpointStatus", "Failed"),
                    fail
                )
                .otherwise(
                    wait.next(check_status)
                )
            )

        # Create state machine
        return sfn.StateMachine(
            self, "EndpointDeploymentWorkflow",
            definition=definition,
            timeout=Duration.hours(2)
        )

    def create_eventbridge_rule(self, state_machine):
        # Create EventBridge IAM role
        events_role = iam.Role(
            self,
            "EventBridgeRole",
            assumed_by=iam.ServicePrincipal("events.amazonaws.com")
        )

        # Add permission to invoke state machine
        events_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:StartExecution"],
                resources=[state_machine.state_machine_arn]
            )
        )

        # Create EventBridge rule using CfnRule
        return events.CfnRule(
            self,
            "ModelApprovalRule",
            description="Trigger deployment workflow when model is approved",
            event_pattern={
                "source": ["aws.sagemaker"],
                "detail-type": ["SageMaker Model Package State Change"],
                "detail": {
                    "ModelPackageGroupName": [MODEL_PACKAGE_GROUP_NAME],
                    "ModelApprovalStatus": ["Approved"]
                }
            },
            targets=[{
                "id": "DeploymentWorkflowTarget",
                "arn": state_machine.state_machine_arn,
                "roleArn": events_role.role_arn
            }]
        )

    def create_outputs(self, deploy_function, check_status_function, state_machine):
        CfnOutput(
            self, "DeployFunctionName",
            value=deploy_function.function_name,
            description="Name of the deployment Lambda function"
        )
        
        CfnOutput(
            self, "CheckStatusFunctionName",
            value=check_status_function.function_name,
            description="Name of the check status Lambda function"
        )
        
        CfnOutput(
            self, "StateMachineArn",
            value=state_machine.state_machine_arn,
            description="ARN of the deployment workflow state machine"
        )