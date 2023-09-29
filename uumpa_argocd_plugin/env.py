import os

from . import config, common


def update_env(chart_path):
    env_path = os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_ENV_CONFIG)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for env_var in common.yaml_load(f):
                if env_var.get('valueIf'):
                    assert not env_var.get('value')
                    for if_, value in env_var['valueIf'].items():
                        if eval(if_, {}, os.environ):
                            os.environ['ARGOCD_ENV_' + env_var['name']] = value
                            break
                else:
                    os.environ['ARGOCD_ENV_' + env_var['name']] = env_var.get('value') or ''
    for k, v in config.get_argocd_app_spec_env_vars().items():
        setattr(config, k, v)
