# Contributing to uumpa-argocd-plugin

## Development

```
python3 -m venv venv
pip install -r requirements.txt
pip install -e .
```

## Tests

E2E Tests Prerequisites:

* [Kind](https://kind.sigs.k8s.io/docs/user/quick-start#installing-from-release-binaries)
* kubectl
* Docker
* [ArgoCD CLI](https://argo-cd.readthedocs.io/en/stable/getting_started/#2-download-argo-cd-cli)

Create Kind cluster:

```
cat tests/kind.yaml.envsubst | envsubst > tests/kind.yaml
kind create cluster --config tests/kind.yaml
```

Make sure you are connected to the testing cluster: `kubectl cluster-info`

You should see the cluster running at localhost / 127.0.0.1

Install test dependencies:

```bash
pip install -r tests/requirements.txt
```

Run the tests:

```bash
pytest
```

To log in to the ArgoCD / Vault created in the E2E tests:

```
export PORT_FORWARDS_KEEP=1
pytest -svvx tests/test_e2e.py
```

The final log line will contain the login details

Code changes will automatically be reloaded in the test cluster, but if you made changes
to requirements or the Dockerfile, you will need to rebuild the image and restart the deployment:

```
docker build -t ghcr.io/orihoch/uumpa-argocd-plugin/plugin:latest .
kind load docker-image ghcr.io/orihoch/uumpa-argocd-plugin/plugin:latest
kubectl rollout restart deployment/argocd-repo-server -n argocd
```
