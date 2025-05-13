import os
import boto3
import json
from datetime import datetime

sagemaker_client = boto3.client('sagemaker')

def create_model(model_package_arn):
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        model_name = f"{os.environ['MODEL_PACKAGE_GROUP_NAME']}-{timestamp}"
        
        response = sagemaker_client.create_model(
            ModelName=model_name,
            ExecutionRoleArn=os.environ['EXECUTION_ROLE_ARN'],
            PrimaryContainer={
                'ModelPackageName': model_package_arn
            }
        )
        return model_name
    except Exception as e:
        print(f"Error creating model: {str(e)}")
        raise

def create_endpoint_config(model_name):
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        endpoint_config_name = f"{os.environ['MODEL_PACKAGE_GROUP_NAME']}-ec-{timestamp}"
        
        response = sagemaker_client.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[
                {
                    'VariantName': os.environ['VARIANT_NAME'],
                    'ModelName': model_name,
                    'InstanceType': os.environ['INSTANCE_TYPE'],
                    'InitialInstanceCount': int(os.environ['INITIAL_INSTANCE_COUNT']),
                    'InitialVariantWeight': float(os.environ['INITIAL_VARIANT_WEIGHT'])
                }
            ],
            KmsKeyId=os.environ['KMS_KEY_ID']
        )
        return endpoint_config_name
    except Exception as e:
        print(f"Error creating endpoint config: {str(e)}")
        raise

def create_or_update_endpoint(endpoint_config_name):
    try:
        endpoint_name = os.environ['ENDPOINT_NAME']
        
        try:
            # Try to update existing endpoint
            response = sagemaker_client.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )
            print(f"Updating existing endpoint: {endpoint_name}")
        except sagemaker_client.exceptions.ClientError as e:
            if "Could not find endpoint" in str(e):
                # Create new endpoint if it doesn't exist
                response = sagemaker_client.create_endpoint(
                    EndpointName=endpoint_name,
                    EndpointConfigName=endpoint_config_name
                )
                print(f"Creating new endpoint: {endpoint_name}")
            else:
                raise
                
        return endpoint_name
    except Exception as e:
        print(f"Error creating/updating endpoint: {str(e)}")
        raise

def deploy_model(model_package_arn):
    try:
        # Create model
        model_name = create_model(model_package_arn)
        print(f"Created model: {model_name}")
        
        # Create endpoint config
        endpoint_config_name = create_endpoint_config(model_name)
        print(f"Created endpoint config: {endpoint_config_name}")
        
        # Create or update endpoint
        endpoint_name = create_or_update_endpoint(endpoint_config_name)
        print(f"Endpoint deployment initiated: {endpoint_name}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Model deployment initiated successfully',
                'modelName': model_name,
                'endpointConfigName': endpoint_config_name,
                'endpointName': endpoint_name
            })
        }
    except Exception as e:
        print(f"Error in deploy_model: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    try:
        if event['detail']['currentModelPackageStatus'] == 'Approved':
            print("Model approved event received")
            model_package_arn = event['detail']['modelPackageArn']
            return deploy_model(model_package_arn)
        else:
            print(f"Ignoring model package status: {event['detail']['currentModelPackageStatus']}")
            return {
                'statusCode': 200,
                'body': json.dumps('No action needed for this status')
            }
    except Exception as e:
        print(f"Error in handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }