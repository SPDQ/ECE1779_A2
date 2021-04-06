import boto3
import json
from math import ceil
import logging
from botocore.exceptions import ClientError
import time
import os
from flaskr import db
from flaskr.models import AutoScalingConfig, users, images
from datetime import datetime, timedelta
import traceback
basedir = os.path.abspath(os.path.dirname(__file__))


import requests
r = requests.get('http://169.254.169.254/latest/meta-data/iam/security-credentials/ece1779_a2_manager')
json_obj = r.json()
# print(json_obj)
TOKEN = json_obj["Token"]
AccessKeyId = json_obj["AccessKeyId"]
SecretAccessKey=json_obj["SecretAccessKey"]


class AwsClient:
    def __init__(self):
        self.ec2 = boto3.client('ec2', region_name='us-east-1', aws_access_key_id= AccessKeyId, aws_secret_access_key=SecretAccessKey, aws_session_token=TOKEN)
        self.elb = boto3.client('elbv2', region_name='us-east-1', aws_access_key_id= AccessKeyId, aws_secret_access_key=SecretAccessKey, aws_session_token=TOKEN)
        self.s3 = boto3.client('s3', region_name='us-east-1', aws_access_key_id= AccessKeyId, aws_secret_access_key=SecretAccessKey, aws_session_token=TOKEN)
        self.bk = 'david-ece1779-test'
        self.TargetGroupArn = \
            'arn:aws:elasticloadbalancing:us-east-1:062266107775:targetgroup/test1/9b6750d09cf3dbd9'
        self.cloudwatch = boto3.client('cloudwatch', region_name='us-east-1', aws_access_key_id=AccessKeyId,
                                       aws_secret_access_key=SecretAccessKey, aws_session_token=TOKEN)
        self.user_app_tag = 'user-ece1779_a2'
        self.manager_app_tag = 'manager-ece1779_a2'
        self.image_id = 'ami-06bf14306281ea55c'
        self.instance_type = 't2.medium'
        self.keypair_name = 'keypair'
        self.security_group = ['launch-wizard-3']
        self.IamInstanceProfile = {
            'Name': 'ec2_s3_role'
        }
        with open(basedir+'/Userdata.txt', 'r') as myfile:
            data = myfile.read()
        self.userdata = data
        self.tag_specification=[{
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': self.user_app_tag
                }]
        }]
        self.monitoring = {
            'Enabled': True
        }
        self.tag_placement ={
            'AvailabilityZone': 'us-east-1f'
        }
        self.loadbalancer = 'app/ece1779alb/5543d659dbff8b26'
        self.targetgroup = 'targetgroup/test1/9b6750d09cf3dbd9'

    def create_ec2_instance(self):
        try:
            response = self.ec2.run_instances(ImageId=self.image_id,
                                                InstanceType=self.instance_type,
                                                KeyName=self.keypair_name,
                                                MinCount=1,
                                                MaxCount=1,
                                                SecurityGroups=self.security_group,
                                                TagSpecifications=self.tag_specification,
                                                Monitoring = self.monitoring,
                                                Placement = self.tag_placement,
                                                IamInstanceProfile= self.IamInstanceProfile,
                                                UserData = self.userdata
                                              )
            return response['Instances'][0]

        except ClientError as e:
            logging.error(e)
            return None

    def get_tag_instances(self):
        instances = []
        custom_filter = [{
            'Name': 'tag:Name',
            'Values': [self.user_app_tag]}]
        response = self.ec2.describe_instances(Filters=custom_filter)
        #instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']
        reservations = response['Reservations']
        for reservation in reservations:
            if len(reservation['Instances']) > 0 and reservation['Instances'][0]['State']['Name'] != 'terminated':
                instances.append({
                 'Id': reservation['Instances'][0]['InstanceId'],
                 'State': reservation['Instances'][0]['State']['Name']
                })
        return instances

    # if the instances in the target group are stopped, then the state is unused,
    # and the instances still stay in the target group.
    def get_target_instances(self):
        tag_instance = self.get_tag_instances()
        tag_instance_id = []
        for item in tag_instance:
            tag_instance_id.append(item['Id'])
        response = self.elb.describe_target_health(
            TargetGroupArn=self.TargetGroupArn,
        )
        instances = []
        if 'TargetHealthDescriptions' in response:
            for target in response['TargetHealthDescriptions']:
                if target['Target']['Id'] not in tag_instance_id:
                    continue
                instances.append({
                    'Id': target['Target']['Id'],
                    'Port': target['Target']['Port'],
                    'State': target['TargetHealth']['State']
                })
        return instances

    # when the state is draining, the instance is actually out of the target group
    def get_valid_target_instances(self):
        target_instances = self.get_target_instances()
        target_instances_id = []
        for item in target_instances:
            if item['State'] != 'draining':
                target_instances_id.append(item['Id'])
        return target_instances_id

    # we have to make instances in the target group are all running
    # in order to make sure that the idle instances are outside the target group.
    def get_idle_instances(self):
        """
        return idle instances
        :return: instances: list
        """
        instances_tag_raw = self.get_tag_instances()
        instances_target_raw = self.get_target_instances()
        instances_tag =[]
        instances_target = []
        for item in instances_tag_raw:
            instances_tag.append(item['Id'])
        for item in instances_target_raw:
            instances_target.append(item['Id'])

        diff_list = []
        for item in instances_tag:
            if item not in instances_target:
                diff_list.append(item)
        
        return diff_list

    # any instance in target group with healthy status
    def get_healthy_instances(self):
        target_instances = self.get_target_instances()
        healthy_target_instances_id = []
        for instance_id in target_instances:
            if instance_id['State'] == 'healthy':
                healthy_target_instances_id.append(instance_id['Id'])
        return healthy_target_instances_id

    # any instance in target group with healthy or initial status
    def get_ini_healthy_instances(self):
        target_instances = self.get_target_instances()
        healthy_target_instances_id = []
        for instance_id in target_instances:
            if instance_id['State'] != 'unused':
                healthy_target_instances_id.append(instance_id['Id'])
        return healthy_target_instances_id

    # cannot get the state of stopped instances
    def get_specfic_instance_state(self, instance_id):
        """
        describe specfic state of an instance 
        """
        response = self.ec2.describe_instance_status(InstanceIds=[instance_id])
        # response['InstanceStatuses'][0]['InstanceState']['Name']
        return response

    def grow_worker_by_one(self):
        """
        add one instance into the self.TargetGroupArn
        :return: msg: str
        register_targets(**kwargs)
        """
        idle_instances = self.get_idle_instances()

        new_instance_id = None
        if idle_instances:
            new_instance_id = idle_instances[0]
            # start instance
            self.ec2.start_instances(
                InstanceIds=[new_instance_id]
            )
        else:
            response = self.create_ec2_instance()
            new_instance_id = response['InstanceId']

        time.sleep(3)
        specfic_state = self.get_specfic_instance_state(new_instance_id)
        while len(specfic_state['InstanceStatuses']) < 1:
            time.sleep(1)
            specfic_state = self.get_specfic_instance_state(new_instance_id)

        while specfic_state['InstanceStatuses'][0]['InstanceState']['Name'] != 'running':
            time.sleep(1)
            specfic_state = self.get_specfic_instance_state(new_instance_id)
        #check again
        time.sleep(2)
        specfic_state = self.get_specfic_instance_state(new_instance_id)
        while specfic_state['InstanceStatuses'][0]['InstanceState']['Name'] != 'running':
            time.sleep(1)
            specfic_state = self.get_specfic_instance_state(new_instance_id)

        # register if it has finished initializing
        response = self.elb.register_targets(
            TargetGroupArn = self.TargetGroupArn,
            Targets=[
                {
                    'Id': new_instance_id,
                    'Port': 5000
                },
            ]
        )
        if response and 'ResponseMetadata' in response and \
                'HTTPStatusCode' in response['ResponseMetadata']:
            return response['ResponseMetadata']['HTTPStatusCode']
        else:
            return -1

    def grow_worker_by_ratio(self, ratio):
        """
        add one instance into the self.TargetGroupArn
        :return: msg: str
        """
        target_instances = self.get_valid_target_instances()
        design_instance_num = int(len(target_instances) * ratio)
        # max have 8 workers by auto-scaleer
        if design_instance_num > 8:
            register_targets_num = 8 - int(len(target_instances))
        else:
            register_targets_num = int(len(target_instances) * (ratio-1))
        response_list = []
        if register_targets_num <= 0:
            return "Invalid ratio, can have at most 8 workers"
        if len(target_instances) < 1:
            return "You have no target instance in your group yet."

        for i in range(register_targets_num):
            response_list.append(self.grow_worker_by_one())
        return response_list

    def shrink_worker_by_one(self):
        """
        shrink one instance into the self.TargetGroupArn
        :return: msg: str
        """
        target_instances_id = self.get_valid_target_instances()
        flag, msg = True, ''
        if len(target_instances_id) >= 1:
            unregister_instance_id = target_instances_id[0]

            # unregister instance from target group
            response1 = self.elb.deregister_targets(
                TargetGroupArn=self.TargetGroupArn,
                Targets=[
                    {
                        'Id': unregister_instance_id,
                        'Port': 5000
                    },
                ]
            )
            status1 = -1
            if response1 and 'ResponseMetadata' in response1 and \
                    'HTTPStatusCode' in response1['ResponseMetadata']:
                status1 = response1['ResponseMetadata']['HTTPStatusCode']

            if int(status1) == 200:
                #stop instance
                status2 = -1
                response2 = self.ec2.terminate_instances(InstanceIds=[unregister_instance_id])
                if response2 and 'ResponseMetadata' in response2 and \
                        'HTTPStatusCode' in response2['ResponseMetadata']:
                    status2 = response2['ResponseMetadata']['HTTPStatusCode']
                if int(status2) != 200:
                    flag = False
                    msg = "Unable to stop the unregistered instance"
            else:
                flag = False
                msg = "Unable to unregister from target group"

        else:
            flag = False
            msg = "No workers to unregister"

        return [flag, msg]
            
    def shrink_worker_by_ratio(self, ratio):
        """
        shrink one instance into the self.TargetGroupArn
        :return: msg: str
        """
        healthy_instances_id = self.get_healthy_instances()
        target_instances_id = self.get_valid_target_instances()
        response_list = []
        if ratio > 1:
            return [False, "Ratio should not be more than 1", response_list]
        elif len(healthy_instances_id) <= 1:
            return [False, "Target instance group has no more than one healthy instance and can not be shrinked", response_list]
        else:
            shrink_targets_num = len(target_instances_id) - ceil(len(target_instances_id) * round(ratio, 2))
            # minimum work pool set by auto-scaler is 1
            if shrink_targets_num == len(target_instances_id):
                shrink_targets_num = shrink_targets_num - 1
            for i in range(shrink_targets_num):
                response_list.append(self.shrink_worker_by_one())
        
        return [True, "Success", response_list]


    def get_cpu_utils(self, instance_id, start_time, end_time):
        response = self.cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[
                {
                    'Name': 'InstanceId',
                    'Value': instance_id
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=[
                'Maximum',
            ],
            Unit='Percent'
        )
        if 'Datapoints' in response:
            datapoints = []
            for datapoint in response['Datapoints']:
                datapoints.append([
                    int(datapoint['Timestamp'].timestamp() * 1000),
                    float(datapoint['Maximum'])
                ])
            return json.dumps(sorted(datapoints, key=lambda x: x[0]))
        else:
            return json.dumps([[]])

    ###Chart to show the http rates of ELB
    def fetch_http_rates(self, id):
        response = self.cloudwatch.get_metric_statistics(
            Namespace="AWS/ApplicationELB",
            MetricName="RequestCount",
            Dimensions=[
                {
                    "Name": "LoadBalancer",
                    "Value": "flaskr/1779test/0e341fbb39883284 "
                },
            ],
            StartTime=datetime.utcnow() - timedelta(seconds=30 * 60),
            EndTime=datetime.utcnow() - timedelta(seconds=0 * 60),
            Period=60,
            Statistics=["Sum"])

        http_rates_axis = []
        for point in response['Datapoints']:
            hour = point['Timestamp'].hour
            minute = point['Timestamp'].minute
            time = hour + minute/60
            http_rates_axis.append([time,point['Sum']])
        return http_rates_axis


    def fetch_request_rate_worker(self, instance_id, start_time, end_time):
        response = self.cloudwatch.get_metric_statistics(
            Period=60,
            StartTime=start_time,
            EndTime=end_time,
            MetricName='Request_Rate',
            Namespace='My_Service',  # Unit='Percent',
            Statistics=['Sum'],
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}]
        )

        # print(request_rate['Datapoints'])
        if 'Datapoints' in response:
            datapoints = []
            for point in response['Datapoints']:
                datapoints.append([
                    int(point['Timestamp'].timestamp() * 1000),
                    float(point['Sum'])
                ])
            return json.dumps(sorted(datapoints, key=lambda x: x[0]))
        else:
            return json.dumps([[]])


    def get_healthy_count(self,start_time=datetime.utcnow() - timedelta(seconds=30 * 60), end_time=datetime.utcnow() - timedelta(seconds=0 * 60)):
        response = self.cloudwatch.get_metric_statistics(
            Namespace='AWS/ApplicationELB',
            MetricName='HealthyHostCount',
            Dimensions=[
                {
                    'Name': 'TargetGroup',
                    'Value': self.targetgroup,
                },
                {
                    'Name': 'AvailabilityZone',
                    'Value':self.tag_placement['AvailabilityZone'],
                },
                {
                    'Name': 'LoadBalancer',
                    'Value': self.loadbalancer,
                },
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=[
                'Maximum',
            ],
            Unit='Count'
        )
        if 'Datapoints' in response:
            datapoints = []
            for datapoint in response['Datapoints']:
                datapoints.append([
                    int(datapoint['Timestamp'].timestamp() * 1000),
                    float(datapoint['Maximum'])
                ])
            print(datapoints)
            return json.dumps(sorted(datapoints, key=lambda x: x[0]))
        else:
            return json.dumps([[]])


    def clear_s3(self):
        imgsP = images.query.all()
        # print(imgsP)
        for image in imgsP:
            img = image.serialize()
            self.s3.delete_object(
                Bucket=self.bk,
                Key=img["path"],
            )

    def stop_user_instance(self):
        tag_insrances_id = self.get_tag_instances()
        response_list = []
        for item in tag_insrances_id:
            terminate_instances = self.ec2.terminate_instances(InstanceIds=[item['Id']])
            if terminate_instances and 'TerminatingInstances' in terminate_instances:
                response_list.append(terminate_instances)
        return [True, "Stop users success", response_list]

    # get manager instance
    def get_manager_instances(self):
        instances = []
        custom_filter = [{
            'Name': 'tag:Name',
            'Values': [self.manager_app_tag]}]
        response = self.ec2.describe_instances(Filters=custom_filter)
        #instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']
        reservations = response['Reservations']
        for reservation in reservations:
            if len(reservation['Instances']) > 0 and reservation['Instances'][0]['State']['Name'] != 'terminated':
                instances.append({
                    'Id': reservation['Instances'][0]['InstanceId'],
                    'State': reservation['Instances'][0]['State']['Name']
                })
        return instances

    ### Stop all managers
    def stop_manager_instances(self):
        manager_instances_id = self.get_manager_instances()
        response_list = []
        for item in manager_instances_id:
            self.ec2.stop_instances(
                InstanceIds=[item['Id']],
                Hibernate=False,
                Force=False
                )
            # if response2 and 'ResponseMetadata' in response2 and \
            #         'HTTPStatusCode' in response2['ResponseMetadata']:
            #     response_list.append(response2['ResponseMetadata']['HTTPStatusCode'])
        # return [True, "Stop managers success", response_list]

    def stop_all_instances(self):
        self.stop_user_instance()
        print('User terminated')
        self.stop_manager_instances()
        print('manager terminated')
        # return user_terminate[0] and manager_stop[0]


    def creat_and_regist_one_instance(self):
        response = self.create_ec2_instance()
        new_instance_id = response['InstanceId']

        specfic_state = self.get_specfic_instance_state(new_instance_id)
        while len(specfic_state['InstanceStatuses']) < 1:
            time.sleep(1)
            specfic_state = self.get_specfic_instance_state(new_instance_id)

        while specfic_state['InstanceStatuses'][0]['InstanceState']['Name'] != 'running':
            time.sleep(1)
            specfic_state = self.get_specfic_instance_state(new_instance_id)

        time.sleep(2)
        #check again
        specfic_state = self.get_specfic_instance_state(new_instance_id)
        while specfic_state['InstanceStatuses'][0]['InstanceState']['Name'] != 'running':
            time.sleep(1)
            specfic_state = self.get_specfic_instance_state(new_instance_id)

        # register if it has finished initializing
        response = self.elb.register_targets(
            TargetGroupArn = self.TargetGroupArn,
            Targets=[
                {
                'Id': new_instance_id,
                'Port': 5000
                },
            ])
        if response and 'ResponseMetadata' in response and 'HTTPStatusCode' in response['ResponseMetadata']:
            return response['ResponseMetadata']['HTTPStatusCode']
        else:
            return -1

    def initial_data(self):
        try:
            AutoScalingConfig.query.delete()
            db.session.commit()
            self.stop_user_instance()
            #self.stop_all_instances()
            images.query.delete()
            db.session.commit()
            self.clear_s3()
            self.creat_and_regist_one_instance()
            return [True, 'Initialization success']
        except Exception as e:
            print(e)
            traceback.print_tb(e.__traceback__)
            return [False, 'Unablr initialize the data']






if __name__ == '__main__':
    awscli = AwsClient()
    # print('grow_worker_by_one {}'.format(awscli.grow_worker_by_one()))
    # print('get_tag_instances:{}'.format(awscli.get_tag_instances()))
    print('get_target_instances:{}'.format(awscli.get_target_instances()))
    # print('get_idle_instances:{}'.format(awscli.get_idle_instances()))
    # print('grow_worker_by_one:{}'.format(awscli.grow_worker_by_one()))
    print('shrink_worker_by_one:{}'.format(awscli.shrink_worker_by_one()))
    # print('grow_worker_by_ratio:{}'.format(awscli.grow_worker_by_ratio(4)))
    # print('shrink_worker_by_ratio:{}'.format(awscli.shrink_worker_by_ratio(2)))
    # print('get_specfic_instance_state:{}'.format(awscli.get_specfic_instance_state('i-05d30395630a679bd')))
    # print('create_ec2_instances:{}'.format(awscli.create_ec2_instance()))
    print('get_valid_target_instances:{}'.format(awscli.get_valid_target_instances()))
    # print('stop_user_instance:{}'.format(awscli.stop_user_instance()))
    print('get_healthy_count.{}'.format(awscli.get_healthy_count()))
    # print('creat_and_regist_one_instance:{}'.format(awscli.creat_and_regist_one_instance()))


    
