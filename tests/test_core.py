import json
import base64
import tempfile
import subprocess

import pytest
from unittest.mock import patch

from uumpa_argocd_plugin import core, config


@pytest.mark.parametrize('type_, name, namespace, p_returncode, p_stdout, expected_result', [
    ('secret', 'my_secret', 'my_namespace', 0, {'key1': 'value1', 'key2': 'value2'}, {'key1': 'value1', 'key2': 'value2'}),
    ('configmap', 'my_secret', 'my_namespace', 0, {'key1': 'value1', 'key2': 'value2'}, {'key1': 'value1', 'key2': 'value2'}),
    ('secret', 'my_secret', 'my_namespace', 1, '', {}),
    ('configmap', 'my_secret', 'my_namespace', 1, '', {}),
])
def test_get_secret_configmap(type_, name, namespace, p_returncode, p_stdout, expected_result):
    if isinstance(p_stdout, dict):
        p_stdout = json.dumps({
            'data': {key: (base64.b64encode(value.encode()).decode() if type_ == 'secret' else value) for key, value in p_stdout.items()}
        })
    mock_result = subprocess.CompletedProcess(args=[], returncode=p_returncode, stdout=p_stdout)
    with patch('subprocess.run', return_value=mock_result) as mock_run:
        result = core.get_secret_configmap(type_, name, namespace)
        assert result == expected_result
        mock_run.assert_called_once_with([
            'kubectl', 'get', type_, name, '-n', namespace, '-o', 'json'
        ], capture_output=True, text=True)


@pytest.mark.parametrize('key, value, data_, expected_get_secret_configmap_args, secret_configmap_data, expected_data_key_value', [
    (
        'user',
        {'namespace': 'my_namespace', 'name': 'user_secret', 'type': 'secret'},
        {'__namespace_name': 'ignored'},
        ('secret', 'user_secret', 'my_namespace'),
        {'name': 'my_username', 'admin': 'true'},
        {'name': 'my_username', 'admin': 'true'}
    ),
    (
        'user',
        {'name': '~user_secret_name~', 'type': 'secret', 'key': 'admin'},
        {'__namespace_name': '~user_namespace_name~', 'user_secret_name': 'user_secret', 'user_namespace_name': 'user_namespace'},
        ('secret', 'user_secret', 'user_namespace'),
        {'name': 'my_username', 'admin': 'true'},
        'true'
    ),
    (
        'user',
        {'name': '~user_configmap_name~', 'type': 'configmap', 'keys': ['admin']},
        {'__namespace_name': '~user_namespace_name~', 'user_configmap_name': 'user', 'user_namespace_name': 'user_namespace'},
        ('configmap', 'user', 'user_namespace'),
        {'name': 'my_username', 'admin': 'true'},
        {'admin': 'true'},
    ),
])
def test_process_value_secret_configmap(key, value, data_, expected_get_secret_configmap_args, secret_configmap_data, expected_data_key_value):
    with patch('uumpa_argocd_plugin.core.get_secret_configmap', return_value=secret_configmap_data) as mock_get_secret_configmap:
        core.process_value_secret_configmap(key, value, data_)
        mock_get_secret_configmap.assert_called_once_with(*expected_get_secret_configmap_args)
    assert data_[key] == expected_data_key_value


def test_process_value_password():
    data = {}
    core.process_value_password('password', {'length': 10}, data)
    assert len(data['password']) == 10


def test_process_value_httpauth():
    data = {}
    with patch('subprocess.check_output', return_value='encrypted_auth') as mock_check_output:
        core.process_value_httpauth('auth', {'user': 'admin', 'password': '123456'}, data)
        mock_check_output.assert_called_once_with(['htpasswd', '-bc', '/dev/stdout', 'admin', '123456'], text=True)
    assert data['auth'] == 'encrypted_auth'


def test_process_generator_job():
    repo_server_deployment = {
        'spec': {
            'template': {
                'spec': {
                    'serviceAccountName': 'argocd-repo-server',
                    'tolerations': [
                        {'key': 'dedicated', 'operator': 'Equal', 'value': 'repo-server', 'effect': 'NoSchedule'}
                    ],
                    'containers': [
                        {
                            'name': config.ARGOCD_UUMPA_PLUGIN_CONTAINER,
                            'volumeMounts': [{'name': 'other_volume'}]
                        }
                    ],
                    'volumes': [{'name': 'other_volume'}]
                }
            }
        }
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f'{tmpdir}/data.json', 'w') as f:
            f.write('{}')
        with open(f'{tmpdir}/init.sh', 'w') as f:
            f.write('#!/usr/bin/env bash\necho hello world\n')
        generator = {
            'if': 'run_it is True',
            'name': 'my_hook',
            'hook': 'Sync',
            'hook-delete-policy': 'AfterSuccess',
            'type': 'Sync',
            'script': 'init.sh',
            'files': [
                'data.json'
            ],
        }
        data = {
            '__namespace_name': 'my_namespace',
            '__chart_path': tmpdir,
            'run_it': True,
        }
        with patch('subprocess.check_output', return_value=json.dumps(repo_server_deployment)) as mock_check_output:
            items = list(core.process_generator_job(generator, data))
            mock_check_output.assert_called_once_with(
                ['kubectl', '-n', config.ARGOCD_NAMESPACE, 'get', 'deployment', config.ARGOCD_REPO_SERVER_DEPLOYMENT, '-o', 'json'],
                text=True
            )
    assert len(items) == 2
    assert items[0] == {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': 'my_namespace-my_hook-files',
            'namespace': 'argocd',
            'annotations': {
                'argocd.argoproj.io/hook': 'Sync',
                'argocd.argoproj.io/hook-delete-policy': 'AfterSuccess'
            },
            'labels': {
                'uumpa.argocd.plugin/item-type': 'job-files'
            }
        },
        'data': {
            'file_0': base64.b64encode('#!/usr/bin/env bash\necho hello world\n'.encode()).decode(),
            'file_1': base64.b64encode('{}'.encode()).decode(),
        }
    }
    assert items[1] == {
        'apiVersion': 'batch/v1',
        'kind': 'Job',
        'metadata': {
            'generateName': 'my_namespace-my_hook',
            'namespace': 'argocd',
            'annotations': {
                'argocd.argoproj.io/hook': 'Sync',
                'argocd.argoproj.io/hook-delete-policy': 'AfterSuccess'
            },
            'labels': {
                'uumpa.argocd.plugin/item-type': 'job'
            }
        },
        'spec': {
            'template': {
                'spec': {
                    'automountServiceAccountToken': True,
                    'serviceAccountName': 'argocd-repo-server',
                    'restartPolicy': 'Never',
                    'tolerations': [
                        {'key': 'dedicated', 'operator': 'Equal', 'value': 'repo-server', 'effect': 'NoSchedule'}
                    ],
                    'volumes': [
                        {'name': 'other_volume'},
                        {'name': 'uumpa-job-files', 'configMap': {'name': 'my_namespace-my_hook-files'}}
                    ],
                    'containers': [
                        {
                            'name': 'uumpa',
                            'volumeMounts': [
                                {'name': 'other_volume'},
                                {'name': 'uumpa-job-files', 'mountPath': '/var/uumpa-job-files'}
                            ],
                            'command': ['uumpa-argocd-plugin'],
                            'args': [
                                'run-generator-job',
                                base64.b64encode(json.dumps({
                                    'generator': generator,
                                    'data': data,
                                    'file_paths': ['init.sh', 'data.json']
                                }).encode()).decode()
                            ]
                        }
                    ]
                }
            }
        }
    }


def test_process_generator_job_skipped():
    generator = {
        'if': 'run_it is True',
        'generators': [
            {'if': 'False', 'generator': 1},
            {'if': '_job_status == "success"', 'generator': 2},
            {'generator': 3},
        ]
    }
    data = {'run_it': False}
    assert list(core.process_generator_job(generator, data)) == [{'generator': {'generator': 3}}]


def test_process_generator_secret_configmap():
    assert core.process_generator_secret_configmap(
        'configmap',
        {
            'name': 'my_config',
            'namespace': 'my_namespace',
            'data': {
                'name': 'p_~user.name~',
                'pass': '~user_pass~',
            }
        },
        {
            'user': {'name': 'username'},
            'user_pass': 'password'
        }
    ) == {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': 'my_config',
            'namespace': 'my_namespace'
        },
        'data': {
            'name': 'p_username',
            'pass': 'password'
        }
    }
