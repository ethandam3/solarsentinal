import boto3, time

sm = boto3.client('sagemaker', region_name='us-east-1')

print("Polling solarsentinel-predictor endpoint...")
for i in range(120):  # wait up to 30 min
    resp   = sm.describe_endpoint(EndpointName='solarsentinel-predictor')
    status = resp['EndpointStatus']
    print(f'  [{i*15:>4}s] {status}')
    if status == 'InService':
        print('\nENDPOINT IS LIVE - ready for demo!')
        break
    if status == 'Failed':
        print('\nFAILED:', resp.get('FailureReason'))
        break
    time.sleep(15)
