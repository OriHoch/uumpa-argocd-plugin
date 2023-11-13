import os
import pytest

from . import common
from uumpa_argocd_plugin import observability


@pytest.fixture(scope="session")
def observability_span_session():
    observability.init()
    with observability.start_as_current_span('pytest_session') as span:
        yield span


@pytest.fixture(autouse=True)
def observability_span_function(request, observability_span_session):
    with observability.start_as_current_span(f'{request.module.__name__}.{request.function.__name__}') as span:
        yield span


@pytest.fixture(scope="session")
def start_infra():
    if os.environ.get('CI') == 'true':
        with common.start_infra(with_observability=False, build=True, skip_create_cluster=False):
            yield
    else:
        yield
