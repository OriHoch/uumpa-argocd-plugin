import os
import tempfile

from uumpa_argocd_plugin import data, config, common


def test_process():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, config.ARGOCD_ENV_UUMPA_DATA_CONFIG), 'w') as f:
            common.yaml_dump([
                {
                    'key': 'value',
                },
                {
                    'if': 'key == "value"',
                    'foo': 'bar-~key~',
                },
                {
                    'baz.x': '~cab~',
                    'cab': 'rab',
                }
            ], f)
        assert data.process('my_namespace', tmpdir) == {
            '__namespace_name': 'my_namespace',
            '__chart_path': tmpdir,
            'key': 'value',
            'if': 'key == "value"',
            'foo': 'bar-value',
            'cab': 'rab',
            'baz': {
                'x': 'rab',
            }
        }
