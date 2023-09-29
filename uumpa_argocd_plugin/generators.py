import os
import json
import importlib

from . import config, common


def process_generator(generator, data_, loaded_modules):
    plugin = generator.get('plugin', 'uumpa_argocd_plugin.core')
    module = importlib.import_module(plugin)
    loaded_modules.add(module)
    yield from module.process_generator(generator, data_)


def process_generators(generators, data_, loaded_modules):
    for generator in generators:
        for item in process_generator(generator, data_, loaded_modules):
            if list(item.keys()) == ['generator']:
                yield from process_generators([item['generator']], data_, loaded_modules)
            else:
                yield item


def post_process_generator_items(items_iterator, data_, loaded_modules):
    items = list(items_iterator)
    needs_reprocess = True
    while needs_reprocess:
        needs_reprocess = False
        for module in loaded_modules:
            if hasattr(module, 'post_process_generator_items'):
                made_changes, items = module.post_process_generator_items(items, data_)
                if made_changes:
                    needs_reprocess = True
        new_items = []
        for item in items:
            if list(item.keys()) == ['generator']:
                new_items += list(process_generators([item['generator']], data_, loaded_modules))
                needs_reprocess = True
            else:
                new_items.append(item)
        items = new_items
    return items


def iterate_process_generators(chart_path, data_, loaded_modules):
    if config.ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG:
        with open(config.ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG) as f:
            for item in process_generators(common.yaml_load(f), data_, loaded_modules):
                yield item
    if os.path.exists(os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_GENERATORS_CONFIG)):
        with open(os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_GENERATORS_CONFIG)) as f:
            for item in process_generators(common.yaml_load(f), data_, loaded_modules):
                yield item


def process(data_):
    chart_path = data_['__chart_path']
    loaded_modules = set()
    for item in post_process_generator_items(iterate_process_generators(chart_path, data_, loaded_modules), data_, loaded_modules):
        yield common.yaml_dump_dict(item)
    data_['__loaded_modules'] = loaded_modules
