import os

import pytest

from .common import install_argocd, argocd_login, argocd_update_git, argocd_login_cleanup


@pytest.fixture(scope="session")
def argocd(request):
    if not os.environ.get('SKIP_ARGOCD_FIXTURE'):
        install_argocd('base')
        argocd_login()
        argocd_update_git()
        request.addfinalizer(argocd_login_cleanup)
