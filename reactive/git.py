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

from charmhelpers.core.templating import render
from charmhelpers.core.host import (
    adduser,
    service_restart,
    service_running,
    service_start,
)

from charmhelpers.fetch import (
    apt_install,
    install_remote,
)

from charms.reactive import (
    hook,
    when,
    when_not,
    is_state,
    set_state,
    remove_state,
)


@when('git.available')
@when_not('git.username.available')
def wait_username():
    status_set('waiting', 'Waiting for client username')


@when('git.available')
@when_not('git.public-key.available')
def wait_public_key():
    status_set('waiting', 'Waiting for client public key')


@when('git.username.available', 'git.public-key-available')
@when_not('git.repo.created')
def create_repo(git):
    repo_path = create_repo(repo_name,
                            git.get_remote('username'),
                            git.get_remote('public-key'))
    git.configure(repo_path)
    set_state('git.repo.created')


def create_repo(repo_name, username, public_key):
    service = remote_service_name()
    repo_path = os.path.join(repo_root(), service+'.git')
    host.add_group(service)
    host.adduser(service, password=password, shell='/usr/bin/git-shell')
    host.add_user_to_group(service, service)
    # TODO(axw) write public key to ~user/.ssh/authorized_keys
    host.mkdir(repo_path, group=service, perms=0o770)
    subprocess.check_call([
        'git', 'init', '--bare', '--shared=group', repo_path,
    ])
    return repo_path


def repo_root():
    return storage_get('location', storage_list('repo-root')[0])


