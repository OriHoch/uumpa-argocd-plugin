import os

from . import config, common, data, observability


def parse_value(value):
    if isinstance(value, dict):
        data_ = {**os.environ}
        data.process_value('value', value, data_)
        value = data_.get('value')
    return str(value or '')


def update_env(chart_path):
    with observability.start_as_current_span(update_env, attributes={'chart_path': chart_path}):
        env_path = os.path.join(chart_path, config.ARGOCD_ENV_UUMPA_ENV_CONFIG)
        observability.set_attribute('env_path', env_path)
        if os.path.exists(env_path):
            with observability.start_as_current_span('update_from_env_path'):
                with open(env_path) as f:
                    env_path_data = common.yaml_load(f)
                    observability.set_attribute('env_path_data', env_path_data)
                    for env_var in env_path_data:
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
        with observability.start_as_current_span('update_argocd_app_spec_env_vars'):
            argocd_app_spec_env_vars = config.get_argocd_app_spec_env_vars()
            observability.set_attribute('argocd_app_spec_env_vars', argocd_app_spec_env_vars)
            for k, v in argocd_app_spec_env_vars.items():
                setattr(config, k, v)
