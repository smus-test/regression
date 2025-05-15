import boto3
import json

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event, indent=4)}")
    sagemaker_client = boto3.client('sagemaker')
    
    try:
        # Get endpoint name directly from the event
        endpoint_name = event.get('endpointName')
        if not endpoint_name:
            raise ValueError(f"No endpoint name found in event: {json.dumps(event)}")
            
        print(f"Checking status for endpoint: {endpoint_name}")
        response = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        
        status = response['EndpointStatus']
        print(f"Endpoint status: {status}")
        
        return {
            'statusCode': 200,
            'endpointName': endpoint_name,
            'endpointStatus': status,
            'failureReason': response.get('FailureReason', '') if status == 'Failed' else ''
        }
    except Exception as e:
        print(f"Error checking endpoint status: {str(e)}")
        return {
            'statusCode': 500,
            'endpointName': event.get('endpointName', 'unknown'),
            'endpointStatus': 'Failed',
            'failureReason': str(e)
        }
