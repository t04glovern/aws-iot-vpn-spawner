import boto3
import os
import json
import random
import string
import re

# create the client outside of the handler
region_name = os.environ['REGION_NAME']
cf_client = boto3.client('cloudformation', region_name=region_name)
sns_client = boto3.client('sns', region_name=region_name)

# Get Stack details
stack_name          = os.environ['STACK_NAME']
stack_s3_bucket     = os.environ['STACK_S3_BUCKET']
stack_s3_key        = os.environ['STACK_S3_KEY']
stack_instance_type = os.environ['STACK_INSTANCE_TYPE']
stack_dns_primary   = os.environ['STACK_DNS_PRIMARY']
stack_dns_secondary = os.environ['STACK_DNS_SECONDARY']
sns_topic           = os.environ['SNS_TOPIC']

def _to_env(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).upper()

def lambda_handler(event, context):
    # Generate Credentials
    vpn_username = ''.join(random.choice(string.ascii_lowercase) for _ in range(5))
    vpn_password = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20))

    print("Creating " + stack_name + " stack...")
    cf_client.create_stack(
        StackName=stack_name,
        TemplateURL='https://s3.amazonaws.com/' + stack_s3_bucket + '/' + stack_s3_key,
        Parameters=[
            {
                "ParameterKey": "VPNUsername",
                "ParameterValue": vpn_username
            },
            {
                "ParameterKey": "VPNPassword",
                "ParameterValue": vpn_password
            },
            {
                "ParameterKey": "VPNPhrase",
                "ParameterValue": vpn_password
            },
            {
                "ParameterKey": "InstanceSize",
                "ParameterValue": stack_instance_type
            },
            {
                "ParameterKey": "DNSServerPrimary",
                "ParameterValue": stack_dns_primary
            },
            {
                "ParameterKey": "DNSServerSecondary",
                "ParameterValue": stack_dns_secondary
            }
        ]
    )

    print("Waiting for " + stack_name + " stack creation to complete...")
    cf_client.get_waiter('stack_create_complete').wait(StackName=stack_name)

    print("Retrieving outputs from " + stack_name + "...")
    response = cf_client.describe_stacks(StackName=stack_name)

    stack, = response['Stacks']
    outputs = stack['Outputs']
    out = {}
    for o in outputs:
        key = _to_env(o['OutputKey'])
        out[key] = o['OutputValue']
    out['VPN_USERNAME'] = vpn_username
    out['VPN_PASSWORD'] = vpn_password
    out['VPN_PHRASE']   = vpn_password

    print("Sending VPN details to " + sns_topic + "...")
    res = sns_client.publish(
        TargetArn=sns_topic,
        Message=json.dumps({'default': json.dumps(out)}),
        MessageStructure='json'
    )

    return res
