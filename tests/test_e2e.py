import os
import time
import glob
import json
import functools
import subprocess


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


def wait_for_argocd_app_synced(app_name):
    check = functools.partial(check_argocd_app_synced, app_name)
    wait_for(check, 240, f'argocd app {app_name} did not sync')


def test():
    install_argocd('base')
    subprocess.check_call('kubectl config set-context --current --namespace=argocd', shell=True)
    wait_for_argocd_app_synced('tests-base')
    wait_for_argocd_app_synced('tests-base-production')
    wait_for_argocd_app_synced('tests-base-staging')

