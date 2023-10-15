import os
import json

import requests

from uumpa_argocd_plugin import common


def process_generator(generator, data_, is_skipped=False):
    if not is_skipped:
        _ = generator.pop('plugin', None)
        name = generator.pop('name')
        vault = generator.pop('vault')
        env = generator.pop('env', {})
        yield {
            'generator': {
                'type': 'job',
                'name': name,
                'python-module-function': 'uumpa_argocd_plugin.plugins.vault:run_generator_job',
                'env': {
                    'VAULT_GENERATORS_JSON': json.dumps(vault),
                    'ARGOCD_ENV_VAULT_ADDR': os.environ['ARGOCD_ENV_VAULT_ADDR'],
                    'ARGOCD_ENV_VAULT_ROLE_ID': os.environ['ARGOCD_ENV_VAULT_ROLE_ID'],
                    'ARGOCD_ENV_VAULT_SECRET_ID': os.environ['ARGOCD_ENV_VAULT_SECRET_ID'],
                    'ARGOCD_ENV_VAULT_PATH': os.environ['ARGOCD_ENV_VAULT_PATH'],
                    **env
                },
                **generator
            }
        }


def vault_init(env=None):
    env = os.environ if env is None else {**os.environ, **env}
    addr = env['ARGOCD_ENV_VAULT_ADDR']
    role_id = env['ARGOCD_ENV_VAULT_ROLE_ID']
    secret_id = env['ARGOCD_ENV_VAULT_SECRET_ID']
    data_path_prefix = env['ARGOCD_ENV_VAULT_PATH']
    res = requests.post(
        f"{addr}/v1/auth/approle/login",
        data=json.dumps({"role_id": role_id, "secret_id": secret_id}),
        headers={'Content-Type': 'application/json'}
    )
    assert res.status_code == 200, res.text
    token = res.json()['auth']['client_token']
    return token, addr, data_path_prefix


def vault_set(token, addr, data_path_prefix, path, data):
    res = requests.post(
        os.path.join(addr, 'v1', data_path_prefix, path),
        headers={
            'Content-Type': 'application/json',
            'X-Vault-Token': token
        },
        data=json.dumps({
            'data': data
        })
    )
    res.raise_for_status()


def run_generator_job(tmpdir, env):
    token, addr, data_path_prefix = vault_init(env)
    vault_generators_json = env['VAULT_GENERATORS_JSON']
    try:
        vault_generators = json.loads(vault_generators_json)
        for path, data in vault_generators.items():
            vault_set(token, addr, data_path_prefix, path, data)
    except Exception as e:
        raise Exception(f"Failed to run generator job\nvault_generators_json: {vault_generators_json}") from e


def get_vault_path(path):
    token, addr, data_path_prefix = vault_init()
    res = requests.get(
        os.path.join(addr, 'v1', data_path_prefix, path),
        headers={
            'Content-Type': 'application/json',
            'X-Vault-Token': token
        }
    )
    res.raise_for_status()
    return res.json()['data']['data']


def process_value(key, value, data_):
    path = common.render(value['path'], data_)
    d = get_vault_path(path)
    common.process_keyed_value(d, key, value, data_)
