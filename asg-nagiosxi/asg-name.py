#!/usr/bin/env python

# Automatically add/remove ASG instances to/from NagiosXI
# - create an ASG called "asg-name", enable SNS notifications for scale up an scale down events (name the SNS topic "asg-name")
# - create an SQS queue name "asg-name"
# - subscribe the SQS to the SNS topic
# - edit the template file "asg-name.cfg" and add additional services you need

import boto.sqs
import boto.ec2
import json
import fileinput
import os

qname = "asg-name"
fpath = "/root/asg-nagioxi/"
needs_reaload = 0

ec2 = boto.ec2.connect_to_region("us-east-1")
sqs = boto.sqs.connect_to_region("us-east-1")
q = sqs.get_queue(qname)

# get all messages from queue
all_messages = []
rs = q.get_messages( num_messages=10, wait_time_seconds=1 )

while len(rs) > 0 :
    all_messages.extend(rs)
    rs = q.get_messages( num_messages=10, wait_time_seconds=1 )
#

for i in range( len( all_messages ) ):
    needs_reaload = 1
    message = all_messages[i]
    js = json.loads( message.get_body() )
    js2 = json.loads( js['Message'] )
    my_desc = js2['Description']

    ##print(my_desc.split()[0])

    if my_desc.split()[0] == "Launching":
        # adding
        instance_id = my_desc.split()[5]
        asg_name = js2['AutoScalingGroupName']
        instance_ip = ec2.get_only_instances( instance_ids=instance_id )[0].private_ip_address

        # read nagios config file template
        fh = open( fpath + asg_name + '.cfg', 'r' )
        data = fh.read();
        fh.close()

        data1 = data.replace( "__ADDR__", instance_ip )       
        data2 = data1.replace( "__HOST__", instance_id )
        data3 = data2.replace( "__GROUP__", asg_name )

        # write nagios config file
        fh = open( '/usr/local/nagios/etc/import/' + instance_id + '.cfg', 'w' )
        fh.write( data3 );
        fh.close()
    else:
        # removing
        instance_id = my_desc.split()[3]
        
        rets = os.system('cd /usr/local/nagiosxi/scripts; ./nagiosql_delete_service.php --config=' + instance_id)
        reth = os.system('cd /usr/local/nagiosxi/scripts; ./nagiosql_delete_host.php --host=' + instance_id)

    q.delete_message(message)

if needs_reaload == 1:
    retr = os.system('cd /usr/local/nagiosxi/scripts; ./reconfigure_nagios.sh')
