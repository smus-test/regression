import boto3
import json

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    sagemaker_client = boto3.client('sagemaker')
    
    try:
        # Parse the stringified JSON in the body if it's a string
        body = event['body'] if isinstance(event['body'], dict) else json.loads(event['body'])
        endpoint_name = body['endpointName']
        
        print(f"Checking status for endpoint: {endpoint_name}")
        response = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        
        status = response['EndpointStatus']
        print(f"Endpoint status: {status}")
        
        return {
            'statusCode': 200,
            'endpointStatus': status,
            'endpointName': endpoint_name,
            'failureReason': response.get('FailureReason', '') if status == 'Failed' else ''
        }
    except Exception as e:
        print(f"Error checking endpoint status: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'endpointName': endpoint_name if 'endpoint_name' in locals() else 'unknown'
        }