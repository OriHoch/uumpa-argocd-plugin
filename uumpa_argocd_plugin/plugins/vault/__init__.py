import json


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
