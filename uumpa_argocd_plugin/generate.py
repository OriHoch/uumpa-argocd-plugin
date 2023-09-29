import os
import subprocess

from . import data, common, generators, env


def generate_local(namespace_name, chart_path, *helm_args, only_generators=False):
    env.update_env(chart_path)
    if only_generators:
        assert not helm_args
    data_ = data.process(namespace_name, chart_path)
    output = [
        *generators.process(data_)
    ]
    if not only_generators:
        output.append(subprocess.check_output(['helm', 'template', '.', '--namespace', namespace_name, *helm_args], text=True, cwd=chart_path))
    output = common.render('\n---\n'.join(output), data_)
    output = post_process_output(output, data_)
    print(output)


def post_process_output(output, data_):
    for module in data_.pop('__loaded_modules'):
        if hasattr(module, 'post_process_output'):
            output = module.post_process_output(output, data_)
    return output


def generate_argocd():
    chart_path = os.getcwd()
    env.update_env(chart_path)
    app_name = os.environ['ARGOCD_APP_NAME']
    namespace_name = os.environ['ARGOCD_APP_NAMESPACE']
    kube_version = os.environ.get('KUBE_VERSION')
    kube_api_versions = os.environ.get('KUBE_API_VERSIONS')
    helm_args = os.environ.get('ARGOCD_ENV_HELM_ARGS')
    data_ = data.process(namespace_name, chart_path)
    cmd = f'helm template . --name-template {app_name} --namespace {namespace_name}'
    if kube_version:
        cmd += f' --kube-version {kube_version}'
    if kube_api_versions:
        for version in kube_api_versions.split(','):
            cmd += f' --api-versions {version}'
    if helm_args:
        cmd += f' {helm_args}'
    output = [
        *generators.process(data_),
        subprocess.check_output(cmd, shell=True, text=True, cwd=chart_path)
    ]
    output = common.render('\n---\n'.join(output), data_)
    output = post_process_output(output, data_)
    print(output)
