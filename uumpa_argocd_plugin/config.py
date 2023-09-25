import os


ARGOCD_ENV_UUMPA_DATA_CONFIG = os.environ.get('ARGOCD_ENV_UUMPA_DATA_CONFIG') or 'uumpa_data.yaml'
ARGOCD_ENV_UUMPA_GENERATORS_CONFIG = os.environ.get('ARGOCD_ENV_UUMPA_GENERATORS_CONFIG') or 'uumpa_generators.yaml'
ARGOCD_NAMESPACE = os.environ.get('ARGOCD_NAMESPACE') or 'argocd'
ARGOCD_REPO_SERVER_DEPLOYMENT = os.environ.get('ARGOCD_REPO_SERVER_DEPLOYMENT') or 'argocd-repo-server'
ARGOCD_UUMPA_PLUGIN_CONTAINER = os.environ.get('ARGOCD_UUMPA_PLUGIN_CONTAINER') or 'uumpa'
