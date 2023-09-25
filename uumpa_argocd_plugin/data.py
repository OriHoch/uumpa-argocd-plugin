import os
import json
import importlib

from . import config, common


def process_value(key, value, data_):
    if isinstance(value, str):
        data_[key] = common.render(value, data_)
    else:
        assert isinstance(value, dict)
        plugin = value.get('plugin') or 'uumpa_argocd_plugin.core'
        importlib.import_module(plugin).process_value(key, value, data_)


def process(namespace_name, chart_path):
    data_ = {
        '__namespace_name': namespace_name,
        '__chart_path': chart_path,
    }
    with open(os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_DATA_CONFIG)) as f:
        for data_config in common.yaml_load(f):
            if_ = data_config.get('if', None)
            if common.process_if(if_, data_):
                later_items = []
                for k, v in data_config.items():
                    if '~' in json.dumps(v):
                        later_items.append((k, v))
                    else:
                        process_value(k, v, data_)
                for k, v in later_items:
                    process_value(k, v, data_)
    return data_
