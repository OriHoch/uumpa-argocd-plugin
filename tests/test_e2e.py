import base64
import json
import subprocess

from .common import argocd_app_diff_sync


def argocd_app_git_hard_refresh_sync(app_name):
    subprocess.check_call(f'kubectl delete ns {app_name} --ignore-not-found --wait', shell=True)
    if app_name != 'tests-base':
        argocd_app_diff_sync(f'{app_name}-prepare')
    subprocess.check_call(f'kubectl delete job -lapp.kubernetes.io/instance={app_name} --ignore-not-found --wait', shell=True)
    argocd_app_diff_sync(app_name)


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
    assert user_json == '{"name": "admin", "password": "password"}' or user_json == '{"password": "password", "name": "admin"}', user_json
    user = json.loads(user_json)
    assert user == {
        'name': 'admin',
        'password': 'password',
    }
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
        'vault_test_hello': 'world',
        'vault_test_value': '1234',
        **expected_configmap_changes
    }
    assert actual_configmap == expected_configmap
    return actual_configmap


def assert_argocd_app_jobs(name, expected_nfs_init_configmap, expected_nfs_init_job):
    jobs = json.loads(subprocess.check_output(f'kubectl get job -l app.kubernetes.io/instance={name} -o json', shell=True))['items']
    assert len(jobs) > 0
    nfs_init_job = None
    for job in jobs:
        completed = False
        for condition in job.get('status', {}).get('conditions', []):
            if condition.get('type') == 'Complete' and condition.get('status') == 'True':
                completed = True
        assert completed, f'Job {job["metadata"]["name"]} did not complete'
        if job['metadata']['name'].startswith(f'{name}-nfs-init'):
            nfs_init_job = job
    if expected_nfs_init_job:
        job = nfs_init_job
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


def assert_argocd_app(name, expected_configmap_changes=None, expected_testdep_source='tgz',
                      expected_nfs_init_job=True, expected_nfs_init_configmap='created'):
    try:
        configmap = assert_argocd_app_configmap(name, expected_configmap_changes or {})
        assert expected_testdep_source == json.loads(subprocess.check_output(
            f'kubectl -n {name} get configmap testdep -o json', shell=True
        ))['data']['source']
        assert_argocd_app_jobs(name, expected_nfs_init_configmap, expected_nfs_init_job)
    except Exception as e:
        raise Exception(f'Failed to assert argocd app {name}') from e
    return configmap


def test_base(start_infra):
    argocd_app_git_hard_refresh_sync('tests-base')
    assert_argocd_app('tests-base')


def test_base_production(start_infra):
    delete_vault_paths(['production'])
    argocd_app_git_hard_refresh_sync('tests-base-production')
    configmap = assert_argocd_app(
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
    production, = get_vault_paths(['production'])
    assert json.loads(base64.b64decode(production['alertmanager_secret'].encode()).decode()) == json.loads(configmap['alertmanager_secret'])


def delete_vault_paths(paths):
    for path in paths:
        subprocess.call([
            'kubectl', '-n', 'vault', 'exec', 'deploy/vault', '--', 'sh', '-c',
            f'VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=$(cat /tmp/root_token) vault kv delete -mount=kv {path}'
        ])


def get_vault_paths(paths):
    res = []
    for path in paths:
        res.append(json.loads(subprocess.check_output([
            'kubectl', '-n', 'vault', 'exec', 'deploy/vault', '--', 'sh', '-c',
            f'VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=$(cat /tmp/root_token) vault kv get -mount=kv -format=json {path}'
        ]))['data']['data'])
    return res


def test_base_staging(start_infra):
    delete_vault_paths(['staging/alertmanager-httpauth', 'staging/nfs'])
    argocd_app_git_hard_refresh_sync('tests-base-staging')
    configmap = assert_argocd_app(
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
    alertmanager_httpauth, nfs = get_vault_paths(['staging/alertmanager-httpauth', 'staging/nfs'])
    assert alertmanager_httpauth == {
        'auth': configmap['alertmanager_secret.auth'],
        'password': configmap['alertmanager_secret.password'],
        'user': 'admin'
    }
    assert nfs == {'ip': '1.2.3.4'}
