# Contributing to uumpa-argocd-plugin

## Tests

```bash
pip install -r tests/requirements.txt
pytest
```

## E2E Tests

Prerequisites:

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

Run the E2E tests:

```bash
pytest tests/test_e2e.py
```

To log in to the ArgoCD created in the tests:

```
# Get the admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
# Start a port forward
kubectl -n argocd port-forward svc/argocd-server 8080:80
```

Open http://localhost:8080 and login with `admin` username and the password from above.
