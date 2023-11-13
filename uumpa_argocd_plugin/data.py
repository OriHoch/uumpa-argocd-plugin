import os
import json
import importlib

from . import config, common, observability


def process_data_keys(data_):
    for k, v in list(data_.items()):
        if '.' in k:
            del data_[k]
            obj, key, *extra = k.split('.')
            assert len(extra) == 0, f'Only one level of nesting is supported for data keys, got {k}'
            if obj not in data_:
                data_[obj] = {}
            assert isinstance(data_[obj], dict), f'Cannot set {k} because {obj} is not a dict'
            data_[obj][key] = v


def process_value(key, value, data_):
    if isinstance(value, str):
        data_[key] = common.render(value, data_)
    else:
        assert isinstance(value, dict)
        plugin = value.get('plugin') or 'uumpa_argocd_plugin.core'
        importlib.import_module(plugin).process_value(key, value, data_)
    process_data_keys(data_)


def iterate_data_configs(chart_path):
    with observability.start_as_current_span(iterate_data_configs, attributes={'chart_path': chart_path}):
        if config.ARGOCD_UUMPA_GLOBAL_DATA_CONFIG:
            with open(config.ARGOCD_UUMPA_GLOBAL_DATA_CONFIG) as f:
                global_data_configs = common.yaml_load(f)
                observability.add_event('load_global_data_config', attributes={
                    'path': config.ARGOCD_UUMPA_GLOBAL_DATA_CONFIG,
                    'global_data_configs': global_data_configs,
                })
                for data_config in global_data_configs:
                    yield data_config
        if os.path.exists(os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_DATA_CONFIG)):
            chart_data_configs_path = os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_DATA_CONFIG)
            with open(chart_data_configs_path) as f:
                chart_data_configs = common.yaml_load(f)
                observability.add_event('load_chart_data_config', attributes={
                    'path': chart_data_configs_path,
                    'chart_data_configs': chart_data_configs,
                })
                for data_config in chart_data_configs:
                    yield data_config


def process(namespace_name, chart_path):
    with observability.start_as_current_span(process, attributes={'namespace_name': namespace_name, 'chart_path': chart_path}) as span:
        data_ = {
            '__namespace_name': namespace_name,
            '__chart_path': chart_path,
        }
        for data_config in iterate_data_configs(chart_path):
            if_ = data_config.get('if', None)
            if_result = common.process_if(if_, data_)
            observability.add_event('if', attributes={'if': if_, 'result': if_result}, span=span)
            if if_result:
                later_items = []
                for k, v in data_config.items():
                    if '~' in json.dumps(v):
                        later_items.append((k, v))
                    else:
                        process_value(k, v, data_)
                for k, v in later_items:
                    process_value(k, v, data_)
        return data_
