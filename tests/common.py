import os
import time
import glob
import json
import base64
import traceback
import functools
import subprocess
import contextlib
from textwrap import dedent


def check_argocd_login(argocd_password):
    return subprocess.call(f'argocd login --insecure localhost:8080 --username admin --password {argocd_password}', shell=True) == 0


def vault_port_forward_start(finalizers, messages):
    cmd = ['kubectl', '-n', 'vault', 'port-forward', 'svc/vault', '8200:8200']
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    root_token = subprocess.check_output('kubectl -n vault exec deploy/vault -- cat /tmp/root_token', shell=True, text=True).strip()
    finalizers.append(process.kill)
    messages.append(f'Login to vault at http://localhost:8200 with root token "{root_token}"')


def port_forward_start(finalizers, host_port, target_port, namespace, target):
    cmd = ['kubectl', '-n', namespace, 'port-forward', target, f'{host_port}:{target_port}']
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finalizers.append(process.kill)


def argocd_login(finalizers, messages):
    subprocess.check_call('kubectl config set-context --current --namespace=argocd', shell=True)
    cmd = ['kubectl', 'port-forward', 'svc/argocd-server', '8080:443']
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    password = base64.b64decode(
        json.loads(
            subprocess.check_output('kubectl get secret argocd-initial-admin-secret -o json', shell=True)
        )['data']['password'].encode()
    ).decode()
    wait_for(functools.partial(check_argocd_login, password), 120, 'failed to login to argocd')
    finalizers.append(process.kill)
    messages.append(f'Login to argocd at http://localhost:8080 with username "admin" and password "{password}"')


def git_pod_ready():
    pods = json.loads(subprocess.check_output('kubectl get pods -lapp=git -o json', shell=True))['items']
    if len(pods) != 1:
        return False
    pod = pods[0]
    if pod['status']['phase'] != 'Running':
        return False
    for container in pod['status']['containerStatuses']:
        if not container['ready']:
            return False
    return True


def argocd_update_git():
    print('Waiting for git pod to start...')
    wait_for(git_pod_ready, 120, 'git pod did not start')
    print('Setting up argocd local git repo')
    subprocess.check_call(['kubectl', 'exec', 'deploy/git', '--', 'bash', '-c', dedent('''
        rm -rf /git/uumpa-argocd-plugin &&\
        mkdir -p /git/uumpa-argocd-plugin &&\
        cp -r /uumpa-argocd-plugin/* /git/uumpa-argocd-plugin/ &&\
        cp /uumpa-argocd-plugin/.gitignore /git/uumpa-argocd-plugin/ &&\
        cd /git/uumpa-argocd-plugin &&\
        git init -b main &&\
        git config user.email root@localhost &&\
        git config user.name root &&\
        git add . &&\
        git commit -m "Initial commit"
    ''')])


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
    print('Waiting for argocd-repo-server to start...')
    wait_for(check_argocd_repo_server, 120, 'argocd-repo-server did not start')


def wait_for_argocd_crds():
    print('Waiting for argocd CRDs to install...')
    wait_for(lambda: 'applications.argoproj.io' in subprocess.check_output('kubectl api-resources -o name', shell=True).decode('utf-8'), 120, 'argocd CRDs did not install')


def install_argocd(argocd_kustomize_dir):
    print('create argocd namespace')
    subprocess.run(['kubectl', 'apply', '-f', '-'], text=True, check=True, input=json.dumps({
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": 'argocd'}
    }))
    print('install argocd')
    subprocess.check_call(['kubectl', 'apply', '-n', 'argocd', '-k', os.path.join('kustomize', 'tests', 'argocd', argocd_kustomize_dir)])
    wait_for_argocd_repo_server()
    wait_for_argocd_crds()
    for path in glob.glob(os.path.join('kustomize', 'tests', 'argocd', argocd_kustomize_dir, 'apps', '*.yaml')):
        print(f'installing manifests from {path}')
        subprocess.check_call(['kubectl', 'apply', '-n', 'argocd', '-f', path])


def verify_argocd_app_synced(app_name):
    return json.loads(subprocess.check_output(f'argocd app get -o json {app_name}', shell=True))['status']['sync']['status'] == 'Synced'


def verify_argocd_app_healthy(app_name):
    return json.loads(subprocess.check_output(f'argocd app get -o json {app_name}', shell=True))['status']['health']['status'] == 'Healthy'


def argocd_app_terminate_op(app_name):
    return subprocess.call(f'argocd app terminate-op {app_name}', shell=True) == 20


def argocd_app_diff_sync(app_name):
    print(f'argocd_app_diff_sync: {app_name}')
    subprocess.check_call(f'argocd app diff --hard-refresh --exit-code=false {app_name}', shell=True)
    print(f'Waiting for argocd app {app_name} to terminate any previous op...')
    wait_for(functools.partial(argocd_app_terminate_op, app_name), 60, f'argocd app {app_name} did not terminate')
    subprocess.check_call(f'argocd app sync {app_name} --force --assumeYes --prune', shell=True)
    print(f'Waiting for argocd app {app_name} to sync...')
    wait_for(functools.partial(verify_argocd_app_synced, app_name), 10, f'argocd app {app_name} did not sync')
    print(f'Waiting for argocd app {app_name} to be healthy...')
    wait_for(functools.partial(verify_argocd_app_healthy, app_name), 120, f'argocd app {app_name} did not become healthy')


@contextlib.contextmanager
def start_infra(with_observability=False, build=False, skip_create_cluster=False):
    finalizers = []
    messages = []
    try:
        if not skip_create_cluster:
            subprocess.check_call('kind delete cluster', shell=True)
            subprocess.check_call('cat tests/kind.yaml.envsubst | envsubst > tests/kind.yaml', shell=True)
            subprocess.check_call('kind create cluster --config tests/kind.yaml --wait 240s', shell=True)
        if build:
            load_image = 'ghcr.io/orihoch/uumpa-argocd-plugin/plugin:latest'
            subprocess.check_call(f'docker build -t {load_image} .', shell=True)
            if with_observability:
                load_image = 'ghcr.io/orihoch/uumpa-argocd-plugin/plugin-with-observability:latest'
                subprocess.check_call(f'docker build -t {load_image} -f Dockerfile.observability .', shell=True)
            subprocess.check_call(f'kind load docker-image {load_image}', shell=True)
            if skip_create_cluster:
                subprocess.call('kubectl -n argocd delete deployment argocd-repo-server', shell=True)
        if with_observability and subprocess.call('kubectl get -n observability svc/jaeger-collector', shell=True) == 0:
            base_app = 'base_observability'
        else:
            base_app = 'base'
        install_argocd(base_app)
        argocd_login(finalizers, messages)
        argocd_update_git()
        print('Deleting existing Vault init job if exists')
        subprocess.check_call(f'kubectl delete job -lapp.kubernetes.io/instance=vault --ignore-not-found --wait', shell=True)
        argocd_app_diff_sync('vault')
        argocd_app_diff_sync('default')
        vault_port_forward_start(finalizers, messages)
        if with_observability:
            argocd_app_diff_sync('cert-manager')
            argocd_app_diff_sync('jaeger-operator')
            argocd_app_diff_sync('jaeger')
            port_forward_start(finalizers,'16686', '16686', 'observability', 'svc/jaeger-query')
            messages.append('login to Jaeger UI at http://localhost:16686')
            port_forward_start(finalizers, '4317', '4317', 'observability', 'svc/jaeger-collector')
            messages.append('Set Jaeger grpc backend to http://localhost:4317')
            if base_app == 'base':
                install_argocd('base_observability')
        print('\n'.join(messages))
        yield
    finally:
        for finalizer in finalizers:
            try:
                finalizer()
            except Exception:
                traceback.print_exc()
                print(f'Failed to run finalizer: {finalizer.__name__}')
