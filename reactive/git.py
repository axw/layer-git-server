import os
import stat
import subprocess
import textwrap

from charmhelpers.core.hookenv import (
    local_unit,
    remote_service_name,
    status_set,
    storage_list,
    storage_get,
)

from charmhelpers.core import (
    host,
)

from charmhelpers.fetch import (
    apt_install,
)

from charms.reactive import (
    hook,
    when,
    when_not,
    set_state,
)


SSH_HOST_RSA_KEY = '/etc/ssh/ssh_host_rsa_key.pub'
AUTHORIZED_KEYS_COMMAND = 'scripts/update-authorized-keys'


@hook('install')
def install_git():
    apt_install('git')
    configure_sshd()
    host.service('restart', 'ssh')


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

    host.add_group(username)
    host.adduser(username, password=host.pwgen(32), shell='/usr/bin/git-shell')

    ssh_public_key = git.get_remote('ssh-public-key')
    dotssh_dir = '/home/{}/.ssh/'.format(username)
    host.mkdir(dotssh_dir, username, username, 0o700)
    host.write_file(dotssh_dir + 'authorized_keys',
                    ssh_public_key.encode('utf-8'),
                    username, username, 0o400)

    host.mkdir(repo_path, group=username, perms=0o770)
    subprocess.check_call(['git', 'init', '--bare', '--shared=group', repo_path])

    # Create server-side hook that will inform
    # clients whenever changes are committed.
    create_git_hooks(repo_path, username)

    # Make the repo owned by <username>.
    chown_repo(repo_path, username)

    # TODO(axw) read and publish all host keys.
    ssh_host_keys = [open(SSH_HOST_RSA_KEY).read()]
    git.configure(repo_path, ssh_host_keys)
    set_state('git.repo.created')
    status_set('active', '')


def create_git_hooks(repo, owner):
    """
    create_git_hooks creates server-side hooks for the git repository.

    Currently, we create only a post-receive hook which will run the
    "scripts/set-commit" script in the hook context of the unit. The
    script will set the "git-commit" relation setting for each connected
    client unit.
    """

    hook = os.path.join(repo, 'hooks', 'post-receive')
    content = textwrap.dedent("""\
    #!/bin/sh
    set -e
    while read oldrev newrev ref
    do
        if test "$ref"="ref/heads/master"; then
            juju-run {} "scripts/set-commit $newrev"
        fi
    done
    """.format(local_unit()))
    host.write_file(hook, content.encode('utf-8'), owner, owner, 0o700)


def configure_sshd():
    """
    configure_sshd will ensure that sshd looks in .ssh/admin_authorized_keys
    as well as the usual .ssh/authorized_keys.
    """

    # TODO(axw) flock sshd_config
    # TODO(axw) just use a Match directive with Group=<remote-service>

    authorized_keys_command = os.path.abspath(AUTHORIZED_KEYS_COMMAND)
    os.chown(authorized_keys_command, 0, 0) # chown to root:root
    os.chmod(authorized_keys_command, 0o700)
    sshd_config = '/etc/ssh/sshd_config'
    lines = [
        'AuthorizedKeysFile        %h/.ssh/authorized_keys %h/.ssh/admin_authorized_keys',
        'AuthorizedKeysCommand     {}'.format(authorized_keys_command),
        'AuthorizedKeysCommandUser root',
    ]
    with open(sshd_config, 'a') as f:
        f.writelines((l+'\n' for l in lines))


def chown_repo(repo_path, owner):
    # TODO(axw) use os.walk?
    subprocess.check_call(['chown', '-R', owner, repo_path])


def repo_root():
    return storage_get('location', storage_list('repo-root')[0])

