# Contributing to uumpa-argocd-plugin

## Development

```
python3 -m venv venv
pip install -r requirements.txt
pip install -e .
```

## Tests

Install test dependencies:

```bash
pip install -r tests/requirements.txt
```

E2E Tests Prerequisites:

* [Kind](https://kind.sigs.k8s.io/docs/user/quick-start#installing-from-release-binaries)
* kubectl
* Docker
* [ArgoCD CLI](https://argo-cd.readthedocs.io/en/stable/getting_started/#2-download-argo-cd-cli)

Start infrastructure, keep process running in background:

```
python -m tests.cli start-infra --with-observability --build
```

In a separate terminal -

Make sure you are connected to the testing cluster: `kubectl cluster-info`

You should see the cluster running at localhost / 127.0.0.1

Run the tests:

```bash
pytest -svvx
```

Code changes will automatically be reloaded in the test cluster, but if you made changes
to requirements or the Dockerfile, you will need to rebuild the image, you can run the following command
to rebuild without recreating the cluster:

```
python -m tests.cli start-infra --with-observability --build --skip-create-cluster
```

If you want to make sure you run tests from a clean state, you can run without `--skip-create-cluster` flag to
recreate the cluster from scratch.

Once test infra is running with observability, you can send observability data to it from tests and from local running 
of plugin commands by setting the following env var:

```
export ENABLE_OTLP=1
```
