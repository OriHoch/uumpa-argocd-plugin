import io
import os
import sys
import tempfile

from unittest.mock import patch

from uumpa_argocd_plugin import generate, common, config


def test_generate_local():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, config.ARGOCD_ENV_UUMPA_DATA_CONFIG), 'w') as f:
            common.yaml_dump([{'key': 'value'}], f)
        with open(os.path.join(tmpdir, config.ARGOCD_ENV_UUMPA_GENERATORS_CONFIG), 'w') as f:
            common.yaml_dump([{'type': 'configmap', 'name': 'my_config', 'data': {'foo': 'bar'}}], f)
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout
        try:
            with patch('subprocess.check_output', return_value='kind: Mock\n---\nkind: Mock2\n') as mock_check_output:
                generate.generate_local('my_namespace', tmpdir, '--include-crds')
                mock_check_output.assert_called_once_with([
                    'helm', 'template', '.', '--namespace', 'my_namespace', '--include-crds'
                ], text=True, cwd=tmpdir)
        finally:
            sys.stdout = old_stdout
        new_stdout.seek(0)
        output = new_stdout.read().strip()
        assert list(common.yaml_load_all(output)) == [
            {
                'apiVersion': 'v1',
                'kind': 'Configmap',
                'metadata': {'name': 'my_config', 'namespace': 'my_namespace'},
                'data': {'foo': 'bar'},
            },
            {'kind': 'Mock'},
            {'kind': 'Mock2'}
        ]



def test_generate_argocd():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, config.ARGOCD_ENV_UUMPA_DATA_CONFIG), 'w') as f:
            common.yaml_dump([{'key': 'value'}], f)
        with open(os.path.join(tmpdir, config.ARGOCD_ENV_UUMPA_GENERATORS_CONFIG), 'w') as f:
            common.yaml_dump([{'type': 'configmap', 'name': 'my_config', 'data': {'foo': 'bar'}}], f)
        os.chdir(tmpdir)
        os.environ.update({
            'ARGOCD_APP_NAME': 'my_app',
            'ARGOCD_APP_NAMESPACE': 'my_namespace',
            'KUBE_VERSION': '1.16.0',
            'KUBE_API_VERSIONS': 'apps/v1,extensions/v1beta1',
            'ARGOCD_ENV_HELM_ARGS': '--include-crds --do-something-else',
        })
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout
        try:
            with patch('subprocess.check_output', return_value='kind: Mock\n---\nkind: Mock2\n') as mock_check_output:
                generate.generate_argocd()
                mock_check_output.assert_called_once_with(
                    'helm template . --name-template my_app --namespace my_namespace '
                    '--kube-version 1.16.0 --api-versions apps/v1 --api-versions extensions/v1beta1 '
                    '--include-crds --do-something-else',
                    shell=True, text=True, cwd=tmpdir
                )
        finally:
            sys.stdout = old_stdout
        new_stdout.seek(0)
        output = new_stdout.read().strip()
        assert list(common.yaml_load_all(output)) == [
            {
                'apiVersion': 'v1',
                'kind': 'Configmap',
                'metadata': {'name': 'my_config', 'namespace': 'my_namespace'},
                'data': {'foo': 'bar'},
            },
            {'kind': 'Mock'},
            {'kind': 'Mock2'}
        ]
