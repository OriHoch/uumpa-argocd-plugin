import os
import time
import glob
import json
import base64
import functools
import subprocess
import contextlib
from textwrap import dedent


def wait_for(check, seconds, msg='Timeout expired'):
    for i in range(seconds):
        if check():
            return
        time.sleep(1)
    raise Exception(msg)


def check_argocd_repo_server():
    pods = json.loads(subprocess.check_output('kubectl -n argocd get pods -lapp.kubernetes.io/name=argocd-repo-server -o json', shell=True))['items']
    if len(pods) != 1:
        return False
    pod = pods[0]
    if pod['status']['phase'] != 'Running':
        return False
    for container in pod['status']['containerStatuses']:
        if not container['ready']:
            return False
    return True


def wait_for_argocd_repo_server():
    wait_for(check_argocd_repo_server, 120, 'argocd-repo-server did not start')


def wait_for_argocd_crds():
    wait_for(lambda: 'applications.argoproj.io' in subprocess.check_output('kubectl api-resources -o name', shell=True).decode('utf-8'), 120, 'argocd CRDs did not install')


def install_argocd(argocd_kustomize_dir):
    subprocess.run(['kubectl', 'apply', '-f', '-'], text=True, check=True, input=json.dumps({
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": 'argocd'}
    }))
    subprocess.check_call(['kubectl', 'apply', '-n', 'argocd', '-k', os.path.join('kustomize', 'tests', 'argocd', argocd_kustomize_dir)])
    wait_for_argocd_repo_server()
    wait_for_argocd_crds()
    for path in glob.glob(os.path.join('kustomize', 'tests', 'argocd', argocd_kustomize_dir, 'namespaces', '*')):
        namespace = path.split('/')[-1]
        if namespace != "default":
            subprocess.run(['kubectl', 'apply', '-f', '-'], text=True, check=True, input=json.dumps({
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": namespace}
            }))
        if os.path.exists(os.path.join(path, 'kustomization.yaml')):
            subprocess.check_call(['kubectl', 'apply', '-n', namespace, '-k', path])
    for path in glob.glob(os.path.join('kustomize', 'tests', 'argocd', argocd_kustomize_dir, 'apps', '*.yaml')):
        subprocess.check_call(['kubectl', 'apply', '-n', 'argocd', '-f', path])


def check_argocd_app_synced(app_name):
    return json.loads(subprocess.check_output(f'argocd --core app get -o json {app_name}', shell=True))['status']['sync']['status'] == 'Synced'


def argocd_app_git_hard_refresh_sync(app_name):
    subprocess.check_call(f'argocd app diff --hard-refresh --exit-code=false {app_name}', shell=True)
    subprocess.check_call(f'argocd app sync {app_name}', shell=True)
    check = functools.partial(check_argocd_app_synced, app_name)
    wait_for(check, 240, f'argocd app {app_name} did not sync')


@contextlib.contextmanager
def argocd_login():
    subprocess.check_call('kubectl config set-context --current --namespace=argocd', shell=True)
    if os.environ.get('ARGOCD_PORT_FORWARD_PORT'):
        port = os.environ['ARGOCD_PORT_FORWARD_PORT']
        port_forward = None
    else:
        port = '8080'
        cmd = ['kubectl', 'port-forward', 'svc/argocd-server', '-n', 'argocd', '8080:443']
        port_forward = None
        port_forward_exists = False
        if os.environ.get('ARGOCD_PORT_FORWARD_KEEP'):
            for line in subprocess.check_output(['ps', 'aux']).decode('utf-8').splitlines():
                if ' '.join(cmd) in line:
                    port_forward_exists = True
                    break
            if not port_forward_exists:
                port_forward = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
    password = None
    try:
        password = base64.b64decode(
            json.loads(
                subprocess.check_output('kubectl get secret argocd-initial-admin-secret -o json', shell=True)
            )['data']['password'].encode()
        ).decode()
        subprocess.check_call(f'argocd login --insecure localhost:{port} --username admin --password {password}', shell=True)
        yield
    finally:
        if os.environ.get('ARGOCD_PORT_FORWARD_KEEP'):
            print('Keeping port-forward running for debugging')
            print(f'Login to argocd at http://localhost:{port} with username "admin" and password "{password}"')
        elif port_forward:
            print('Killing port-forward, to keep it running set env var ARGOCD_PORT_FORWARD_KEEP=1')
            port_forward.kill()


def argocd_update_git():
    subprocess.check_call(['kubectl', 'exec', 'deploy/git', '--', 'bash', '-c', dedent('''
        mkdir -p /git/uumpa-argocd-plugin &&\
        cp -r /uumpa-argocd-plugin/* /git/uumpa-argocd-plugin/ &&\
        cd /git/uumpa-argocd-plugin &&\
        git init -b main &&\
        git config user.email root@localhost &&\
        git config user.name root &&\
        git add . &&\
        git commit -m "Initial commit"
    ''')])


def test():
    install_argocd('base')
    with argocd_login():
        argocd_update_git()
        argocd_app_git_hard_refresh_sync('tests-base')
        argocd_app_git_hard_refresh_sync('tests-base-production')
        argocd_app_git_hard_refresh_sync('tests-base-staging')
        actual_configmap = json.loads(subprocess.check_output('kubectl -n tests-base get configmap main-app-config -o json', shell=True))['data']
        alertmanager_secret_auth_user, alertmanager_secret_auth_encrypted_password = actual_configmap['alertmanager_secret.auth'].split(':')
        assert alertmanager_secret_auth_user == 'admin'
        assert len(alertmanager_secret_auth_encrypted_password) > 10
        alertmanager_secret_json = actual_configmap['alertmanager_secret']
        alertmanager_secret = json.loads(alertmanager_secret_json)
        alertmanager_secret_password = actual_configmap['alertmanager_secret.password']
        assert alertmanager_secret == {
            "auth": f"{alertmanager_secret_auth_user}:{alertmanager_secret_auth_encrypted_password}",
            "password": alertmanager_secret_password
        }
        user_json = actual_configmap.pop('user')
        user = json.loads(user_json)
        assert set(user.keys()) == {'name', 'password'}
        assert user['name'] == 'admin'
        assert len(user['password']) > 8
        assert actual_configmap.pop('nfs_initialized') in {'', 'true'}
        expected_configmap = {
            'ARGOCD_ENV_ALERTMANAGER_USER': 'admin',
            'ARGOCD_ENV_DOMAIN_SUFFIX': 'local.example.com',
            'ARGOCD_ENV_ENVIRONMENT': '',
            'ARGOCD_ENV_HELM_ARGS': '--values my-values.yaml --values my-other-values.yaml',
            'ARGOCD_ENV_INIT_HELM_DEPENDENCY_BUILD': '~ARGOCD_ENV_INIT_HELM_DEPENDENCY_BUILD~',
            'ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS': '~ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS~',
            'DOMAIN_SUFFIX': 'global.example.com',
            'alertmanager_domain': 'alertmanager.local.example.com',
            'alertmanager_secret': alertmanager_secret_json,
            'alertmanager_secret.auth': f'{alertmanager_secret_auth_user}:{alertmanager_secret_auth_encrypted_password}',
            'alertmanager_secret.password': alertmanager_secret_password,
            'alertmanager_user': 'admin',
            'domain_suffix_global': 'global.example.com',
            'domain_suffix_local': 'local.example.com',
            'helm_values_hello': 'world',
            'helm_values_world': 'hello',
            'nfs_ip': '1.2.3.4',
            'server': '',
            'user.name': 'admin',
            'user.password': user['password'],
            'user_auth': f'admin:{user["password"]}'
        }
        assert actual_configmap == expected_configmap
