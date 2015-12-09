import os
import yaml
import subprocess

from charmhelpers.core.hookenv import (
    remote_service_name,
    status_set,
    open_port,
    config,
    storage_list,
    storage_get,
)

from charmhelpers.core import host

from charmhelpers.fetch import (
    apt_install,
)

from charms.reactive import (
    hook,
    when,
    when_not,
    set_state,
    remove_state,
)


SSH_HOST_RSA_KEY = '/etc/ssh/ssh_host_rsa_key.pub'


@hook('install')
def install_git():
    apt_install('git')


@when('git.available')
@when_not('git.client.ready')
def wait_username(git):
    status_set('waiting', 'Waiting for client to be ready')


@when('git.client.ready')
@when_not('git.repo.created')
def create_repo(git):
    username = git.get_remote('username')
    service = remote_service_name()
    repo_path = os.path.join(repo_root(), service+'.git')
    host.add_group(service)
    # TODO(axw) generate long, random password
    host.adduser(service, password='hunter2', shell='/usr/bin/git-shell')
    host.add_user_to_group(service, service)

    ssh_public_key = git.get_remote('ssh-public-key')
    dotssh_dir = '/home/{}/.ssh/'.format(service)
    host.mkdir(dotssh_dir, service, service, 0o700)
    host.write_file(dotssh_dir + 'authorized_keys', ssh_public_key, service, service, 0o400)

    host.mkdir(repo_path, group=service, perms=0o770)
    subprocess.check_call(['git', 'init', '--bare', '--shared=group', repo_path])

    ssh_host_key = open(SSH_HOST_RSA_KEY).read()
    git.configure(repo_path, ssh_host_key)
    set_state('git.repo.created')
    status_set('active', '')


def repo_root():
    # TODO(axw) when reactive support for storage is fixed, use
    # storage.
    # return storage_get('location', storage_list('repo-root')[0])
    path = os.path.abspath('repo-root')
    if not os.path.exists(path):
        os.makedirs(path)
    return path

