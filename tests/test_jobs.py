import os
import json
import base64
import tempfile
from textwrap import dedent
from unittest.mock import patch

from uumpa_argocd_plugin import jobs


def test_run_argocd():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, 'file_0'), 'w') as f:
            f.write(base64.b64encode(dedent(f'''
                #!/usr/bin/env bash
                
                echo $NFS_IP > {tmpdir}/__nfs_ip
                echo $NFS_ID_RSA_FILE > {tmpdir}/__nfs_id_rsa_file
                cat $NFS_ID_RSA_FILE > {tmpdir}/__nfs_id_rsa_file_content
                ls -lah $NFS_ID_RSA_FILE > {tmpdir}/__nfs_id_rsa_file_ls
            ''').strip().encode()).decode())
        with patch('subprocess.run') as mock_run:
            jobs.run_argocd(
                base64.b64encode(json.dumps({
                    "generator": {
                        "if": 'nfs_initialized != "yes"',
                        "type": "job",
                        "name": "init-nfs",
                        "script": "init.sh",
                        "env": {
                            "NFS_IP": "~nfs_ssh_key.ip~",
                            "NFS_ID_RSA_FILE": "FILE::~nfs_ssh_key.id_rsa~"
                        },
                        "generators": [
                            {
                                "type": "configmap",
                                "name": "nfs-initializaed",
                                "data": {
                                    "initialized": "yes"
                                }
                            }
                        ]
                    },
                    "data": {
                        "__namespace_name": "storage",
                        "nfs_ssh_key": {
                            "id_rsa": "--- OPENSSH PRIVATE KEY ---",
                            "ip": "172.16.0.2"
                        },
                        "nfs_initialized": None
                    },
                    "file_paths": [
                        "init.sh"
                    ]
                }).encode()).decode(),
                uumpa_job_files_path=tmpdir
            )
            mock_run.assert_called_once_with(
                ['kubectl', 'apply', '-f', '-'],
                input='{"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "nfs-initializaed", "namespace": "storage"}, "data": {"initialized": "yes"}}',
                text=True, check=True
            )


def test_run_job_process_env():
    env = jobs.run_job_process_env([], None, {}, {
        'VAULT_GENERATORS_JSON': json.dumps({
            'production': {
                'alertmanager_secret': '~alertmanager_secret:base64~'
            }
        })
    }, {
        'alertmanager_secret': {
            'user': 'admin'
        }
    })
    assert set(env.keys()) == {'VAULT_GENERATORS_JSON'}
    vault_generators = json.loads(env['VAULT_GENERATORS_JSON'])
    assert set(vault_generators.keys()) == {'production'}
    assert set(vault_generators['production'].keys()) == {'alertmanager_secret'}
    assert vault_generators['production']['alertmanager_secret'] == base64.b64encode(json.dumps({'user': 'admin'}).encode()).decode()
