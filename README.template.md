# Uumpa ArgoCD Plugin

## Install

* Add the plugin sidecar to the argocd-repo-server deployment, 
  see [kustomize/install/patch-argocd-repo-server-deployment.yaml](kustomize/install/patch-argocd-repo-server-deployment.yaml)
  for details, if you are using Kustomize you can use that file as a base for a strategic merge patch.
* Add the plugin configuration - [kustomize/install/uumpa-plugin-configmap.yaml](kustomize/install/uumpa-plugin-configmap.yaml), for
  most common use-cases you will not need to modify it.
* Add rbac to allow the plugin to access the cluster - [kustomize/install/uumpa-plugin-rbac.yaml](kustomize/install/uumpa-plugin-rbac.yaml).

## Usage

Enable the plugin in the ArgoCD application spec by adding the plugin section under source, for example:

```yaml
  source:
# -- SNIPPET argocd_app_plugin --
```

The plugin will handle the app as a Helm chart.

You can define additional env vars in the chart path at `uumpa_env.yaml`, for example:

```yaml
# -- SNIPPET uumpa_env --
```

The basic functionality allows to get values from different sources and use them in the Helm chart, this is done
by creating file `uumpa_data.yaml` in the chart root directory:

```yaml
# -- SNIPPET uumpa_data --
```

The same string templating will also be applied to the resulting templates from the Helm chart, so you can include
them either in the `values.yaml` or in the templates themselves as strings like ~alertmanager_auth~.

Another useful functionality is the ability to generate additional templates.
This is done in the `uumpa_generators.yaml` file:

```yaml
# -- SNIPPET uumpa_generators --
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

Create a virtualenv and install the plugin and dependencies 
(this assumes you cloned the uumpa-argocd-plugin repo to directory `~/uumpa-argocd-plugin`):

```bash
python3 -m venv venv
venv/bin/pip install -r ~/uumpa-argocd-plugin/requirements.txt
venv/bin/pip install -e ~/uumpa-argocd-plugin
```

Generate the templates:

```bash
. venv/bin/activate
uumpa-argocd-plugin generate --namespace NAMESPACE_NAME --chart-path /path/to/chart
```

You can also pass additional arguments to the helm template command:

```bash
uumpa-argocd-plugin generate --namespace NAMESPACE_NAME --chart-path /path/to/chart --helm-args "--include-crds --values my-values.yaml"
```

Output only the generators without the helm chart:

```bash
uumpa-argocd-plugin generate --namespace NAMESPACE_NAME --chart-path /path/to/chart --only-generators
```

You can also run the generator jobs locally, this will run the jobs locally on your machine:

```bash
uumpa-argocd-plugin generate --namespace NAMESPACE_NAME --chart-path /path/to/chart --run-jobs
```

## Reference

### Environment variables

| Name                                          | Description                                                                      | Default               |
|-----------------------------------------------|----------------------------------------------------------------------------------|-----------------------|
| ARGOCD_ENV_UUMPA_DATA_CONFIG                  | Path to the data config file relative to the helm chart root                     | uumpa_data.yaml       |
| ARGOCD_ENV_UUMPA_GENERATORS_CONFIG            | Path to the hooks config file relative to the helm chart root                    | uumpa_generators.yaml |
| ARGOCD_ENV_UUMPA_ENV_CONFIG                   | Path to the env config file relative to the helm chart root                      | uumpa_env.yaml        |
| ARGOCD_NAMESPACE                              | Namespace of the ArgoCD application, used to create jobs                         | argocd                |
| ARGOCD_REPO_SERVER_DEPLOYMENT                 | Name of the ArgoCD repo server deployment, used to create jobs                   | argocd-repo-server    |
| ARGOCD_UUMPA_PLUGIN_CONTAINER                 | Name of the plugin sidecar container, used to create jobs                        | uumpa                 |
| ARGOCD_UUMPA_GLOBAL_DATA_CONFIG               | Absolute path to a global data config file                                       | -                     |
| ARGOCD_UUMPA_GLOBAL_GENERATORS_CONFIG         | Absolute path to a global generators config file                                 | -                     |
| ARGOCD_ENV_INIT_PLUGIN_FUNCTIONS              | Comma separated list of plugin functions to run on initialization (if needed)    | -                     |
| ARGOCD_ENV_GENERATE_TEMPLATE_PLUGIN_FUNCTIONS | Comma separated list of plugin functions to run on generate template (if needed) | -                     |
| ARGOCD_ENV_HELM_ARGS                          | Additional arguments to pass to the helm template command                        | -                     |

Env vars prefixed with `ARGOCD_ENV_` must be set in the ArgoCD app spec without this prefix, for example:

```
  source:
    plugin:
      name: uumpa
      env:
        # ARGOCD_ENV_HELM_ARGS
        - name: HELM_ARGS
          value: --include-crds --values my-values.yaml
```

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

### Core generators

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
| hook                   | ArgoCD hook to run the job as, see https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/            | Sync                            |
| hook-delete-policy     | ArgoCD hook delete policy, see https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/                | BeforeHookCreation                 |
| name                   | Name of the hook, required for identification, must be valid for Kubernetes job / configmap name                  | -                                  |
| script                 | Path to script relative to the chart root, script will run as executable so make sure it has a shebang            | -                                  |
| python-module-function | Name of python module function to run instead of the script                                                       | -                                  | 
| files                  | list of files to copy from the chart root to be available for the script                                          | -                                  |
| env                    | {key: value} env vars for the script, value prefixed with FILE:: will save to file mode 0400 and provide the path | -                                  |
| generators             | List of generators to run after the job completed                                                                 | -                                  |
| generators[].if        | Has access to additional variable: `_job_status` with values: "skip", "success", "fail"                           | _job_status in ["skip", "success"] |

### Core init functions

#### `init_helm`

Handles helm initialization, it's recommended not to rely on this handle initialization before committing your chart code.

However, if needed, this plugin will run helm initialization base on the following env vars:

| Name                                       | Description                                                   | Default |
|--------------------------------------------|---------------------------------------------------------------|---------|
| ARGOCD_ENV_INIT_HELM_DEPENDENCY_BUILD      | Set to "true" to run helm dependency build                    | -       |
| ARGOCD_ENV_INIT_HELM_DEPENDENCY_BUILD_ARGS | Additional arguments to pass to helm dependency build command | -       |

Example usage:

```
  source:
    plugin:
      name: uumpa
      env:
        - name: INIT_PLUGIN_FUNCTIONS
          value: init_helm
        - name: INIT_HELM_DEPENDENCY_BUILD
          value: "true"
```

### Plugins Development

Plugins are Python packages which expose the following functions:

#### `process_value(key, value, data)`

##### Arguments

| Name      | Type | Description                                               |
|-----------|------|-----------------------------------------------------------|
| key       | str  | the key to set in the data                                |
| value     | str  | a dict containing the value definition (plugin dependant) |
| data      | dict | the uumpa argocd plugin data                              |

##### Process

The function should set the key in the data dict to the given value, after processing it.

It has no return value.

##### Examples

Get a value and set it in the data dict: 

```python
import os
import uumpa_argocd_plugin.common

def get_value_from_server(object_name):
    # do something to get the value of object_name from a server
    # You can use env vars here to get the server URL / credentials
    # this env var will need to be set on the sidecar container
    os.environ.get('MY_SERVER_CREDENTIALS')
    # this env var can also be set in the argocd app definition
    os.environ.get('ARGOCD_ENV_MY_SERVER_URL')
    # get the value from the server and return it
    return "my-value"

def process_value(key, value, data):
    # the common.render function should be called to in process_value functions to support variable substitutions
    object_name = uumpa_argocd_plugin.common.render(value["object_name"], data)
    data[key] = get_value_from_server(value["object_name"])
```

Another common use-case is to get multiple values from an object like a secret or configmap:

```python
def process_value(key, value, data):
    # this will get the namespace name from either the data value or from the current app namespace
    namespace = common.render(value.get('namespace') or data['__namespace_name'], data)
    secret_name = common.render(value['name'], data)
    secret_data = get_secret(namespace, secret_name)
    # now we have a dict containing key/value pairs from the secret
    # the common.process_keyed_value allows to set either the whole dict, subset of keys or a single key
    # depending on the value attributes `key` / `keys` - see the documentation for `secret` / `configmap` types for details
    common.process_keyed_value(secret_data, key, value, data)
```

#### `process_generator(generator, data, is_skipped)`

##### Arguments

| Name       | Type | Description                                                      |
|------------|------|------------------------------------------------------------------|
| generator  | dict | the generator definition                                         |
| data       | dict | the uumpa argocd plugin data                                     |
| is_skipped | bool | True if the generator should be skipped due to it's if condition |

##### Proess

The function should yield `dict` items which can be either Kubernetes objects or other generators.

Kubernetes objects need to be yielded as a dict containing the Kubernetes object definition.

Generators need to be yielded as a dict containing a single attribute `generator` which contains the generator definition.

Generators should not modify the `data` dict, and can assume all values are already rendered, so no need to call
`common.render` on them like in the `process_value` function.

If the `is_skipped` argument is True, the generator should not perform its main functionality, but can still yield items
if needed.

##### Example

```python
def process_generator(generator, data):
    # checking the type is optional, only in case your plugin supports different generator types
    if generator["type"] == "my-special-type":
        # yield a Kubernetes Object 
        yield {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                # This will use either the namespace from the generator or the current app namespace
                "namespace": generator.get('namespace') or data['__namespace_name'],
                # in this example the name must be specified on the generator
                "name": generator["name"],
            },
            "data": {
                # my-value will need to be set in the uumpa_data.yaml file
                "my-key": data['my-value'],
            },
        }
        # yield another generator which will be processed after this one
        yield {
          "generator": {
              "plugin": "my_plugin_library.my_plugin",
              "name": data["my-name"]
          },
        }
```

#### `post_process_generator_items(items, data)`

##### Arguments

| Name   | Type | Description                        |
|--------|------|------------------------------------|
| items  | list | list of items which were generated |
| data   | dict | the uumpa argocd plugin data       |

##### Process

This function allows to modify the generated items before they are returned to the caller. It will be called if it's
implemented by the plugin, and if the plugin yielded at least one item from the `process_generator` function.

Common use cases are to do bulk processing of multiple generator items, or to delete / modify items.

it returns a tuple (`is_changed`, `items`), where `is_changed` is a boolean indicating if the items were changed,
and `items` is a list of items which will be returned to the caller.

##### Example

This examples shows how to do bulk processing:

```python
# this process_generator function only yields an item which will be identified by the post_process_generator_items function
def process_generator(generator, data):
    yield {'__my_identifier': 'my_generator', 'generator': generator}

def post_process_generator_items(items, data):
    # we first need to filter out the items which were generated by this generator
    new_items, my_generators = [], []
    for item in items:
        # we can use the __my_identifier attribute to identify our generators
        if item.get('__my_identifier') == 'my_generator':
            my_generators.append(item['generator'])
        else:
            new_items.append(item)
    if len(my_generators) > 0:
        # now we can append a single item which will do the processing for all my_generators
        new_items.append(get_my_item(my_generators, data))
        # return True to indicate that the items were changed
        return True, new_items
    else:
        # return False to indicate that the items were not changed
        return False, new_items
```

#### `post_process_output(output, data)`

##### Arguments

| Name   | Type | Description                                                              |
|--------|------|--------------------------------------------------------------------------|
| output | str  | the full output string from the helm template command and the generators |
| data   | dict | the uumpa argocd plugin data                                             |

##### Process

This function allows to modify the output before it's returned to the caller. It will be called if it's implemented by
the plugin, and if the plugin yielded at least one item from the `process_generator` function.

The function should return the modified output string.

#### `run_generator_job(tmpdir, env)`

##### Arguments

| Name   | Type | Description                                                                                      |
|--------|------|--------------------------------------------------------------------------------------------------|
| tmpdir | str  | path to a temporary directory which will contain the job files, can use it also for temp storage |
| env    | dict | env vars which can be used by the job                                                            |

##### Process

This function depensd on the jobs core generator to allow plugins to run python code or scripts.

##### Example

```python
# the plugin generator yields a job generator
def process_generator(generator, data):
    # yield a job generator, see the core generators documentation for jobs for more details
    yield {'generator': {
        'type': 'job',
        'name': 'my_task',
        # the plugin package and function name to run (it's not strictly required to be called run_generator_job)
        'python-module-function': 'my_plugin:run_generator_job',
        'env': {
            # this env var will be available to the job, env vars must be strings so we need to serialize it
            'MY_GENERATOR_JSON': json.dumps(generator)
        }
    }}

# here the plugin runs the job which will be called by the job generator
def run_generator_job(tmpdir, env):
    # get the generator from the env var
    generator = json.loads(env['MY_GENERATOR_JSON'])
    # do something with the generator
```
