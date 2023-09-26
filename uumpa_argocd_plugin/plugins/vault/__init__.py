import os
import json

import requests


def process_generator(generator, data_):
    yield {'_type': 'vault', 'generator': generator}


def get_vault_generator_item(vault_generators, data_):
    return {'generator': {
        'type': 'job',
        'name': 'vault',
        'python-module-function': 'uumpa_argocd_plugin.plugins.vault:run_generator_job',
        'env': {
            'VAULT_GENERATORS_JSON': json.dumps(vault_generators)
        }
    }}


def post_process_generator_items(items, data_):
    new_items = []
    vault_generators = []
    for item in items:
        if set(item.keys()) == {'_type', 'generator'} and item['_type'] == 'vault':
            vault_generators.append(item['generator'])
        else:
            new_items.append(item)
    if len(vault_generators) > 0:
        new_items.append(get_vault_generator_item(vault_generators, data_))
        return True, new_items
    else:
        return False, new_items


def vault_init():
    addr = os.environ['VAULT_ADDR']
    role_id = os.environ['VAULT_ROLE_ID']
    secret_id = os.environ['VAULT_SECRET_ID']
    data_path_prefix = os.environ.get('VAULT_PATH') or 'v1/kv/data'
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
        os.path.join(addr, data_path_prefix, path),
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
    token, addr, data_path_prefix = vault_init()
    vault_generators = json.loads(env['VAULT_GENERATORS_JSON'])
    for vault_generator in vault_generators:
        path = vault_generator['path']
        data = vault_generator['data']
        vault_set(token, addr, data_path_prefix, path, data)
