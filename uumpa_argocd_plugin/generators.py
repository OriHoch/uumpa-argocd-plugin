import os
import importlib

from . import config, common, env, observability


def process_generator(generator, data_, loaded_modules, is_skipped=False):
    observability.add_event('process_generator', attributes={'generator': generator, 'is_skipped': is_skipped, 'data': data_})
    plugin = generator.get('plugin', 'uumpa_argocd_plugin.core')
    module = importlib.import_module(plugin)
    loaded_modules.add(module)
    yield from module.process_generator(generator, data_, is_skipped)


def process_generators(generators, data_, loaded_modules):
    observability.add_event('process_generators', attributes={'generators': generators})
    for generator in generators:
        if_ = generator.get('if', None)
        for item in process_generator(generator, data_, loaded_modules, is_skipped=not common.process_if(if_, data_)):
            if list(item.keys()) == ['generator']:
                yield from process_generators([item['generator']], data_, loaded_modules)
            else:
                yield item


def post_process_generator_items(items_iterator, data_, loaded_modules):
    observability.add_event('post_process_generator_items', attributes={'data': data_})
    items = list(items_iterator)
    needs_reprocess = True
    while needs_reprocess:
        needs_reprocess = False
        for module in loaded_modules:
            if hasattr(module, 'post_process_generator_items'):
                made_changes, items = module.post_process_generator_items(items, data_)
                if made_changes:
                    needs_reprocess = True
                observability.add_event('module_post_process_generator_items', attributes={'module': module, 'made_changes': made_changes})
        new_items = []
        for item in items:
            observability.add_event('post_process_generator_items_item', attributes={'item': item})
            if list(item.keys()) == ['generator']:
                new_items += list(process_generators([item['generator']], data_, loaded_modules))
                needs_reprocess = True
            else:
                new_items.append(item)
        items = new_items
    return items


def iterate_process_generators(chart_path, data_, loaded_modules):
    observability.add_event('iterate_process_generators', attributes={'chart_path': chart_path})
    if config.ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG:
        observability.add_event('load_global_generators_config', attributes={'path': config.ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG})
        with open(config.ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG) as f:
            global_generators_configs = common.yaml_load(f)
            observability.add_event('global_generators_config', attributes=dict(global_generators_configs=global_generators_configs))
            for item in process_generators(global_generators_configs, data_, loaded_modules):
                yield item
    if os.path.exists(os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_GENERATORS_CONFIG)):
        chart_generators_configs_path = os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_GENERATORS_CONFIG)
        observability.add_event('load_chart_generators_config', attributes={'path': chart_generators_configs_path})
        with open(chart_generators_configs_path) as f:
            chart_generators_configs = common.yaml_load(f)
            observability.add_event('chart_generators_configs', attributes=dict(chart_generators_configs=chart_generators_configs))
            for item in process_generators(chart_generators_configs, data_, loaded_modules):
                yield item


def process(data_):
    chart_path = data_['__chart_path']
    with observability.start_as_current_span(process, attributes={'chart_path': chart_path, 'data': data_}):
        env.update_env(chart_path)
        loaded_modules = set()
        for item in post_process_generator_items(iterate_process_generators(chart_path, data_, loaded_modules), data_, loaded_modules):
            observability.add_event('output_item', attributes={'item': item})
            yield common.yaml_dump_dict(item)
        data_['__loaded_modules'] = loaded_modules
