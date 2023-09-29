import os
import importlib

from . import config, env


def process_init_plugin_function(init_plugin_function, chart_path):
    print(f'process_init_plugin_function: {init_plugin_function}')
    if '.' not in init_plugin_function and ':' not in init_plugin_function:
        init_plugin_function = f'uumpa_argocd_plugin.core:{init_plugin_function}'
    module, function = init_plugin_function.split(':')
    getattr(importlib.import_module(module), function)(chart_path)


def init(chart_path):
    env.update_env(chart_path)
    print(f'init: {chart_path}')
    if config.ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS:
        init_plugin_functions = [s.strip() for s in config.ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS.split(',') if s.strip()]
        for init_plugin_function in init_plugin_functions:
            process_init_plugin_function(init_plugin_function, chart_path)
    else:
        print('No init functions to run')
    print("OK")


def init_local(chart_path):
    init(chart_path)


def init_argocd():
    chart_path = os.getcwd()
    init(chart_path)
