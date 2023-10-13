import functools
import os
import time
import glob
import json
import base64
import subprocess
from textwrap import dedent


PORT_FORWARD = None
PORT_FORWARD_PORT = None
ARGOCD_PASSWORD = None


def check_argocd_login():
    global PORT_FORWARD_PORT, ARGOCD_PASSWORD
    return subprocess.call(f'argocd login --insecure localhost:{PORT_FORWARD_PORT} --username admin --password {ARGOCD_PASSWORD}', shell=True) == 0


def argocd_login():
    global PORT_FORWARD, PORT_FORWARD_PORT, ARGOCD_PASSWORD
    subprocess.check_call('kubectl config set-context --current --namespace=argocd', shell=True)
    if os.environ.get('ARGOCD_PORT_FORWARD_PORT'):
        PORT_FORWARD_PORT = os.environ['ARGOCD_PORT_FORWARD_PORT']
    else:
        PORT_FORWARD_PORT = '8080'
        cmd = ['kubectl', 'port-forward', 'svc/argocd-server', '8080:443']
        port_forward_exists = False
        if os.environ.get('ARGOCD_PORT_FORWARD_KEEP'):
            for line in subprocess.check_output(['ps', 'aux']).decode('utf-8').splitlines():
                if ' '.join(cmd) in line:
                    port_forward_exists = True
                    break
        if not port_forward_exists:
            PORT_FORWARD = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ARGOCD_PASSWORD = base64.b64decode(
        json.loads(
            subprocess.check_output('kubectl get secret argocd-initial-admin-secret -o json', shell=True)
        )['data']['password'].encode()
    ).decode()
    wait_for(check_argocd_login, 120, 'failed to login to argocd')


def argocd_login_cleanup():
    global PORT_FORWARD, PORT_FORWARD_PORT, ARGOCD_PASSWORD
    if os.environ.get('ARGOCD_PORT_FORWARD_KEEP'):
        print('Keeping port-forward running for debugging')
        print(f'Login to argocd at http://localhost:{PORT_FORWARD_PORT} with username "admin" and password "{ARGOCD_PASSWORD}"')
    elif PORT_FORWARD:
        print('Killing port-forward, to keep it running set env var ARGOCD_PORT_FORWARD_KEEP=1')
        PORT_FORWARD.kill()


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
    wait_for(git_pod_ready, 120, 'git pod did not start')
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
    for path in glob.glob(os.path.join('kustomize', 'tests', 'argocd', argocd_kustomize_dir, 'apps', '*.yaml')):
        subprocess.check_call(['kubectl', 'apply', '-n', 'argocd', '-f', path])
    subprocess.check_call('kubectl apply -n default -k kustomize/tests/argocd/base/namespaces/default', shell=True)
