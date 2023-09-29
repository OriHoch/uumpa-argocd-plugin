import os

# global env vars - can only be set in the plugin sidecar container
ARGOCD_NAMESPACE = os.environ.get('ARGOCD_NAMESPACE') or 'argocd'
ARGOCD_REPO_SERVER_DEPLOYMENT = os.environ.get('ARGOCD_REPO_SERVER_DEPLOYMENT') or 'argocd-repo-server'
ARGOCD_UUMPA_PLUGIN_CONTAINER = os.environ.get('ARGOCD_UUMPA_PLUGIN_CONTAINER') or 'uumpa'
ARGOCD_UUMPA_GLOBAL_DATA_CONFIG = os.environ.get('ARGOCD_UUMPA_GLOBAL_DATA_CONFIG')
ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG = os.environ.get('ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG')


def get_argocd_app_spec_env_vars():
    return {
        'ARGOCD_ENV_UUMPA_DATA_CONFIG': os.environ.get('ARGOCD_ENV_UUMPA_DATA_CONFIG') or 'uumpa_data.yaml',
        'ARGOCD_ENV_UUMPA_GENERATORS_CONFIG': os.environ.get('ARGOCD_ENV_UUMPA_GENERATORS_CONFIG') or 'uumpa_generators.yaml',
        'ARGOCD_ENV_UUMPA_ENV_CONFIG': os.environ.get('ARGOCD_ENV_UUMPA_ENV_CONFIG') or 'uumpa_env.yaml',
        'ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS': os.environ.get('ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS')
    }


argocd_app_spec_env_vars = get_argocd_app_spec_env_vars()
ARGOCD_ENV_UUMPA_DATA_CONFIG = argocd_app_spec_env_vars['ARGOCD_ENV_UUMPA_DATA_CONFIG']
ARGOCD_ENV_UUMPA_GENERATORS_CONFIG = argocd_app_spec_env_vars['ARGOCD_ENV_UUMPA_GENERATORS_CONFIG']
ARGOCD_ENV_UUMPA_ENV_CONFIG = argocd_app_spec_env_vars['ARGOCD_ENV_UUMPA_ENV_CONFIG']
ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS = argocd_app_spec_env_vars['ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS']
