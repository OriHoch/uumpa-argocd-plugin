import os

from . import config, common, data


def parse_value(value):
    if isinstance(value, dict):
        data_ = {**os.environ}
        data.process_value('value', value, data_)
        value = data_.get('value')
    return str(value or '')


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
                            os.environ[name] = parse_value(value)
                            break
                elif 'defaultValue' in env_var:
                    default_value = env_var.pop('defaultValue')
                    assert len(env_var) == 0
                    if name not in os.environ:
                        os.environ[name] = parse_value(default_value)
                else:
                    os.environ[name] = parse_value(env_var.get('value'))
    for k, v in config.get_argocd_app_spec_env_vars().items():
        setattr(config, k, v)
