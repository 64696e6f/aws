# Parse CloudTrail events from an S3 bucket and raise alerts via email when appropriate
#
# The Lambda function role needs the following permissions (AWS managed policies)
#  - AWSLambdaExecute (or at least read only for the s3 bucket where CT events are stored)
#  - AmazonEC2ReadOnlyAccess (to translate security group IDs names)
#  - AmazonSESFullAccess

from __future__ import print_function

import json
import urllib
import boto3
import gzip
import StringIO

### CHANGE THIS
alert_email="name@domain.com"
###

s3 = boto3.client('s3')
ses = boto3.client('ses')
ec2 = boto3.client('ec2')

def notify_by_email(subj, body):
    ret = ses.send_email( 
        Source = alert_email,
        Destination = { 'ToAddresses': [ alert_email ] },
        Message = {
            'Subject': {'Data': subj },
            'Body': { 'Text': { 'Data': body } }
        }
    )

# security group, port opened to world
def public_sg(record):
    notify = False
    
    group = ec2.describe_security_groups(DryRun=False, GroupIds=[record['requestParameters']['groupId']])
    msg = "When: "          + record['eventTime'] + '\n'
    msg = msg + "Region: "  + record['awsRegion'] + '\n'
    msg = msg + "Who: "     + record['userIdentity']['arn'] + '\n'
    msg = msg + "What: "    + group['SecurityGroups'][0]['GroupName'] + ' (' + record['requestParameters']['groupId'] + ') ' + 'port(s) '

    for ip1 in record['requestParameters']['ipPermissions']['items']:
        for ip2 in ip1['ipRanges']['items']:
            #print( "CIDR: " + ip2['cidrIp'])
            if ip2['cidrIp'] == "0.0.0.0/0":
                notify = True
                msg = msg + str( ip1['toPort'] ) + ', '
                
    if notify is True:
        #print (record)
        notify_by_email('CloudTrail Event - AuthorizeSecurityGroupIngress', msg)

# keypair, created
def create_keypair(record):
    msg = "When: "          + record['eventTime'] + '\n'
    msg = msg + "Region: "  + record['awsRegion'] + '\n'
    msg = msg + "Who: "     + record['userIdentity']['arn'] + '\n'
    msg = msg + "What: "    + record['requestParameters']['keyName']
    
    notify_by_email('CloudTrail Event - CreateKeyPair', msg)

# iam user, created
def create_user(record):
    msg = "When: "          + record['eventTime'] + '\n'
    msg = msg + "Region: "  + record['awsRegion'] + '\n'
    msg = msg + "Who: "     + record['userIdentity']['arn'] + '\n'
    msg = msg + "What: "    + record['requestParameters']['userName']    
    
    notify_by_email('CloudTrail Event - CreateUser', msg)

# iam role, created
def create_role(record):
    msg = "When: "          + record['eventTime'] + '\n'
    msg = msg + "Region: "  + record['awsRegion'] + '\n'
    msg = msg + "Who: "     + record['userIdentity']['arn'] + '\n'
    msg = msg + "What: "    + record['requestParameters']['roleName']
    
    notify_by_email('CloudTrail Event - CreateRole', msg)

# vpc, created
def create_vpc(record):
    msg = "When: "          + record['eventTime'] + '\n'
    msg = msg + "Region: "  + record['awsRegion'] + '\n'
    msg = msg + "Who: "     + record['userIdentity']['arn'] + '\n'
    msg = msg + "What: "    + record['requestParameters']['cidrBlock']
    
    notify_by_email('CloudTrail Event - CreateVPC', msg)

def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    try:
        myGzObj = s3.get_object( Bucket=bucket, Key=key )
        myBody = gzip.GzipFile( fileobj=StringIO.StringIO( myGzObj['Body'].read() ) );
        js = json.loads(myBody.read())

        for record in js['Records']:
            if   record['eventName'] == "AuthorizeSecurityGroupIngress":
                public_sg(record)
            elif record['eventName'] == "CreateKeyPair":
                create_keypair(record)
            elif record['eventName'] == "CreateUser":
                create_user(record)
            elif record['eventName'] == "CreateRole":
                create_role(record)
            elif record['eventName'] == "CreateVpc":
                create_vpc(record)
                
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}.'.format(key, bucket))
        raise e
