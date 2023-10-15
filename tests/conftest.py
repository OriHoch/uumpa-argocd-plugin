import subprocess

import pytest

from .common import (
    install_argocd, argocd_login, argocd_update_git, argocd_login_cleanup, argocd_app_diff_sync,
    vault_port_forward_start, vault_port_forward_stop
)


@pytest.fixture(scope="session")
def argocd(request):
    install_argocd('base')
    argocd_login()
    request.addfinalizer(argocd_login_cleanup)
    argocd_update_git()
    subprocess.check_call(f'kubectl delete job -lapp.kubernetes.io/instance=vault --ignore-not-found --wait', shell=True)
    argocd_app_diff_sync('vault')
    argocd_app_diff_sync('default')
    vault_port_forward_start()
    request.addfinalizer(vault_port_forward_stop)
