import ConfigParser
import logging

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


def initial_deployment():
    with settings(warn_only=True):
        result = run('docker info')
        if result.failed:
            sudo('yum install -y docker')
            sudo('sudo service docker start')
            sudo('sudo usermod -a -G docker ec2-user')

    # sudo('yum install -y git')
    if not exists('bbc_tool', verbose=True):
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
