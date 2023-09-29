import os

from . import config, common


def update_env(chart_path):
    env_path = os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_ENV_CONFIG)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for env_var in common.yaml_load(f):
                os.environ[env_var['name']] = env_var.get('value') or ''
    for k, v in config.get_argocd_app_spec_env_vars().items():
        setattr(config, k, v)
