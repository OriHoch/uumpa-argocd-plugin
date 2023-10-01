import os

from . import config, common


def update_env(chart_path):
    env_path = os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_ENV_CONFIG)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for env_var in common.yaml_load(f):
                name = 'ARGOCD_ENV_' + env_var.pop('name')
                if 'valueIf' in env_var:
                    value_if = env_var.pop('valueIf')
                    assert len(env_var) == 0
                    for if_, value in value_if.items():
                        if eval(if_, {}, os.environ):
                            os.environ[name] = value
                            break
                elif 'defaultValue' in env_var:
                    default_value = env_var.pop('defaultValue')
                    assert len(env_var) == 0
                    if name not in os.environ:
                        os.environ[name] = default_value
                else:
                    os.environ[name] = env_var.get('value') or ''
    for k, v in config.get_argocd_app_spec_env_vars().items():
        setattr(config, k, v)
