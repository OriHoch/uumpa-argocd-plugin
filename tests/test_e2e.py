import os
import json
import functools
import subprocess

from .common import wait_for


def check_argocd_app_synced(app_name):
    return json.loads(subprocess.check_output(f'argocd app get -o json {app_name}', shell=True))['status']['sync']['status'] == 'Synced'


def argocd_app_terminate_op(app_name):
    return subprocess.call(f'argocd app terminate-op {app_name}', shell=True) == 20


def argocd_app_git_hard_refresh_sync(app_name):
    subprocess.check_call(f'kubectl delete ns {app_name} --ignore-not-found --wait', shell=True)
    subprocess.check_call(f'kubectl create ns {app_name}', shell=True)
    if app_name != 'tests-base':
        subprocess.check_call(f'kubectl apply -n {app_name} -k kustomize/tests/argocd/base/namespaces/{app_name}', shell=True)
    subprocess.check_call(f'kubectl delete job -lapp.kubernetes.io/instance={app_name} --ignore-not-found --wait', shell=True)
    subprocess.check_call(f'argocd app diff --hard-refresh --exit-code=false {app_name}', shell=True)
    wait_for(functools.partial(argocd_app_terminate_op, app_name), 60, f'argocd app {app_name} did not terminate')
    subprocess.check_call(f'argocd app sync {app_name} --force --assumeYes --prune', shell=True)
    check = functools.partial(check_argocd_app_synced, app_name)
    wait_for(check, 240, f'argocd app {app_name} did not sync')


def assert_argocd_app_configmap(name, expected_configmap_changes):
    actual_configmap = json.loads(
        subprocess.check_output(f'kubectl -n {name} get configmap main-app-config -o json', shell=True)
    )['data']
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
        'user_auth': f'admin:{user["password"]}',
        'nfs_initialized': '',
        **expected_configmap_changes
    }
    assert actual_configmap == expected_configmap


def assert_argocd_app_job(name, expected_nfs_init_job, expected_nfs_init_configmap):
    jobs = json.loads(subprocess.check_output(f'kubectl get job -l app.kubernetes.io/instance={name} -o json', shell=True))['items']
    if expected_nfs_init_job:
        assert len(jobs) == 1
        job = jobs[0]
        assert job['status']['succeeded'] == 1
        job_name = job['metadata']['name']
        pods = json.loads(subprocess.check_output(f'kubectl get pod -l job-name={job_name} -o json', shell=True))['items']
        assert len(pods) == 1
        pod = pods[0]
        assert pod['status']['phase'] == 'Succeeded'
        pod_name = pod['metadata']['name']
        logs = subprocess.check_output(f'kubectl logs {pod_name}', shell=True, text=True)
        logs = logs.split('~~~~~~~~~~')
        assert len(logs) == 4
        assert logs[0].strip() == 'Hello from nfs init.sh', logs
        assert logs[1].strip().startswith('/tmp/') and logs[1].strip().endswith('/.NFS_ID_RSA'), logs
        assert logs[2].strip() == '---- NFS ID RSA ----', logs
        assert logs[3].strip() == f'configmap/nfs-init {expected_nfs_init_configmap}\nrunning subgenerators...', logs
    else:
        assert len(jobs) == 0


def assert_argocd_app(name, expected_configmap_changes=None, expected_testdep_source='tgz',
                      expected_nfs_init_job=True, expected_nfs_init_configmap='created'):
    try:
        assert_argocd_app_configmap(name, expected_configmap_changes or {})
        assert expected_testdep_source == json.loads(subprocess.check_output(
            f'kubectl -n {name} get configmap testdep -o json', shell=True
        ))['data']['source']
        assert_argocd_app_job(name, expected_nfs_init_job, expected_nfs_init_configmap)
    except Exception as e:
        raise Exception(f'Failed to assert argocd app {name}') from e


def test_base(argocd):
    argocd_app_git_hard_refresh_sync('tests-base')
    assert_argocd_app('tests-base')


def test_base_production(argocd):
    argocd_app_git_hard_refresh_sync('tests-base-production')
    assert_argocd_app(
        'tests-base-production',
        expected_configmap_changes={
            'ARGOCD_ENV_ENVIRONMENT': 'production',
            'ARGOCD_ENV_HELM_ARGS': '-f values.production.yaml',
            'helm_values_hello': '',
            'helm_values_world': '',
            'nfs_ip': '1.2.3.4',
            'server': 'my-production',
        },
        expected_nfs_init_configmap='configured'
    )


def test_base_staging(argocd):
    argocd_app_git_hard_refresh_sync('tests-base-staging')
    assert_argocd_app(
        'tests-base-staging',
        expected_configmap_changes={
            'ARGOCD_ENV_ENVIRONMENT': 'staging',
            'ARGOCD_ENV_HELM_ARGS': '-f values.staging.yaml',
            'ARGOCD_ENV_INIT_HELM_DEPENDENCY_BUILD': 'true',
            'ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS': 'init_helm',
            'helm_values_hello': '',
            'helm_values_world': '',
            'nfs_ip': '1.2.3.4',
            'nfs_initialized': 'true',
            'server': 'my-staging',
        },
        expected_testdep_source='chart',
        expected_nfs_init_job=False
    )
