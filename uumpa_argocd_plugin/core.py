import os
import json
import base64
import string
import secrets
import subprocess

from . import common, config


def get_secret_configmap(type_, name, namespace):
    p = subprocess.run(['kubectl', 'get', type_, name, '-n', namespace, '-o', 'json'], capture_output=True, text=True)
    if p.returncode == 0:
        return {
            k: base64.b64decode(v).decode() if type_.startswith('secret') else v
            for k, v in json.loads(p.stdout)['data'].items()
        }
    else:
        return {}


def process_value_secret_configmap(key, value, data_):
    namespace = common.render(value.get('namespace') or data_['__namespace_name'], data_)
    name = common.render(value['name'], data_)
    d = get_secret_configmap(value['type'], name, namespace)
    common.process_keyed_value(d, key, value, data_)


def process_value_password(key, value, data_):
    length = int(common.render(str(value['length']), data_))
    data_[key] = ''.join([secrets.choice(string.ascii_letters + string.digits) for _ in range(length)])


def process_value_httpauth(key, value, data_):
    user = common.render(value['user'], data_)
    password = common.render(value['password'], data_)
    data_[key] = subprocess.check_output(['htpasswd', '-bc', '/dev/stdout', user, password], text=True).strip()


def process_value(key, value, data_):
    type_ = value['type']
    if type_ in ['secret', 'configmap']:
        process_value_secret_configmap(key, value, data_)
    else:
        globals()[f'process_value_{type_}'](key, value, data_)


def process_generator_job(generator, data_):
    if_ = generator.get('if', None)
    if common.process_if(if_, data_):
        repo_server_deployment = json.loads(subprocess.check_output([
            'kubectl', '-n', config.ARGOCD_NAMESPACE, 'get', 'deployment', config.ARGOCD_REPO_SERVER_DEPLOYMENT, '-o', 'json'
        ], text=True))
        repo_server_spec = repo_server_deployment['spec']['template']['spec']
        repo_server_containers = [c for c in repo_server_spec['containers'] if c['name'] == config.ARGOCD_UUMPA_PLUGIN_CONTAINER]
        container = repo_server_containers[0] if len(repo_server_containers) > 0 else {}
        container['command'] = ['uumpa-argocd-plugin']
        file_paths = []
        files_configmap_data = {}
        files = generator.get('files', [])
        if generator.get('script'):
            files = [generator['script'], *files]
        for i, filepath in enumerate(files):
            file_paths.append(filepath)
            with open(os.path.join(data_['__chart_path'], filepath)) as f:
                files_configmap_data[f'file_{i}'] = base64.b64encode(f.read().encode()).decode()
        namespace_name = data_['__namespace_name']
        hook_name = generator['name']
        hook = generator.get('hook', 'PreSync')
        hook_delete_policy = generator.get('hook-delete-policy', 'HookSucceeded')
        volumes = repo_server_spec['volumes']
        if len(file_paths) > 0:
            volumes = [
                *volumes,
                {
                    'name': 'uumpa-job-files',
                    'configMap': {
                        'name': f'{namespace_name}-{hook_name}-files'
                    }
                }
            ]
            container.setdefault('volumeMounts', []).append({
                'name': 'uumpa-job-files',
                'mountPath': '/var/uumpa-job-files'
            })
            yield {
                'apiVersion': 'v1',
                'kind': 'ConfigMap',
                'metadata': {
                    'name': f'{namespace_name}-{hook_name}-files',
                    'namespace': config.ARGOCD_NAMESPACE,
                    'annotations': {
                        'argocd.argoproj.io/hook': hook,
                        'argocd.argoproj.io/hook-delete-policy': hook_delete_policy,
                    },
                    'labels': {
                        'uumpa.argocd.plugin/item-type': 'job-files'
                    },
                },
                'data': files_configmap_data
            }
        container['args'] = ['run-generator-job', json.dumps({
            'generator': generator,
            'data': data_,
            'file_paths': file_paths
        })]
        yield {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {
                'generateName': f'{namespace_name}-{hook_name}',
                'namespace': config.ARGOCD_NAMESPACE,
                'annotations': {
                    'argocd.argoproj.io/hook': hook,
                    'argocd.argoproj.io/hook-delete-policy': hook_delete_policy,
                },
                'labels': {
                    'uumpa.argocd.plugin/item-type': 'job'
                },
            },
            'spec': {
                'template': {
                    'spec': {
                        'automountServiceAccountToken': True,
                        'serviceAccountName': repo_server_spec['serviceAccountName'],
                        'tolerations': repo_server_spec.get('tolerations', []),
                        'volumes': volumes,
                        'containers': [container]
                    }
                }
            }
        }
    else:
        job_status = 'skip'
        for generator in generator['generators']:
            if_ = generator.get('if', '_job_status in ["skip", "success"]')
            if common.process_if(if_, {**data_, '_job_status': job_status}):
                yield {'generator': generator}


def process_generator_secret_configmap(type_, generator, data_):
    rendered_data = {
        k: common.render(v, data_)
        for k, v in generator['data'].items()
    }
    return {
        'apiVersion': 'v1',
        'kind': type_.capitalize(),
        'metadata': {
            'name': generator['name'],
            'namespace': generator.get('namespace') or data_['__namespace_name'],
        },
        'data': {
            k: base64.b64encode(v.encode()).decode() if type_ == 'secret' else v
            for k, v in rendered_data.items()
        }
    }


def process_generator(generator, data_):
    try:
        type_ = generator.get('type')
        if type_ in ['secret', 'configmap']:
            yield process_generator_secret_configmap(type_, generator, data_)
        else:
            yield from globals()[f'process_generator_{type_}'](generator, data_)
    except Exception as e:
        raise Exception(f'generator: {generator}') from e
