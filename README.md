# Uumpa ArgoCD Plugin

## Install

* Add the plugin sidecar to the argocd-repo-server deployment, 
  see [manifests/patch-argocd-repo-server-deployment.yaml](manifests/patch-argocd-repo-server-deployment.yaml)
  for details, if you are using Kustomize you can use that file as a base for a strategic merge patch.
* Add the plugin configuration - [manifests/uumpa-plugin-configmap.yaml](manifests/uumpa-plugin-configmap.yaml), for
  most common use-cases you will not need to modify it.
* Add rbac to allow the plugin to access the cluster - [manifests/uumpa-plugin-rbac.yaml](manifests/uumpa-plugin-rbac.yaml).

## Usage

Enable the plugin in the ArgoCD application spec by adding the plugin section under source, for example:

```yaml
  source:
    plugin:
      name: uumpa
      env:
        # optional arguments to pass to the helm template command
        - name: HELM_ARGS
          value: --include-crds --values my-values.yaml
        # optional env vars which are available to be used later
        - name: ALERTMANAGER_USER
          value: admin
```

The plugin will handle the app as a Helm chart.

The basic functionality allows to get values from different sources and use them in the Helm chart, this is done
by creating file `uumpa_data.yaml` in the chart root directory:

```yaml
- # set values from the application spec plugin env vars (they are prefixed with ARGOCD_ENV_ for security reasons)
  alertmanager_user: ~ARGOCD_ENV_ALERTMANAGER_USER~
  # set values from global env vars which can be set on the plugin sidecar container
  domain_suffix: ~DOMAIN_SUFFIX~
  # can use dynamic values from other fields as part of strings
  alertmanager_domain: alertmanager.~domain_suffix~
  # set values from secret or configmap
  nfs_ip:
    type: secret
    namespace: default
    name: nfs
    key: ip
  alertmanager_secret:
    type: secret
    name: alertmanager-httpauth
    # this will set the value as a map of the keys and their values
    keys: [auth, password]
- # if statement is in Python code which has access to all the data from the previous items as local variables
  if: not alertmanager_secret.auth or not alertmanager_secret.password
  # generate a password, set it as a value in the alertmanager_secret map object
  alertmanager_secret.password:
    type: password
    length: 18
  # generate a httpauth string which can be used for nginx ingress auth
  # can also use values from other fields
  alertmanager_secret.auth:
    type: httpauth
    user: ~alertmanager_user~
    password: ~alertmanager_secret.password~
- nfs_initialized:
    type: configmap
    name: nfs-init
    key: initialized
# can also set values to objects, in this case data will contain a user object with name and password fields
- user.name: admin
  user.password:
    type: password
    length: 18
# this object can then be used in templates or other fields
- user_auth: ~user.name~:~user.password~
```

The same string templating will also be applied to the resulting templates from the Helm chart, so you can include
them either in the `values.yaml` or in the templates themselves as strings like ~alertmanager_auth~.

Another useful functionality is the ability to generate additional templates.
This is done in the `uumpa_generators.yaml` file:

```yaml
- type: secret
  name: alertmanager-httpauth
  data:
      auth: ~alertmanager_secret.auth~
      user: ~alertmanager_user~
      password: ~alertmanager_secret.password~
- # same as above, will only run based on this condition in Python code
  if: not nfs_initialized
  # creates a job as an argocd hook 
  type: job
  # Following 2 values are the same as the ArgoCD hook attributes, see https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/
  hook: PreSync
  hook-delete-policy: HookSucceeded
  name: nfs-init
  # path to the script relative to the chart root
  # the script will run as an executable, so make sure to add a shebang line
  script: init.sh
  # set env vars, allows to use values from the data section
  env:
    NSF_IP: ~nfs_ip~
    # if value is prefixed with FILE:: the value will be written to a file with the given name in file mode 0400
    NFS_ID_RSA: FILE::~nfs_id_rsa~
  # generators will run after this job completed successfully, or if the job was skipped due to it's if condition
  generators:
    - type: configmap
      name: nfs-init
      data:
        initialized: "true"
```

## Plugins

Plugins allow to extend the functionality, they are implemented as Python modules which are loaded dynamically.
Some plugins are bundled with the core plugin, to see how to use them see the README file for each plugin under 
[uumpa_argocd_plugin/plugins/](uumpa_argocd_plugin/plugins/).

## Generate templates locally

You can run the plugin locally to test it on a chart directory and see the resulting templates. This will output
the generated templates to stdout.

Make sure you have a local `kubectl` and are connected to the relevant cluster, so the plugin will be able to access
the secrets and configmaps.

Make sure to set any additional env vars which are needed for the plugin to run.

Create a virtualenv and install the plugin and dependencies:

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/pip install -e .
```

Generate the templates:

```bash
. venv/bin/activate
uumpa-argocd-plugin local-generate NAMESPACE_NAME /path/to/chart
```

Add helm args to pass to the helm template command:

```bash
uumpa-argocd-plugin local-generate NAMESPACE_NAME /path/to/chart --include-crds --values my-values.yaml
```

Output only the generators without the helm chart:

```bash
uumpa-argocd-plugin local-generate-generators NAMESPACE_NAME /path/to/chart
```

Run the jobs from the generators instead of rendering the helm templates

```bash
uumpa-argocd-plugin local-run-jobs NAMESPACE_NAME /path/to/chart [--dry-run]
```

## Reference

### Environment variables

| Name                               | Description                                                    | Default               |
|------------------------------------|----------------------------------------------------------------|-----------------------|
| ARGOCD_ENV_UUMPA_DATA_CONFIG       | Path to the data config file relative to the helm chart root   | uumpa_data.yaml       |
| ARGOCD_ENV_UUMPA_GENERATORS_CONFIG | Path to the hooks config file relative to the helm chart root  | uumpa_generators.yaml |
| ARGOCD_NAMESPACE                   | Namespace of the ArgoCD application, used to create jobs       | argocd                |
| ARGOCD_REPO_SERVER_DEPLOYMENT      | Name of the ArgoCD repo server deployment, used to create jobs | argocd-repo-server    |
| ARGOCD_UUMPA_PLUGIN_CONTAINER      | Name of the plugin sidecar container, used to create jobs      | uumpa                 |

### Common attributes

| Name   | Description                                                                                                 | Default                  |
|--------|-------------------------------------------------------------------------------------------------------------|--------------------------|
| plugin | Python module name of the plugin to use, if not set the core plugin will be used                            | uumpa_argocd_plugin.core |
| type   | Type of the attribute, see below for details, if a plugin has only a single type it will be used by default | -                        |
| if     | Python code which will be evaluated, has access to the data as local variables                              | -                        |

### Core data types

#### `secret` / `configmap`

Get values from a secret or a configmap:

* if `key` is set - get the value of the key
* if `keys` is set - get the values of the keys as a map of key: value
* if neither are set - get the whole secret or configmap as a map of key: value

| Name      | Description                          | Default               |
|-----------|--------------------------------------|-----------------------|
| type      | `secret` or `configmap`              | -                     |
| namespace | Namespace of the secret or configmap | current app namespace |
| name      | Name of the secret or configmap      | -                     |
| key       | Key of the secret or configmap       | -                     |
| keys      | List of keys to get from the secret  | -                     |

#### `password`

Generate a password using upper-case letters, lower-case letters and digits

| Name   | Description                        | Default |
|--------|------------------------------------|---------|
| type   | `password`                         | -       |
| length | Length of the password to generate | -       |

#### `httpauth`

Generate a httpauth string which can be used for nginx ingress auth

| Name     | Description                        | Default |
|----------|------------------------------------|---------|
| type     | `httpauth`                         | -       |
| user     | Username for the auth string       | -       |
| password | Password for the auth string       | -       |

## Core generators

#### `secret` / `configmap`

Generate a secret or configmap object

| Name      | Description                          | Default               |
|-----------|--------------------------------------|-----------------------|
| type      | `secret` or `configmap`              | -                     |
| namespace | Namespace of the secret or configmap | current app namespace |
| name      | Name of the secret or configmap      | -                     |
| data      | map of the key/values to set         | -                     |

#### `jobs`

Runs a script using the same image and configuration as the Uumpa argocd plugin sidecar container

| Name                   | Description                                                                                                       | Default                            |
|------------------------|-------------------------------------------------------------------------------------------------------------------|------------------------------------|
| type                   | `job`                                                                                                             | -                                  |
| hook                   | ArgoCD hook to run the job as, see https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/            | PreSync                            |
| hook-delete-policy     | ArgoCD hook delete policy, see https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/                | BeforeHookCreation                 |
| name                   | Name of the hook, required for identification, must be valid for Kubernetes job / configmap name                  | -                                  |
| script                 | Path to script relative to the chart root, script will run as executable so make sure it has a shebang            | -                                  |
| python-module-function | Name of python module function to run instead of the script                                                       | -                                  | 
| files                  | list of files to copy from the chart root to be available for the script                                          | -                                  |
| env                    | {key: value} env vars for the script, value prefixed with FILE:: will save to file mode 0400 and provide the path | -                                  |
| generators             | List of generators to run after the job completed                                                                 | -                                  |
| generators[].if        | Has access to additional variable: `_job_status` with values: "skip", "success", "fail"                           | _job_status in ["skip", "success"] |
