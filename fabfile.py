import boto3
import ConfigParser
import logging

import boto3
import time
from fabric.api import *
from fabric.contrib.files import exists

CONFIG_FILE = "settings.cfg"
config = ConfigParser.RawConfigParser()
config.read(CONFIG_FILE)

env.forward_agent = True
env.update(config._sections['ec2'])
env.hosts = [config.get('ec2', 'host')]


def update():
    with cd('bbc_tool'):
        run('git pull')


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

container_state = {'RUNNING': 1, 'STOPPED': 2, 'NOT_FOUND': 3}


def create_instance():
    print('creating instance')
    ec2 = boto3.resource('ec2')

    instances = ec2.create_instances(

        ImageId='ami-e1398992',
        MinCount=1,
        MaxCount=1,
        KeyName='ep-host',
        # SecurityGroups=['sg-e78fbc83',],
        # sg-e78fbc83
        # 'sg2',  # sg-e78fbc83
        SecurityGroupIds=['sg-e78fbc83'],

        InstanceType='m4.large',
        # | 'm1.large'
        # 't1.micro',

        Placement={
            'AvailabilityZone': 'eu-west-1a',
            # 'GroupName': 'string',
            # 'Tenancy': 'default' | 'dedicated' | 'host',
            # 'HostId': 'string',
            # 'Affinity': 'string'
        },
        # KernelId='string',
        # RamdiskId='string',
        BlockDeviceMappings=[
            {
                # 'VirtualName': 'string',
                'DeviceName': '/dev/xvda',
                'Ebs': {
                    'SnapshotId': 'snap-7d042fb4',
                    'VolumeSize': 8,
                    'DeleteOnTermination': True,
                    'VolumeType': 'gp2',
                    # 'Iops': 24,
                    # 'Encrypted': False
                },

            },
        ],
        # Monitoring={
        #     # True |
        #     'Enabled': False
        # },
        # SubnetId='string',
        # DisableApiTermination=True | False,
        # InstanceInitiatedShutdownBehavior='stop',
        # PrivateIpAddress='string',
        # ClientToken='string',
        # AdditionalInfo='string',
        # NetworkInterfaces=[
        #     {
        #         'NetworkInterfaceId': 'string',
        #         'DeviceIndex': 123,
        #         'SubnetId': 'string',
        #         'Description': 'string',
        #         'PrivateIpAddress': 'string',
        #         'Groups': [
        #             'string',
        #         ],
        #         'DeleteOnTermination': True | False,
        #         'PrivateIpAddresses': [
        #             {
        #                 'PrivateIpAddress': 'string',
        #                 'Primary': True | False
        #             },
        #         ],
        #         'SecondaryPrivateIpAddressCount': 123,
        #         'AssociatePublicIpAddress': True | False
        #     },
        # ],
        # 'Arn': 'string',
        IamInstanceProfile={'Name': 'ec2_default_instance_role'},
        EbsOptimized=True | False
    )
    iid = instances[0].id

    # give the instance a tag name
    ec2.create_tags(
        Resources=[iid],
        Tags=mktag(env.notebook_server_tag)
    )

    # instance = start_instance(instances[0])

    # env.user = config.get('ec2', 'USER')
    # return instance


def assert_running(instance):
    if instance.state['Name'] != "running":

        print "Firing up instance"
        instance.start()
        # Give it 10 minutes to appear online
        for i in range(120):
            time.sleep(5)
            instance.update()
            print instance.state
            if instance.state['Name'] != "running":
                break

    if instance.state['Name'] == "running":
        dns = instance.public_dns_name
        print "Instance up and running at %s" % dns

        config.set('ec2', 'host', dns)
        config.set('ec2', 'instance', instance.id)
        # config.write(CONFIG_FILE)
        print "updating env.hosts"
        env.hosts = [dns, ]
        print env.hosts
        # Writing our configuration file to 'example.cfg'
        with open(CONFIG_FILE, 'wb') as configfile:
            config.write(configfile)

    return instance


def mktag(val):
    return [{'Key': 'Name', 'Value': val}]


def assert_instance():
    ec2 = boto3.resource('ec2')
    instances = ec2.instances.filter(
        Filters=[{'Name': 'tag:Name', 'Values': [env.notebook_server_tag]},
                 # {'Name': 'instance-state-name', 'Values': ['running']}
                 ])
    instance_list = [instance for instance in instances]
    if len(instance_list) == 0:
        print('not existing, will create')
        create_instance()
    else:
        assert_running(instance_list[0])


def get_id_from_tag(ec2obj, tag):
    for o in ec2obj.filter(Filters=[{'Name': 'tag:Name', 'Values': [tag]}]):
        return o.id

    return None


def initial_deployment():
    print('checking instance')
    assert_instance()
    print env.hosts
    with settings(warn_only=True):
        result = run('docker info')
        if result.failed:
            sudo('yum install -y docker')
            sudo('sudo service docker start')
            sudo('sudo usermod -a -G docker ec2-user')

    # sudo('yum install -y git')
    if not exists('bbc_tool', verbose=True):
        sudo('yum install -y git')
        run('git clone git@bitbucket.org:dschien/bbc_tool.git')
    else:
        update()

    build_container()
    run_container()


def run_container():
    cmd = 'docker run -d -p 8888:8888 -v $(pwd):/home/jovyan/work -e PASSWORD="%s" -e USE_HTTPS=yes dschien/nb' % \
          env.nb_password
    with cd('bbc_tool'):
        run(cmd)


def build_container():
    with cd('bbc_tool/docker'):
        run('docker build -t dschien/nb .')


def inspect_container(container_name_or_id=''):
    """ e.g. fab --host ep.iodicus.net inspect_container:container_name_or_id=... """
    with settings(warn_only=True):
        result = run("docker inspect --format '{{ .State.Running }}' " + container_name_or_id)
        running = (result == 'true')
    if result.failed:
        logger.warn('inspect_container failed for container {}'.format(container_name_or_id))
        return container_state['NOT_FOUND']
    if not running:
        logger.info('container {} stopped'.format(container_name_or_id))
        return container_state['STOPPED']
    logger.info('container {} running'.format(container_name_or_id))
    return container_state['RUNNING']


def stop_container(container_name_or_id=''):
    with settings(warn_only=True):
        result = run("docker stop " + container_name_or_id)
        if not result.failed:
            logger.info('container {} stopped'.format(container_name_or_id))


def remove_container(container_name_or_id=''):
    with settings(warn_only=True):
        result = run("docker rm " + container_name_or_id)
        if result == container_name_or_id:
            logger.info('container {} removed'.format(container_name_or_id))
        else:
            logger.warn('unexpect command result, check log output')


def docker_logs(container_name_or_id=''):
    with settings(warn_only=True):
        run('docker logs --tail 50 -f {}'.format(container_name_or_id))


def redeploy_container(container_name_or_id=''):
    """ e.g. fab --host ep.iodicus.net inspect_container:container_name_or_id=... """
    state = inspect_container(container_name_or_id)
    if state == container_state['RUNNING']:
        stop_container(container_name_or_id)
    remove_container(container_name_or_id)
    run_container()


def update_site():
    """
    Pull from git and restart docker containers
    :return:
    """
    update()

    for container in ['dschien/nb']:
        redeploy_container(container)
