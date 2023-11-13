import os
import subprocess

from . import data, common, generators, env, jobs, observability


def post_process_output(output, data_):
    for module in data_.pop('__loaded_modules'):
        if hasattr(module, 'post_process_output'):
            output = module.post_process_output(output, data_)
    return output


def main(chart_path=None, app_name=None, namespace=None, kube_version=None, kube_api_versions=None, helm_args=None,
         only_generators=False, run_jobs=False, dry_run=False):
    chart_path = chart_path or os.getcwd()
    env.update_env(chart_path)
    app_name = app_name or os.environ.get('ARGOCD_APP_NAME')
    namespace = namespace or os.environ.get('ARGOCD_APP_NAMESPACE')
    kube_version = kube_version or os.environ.get('KUBE_VERSION')
    kube_api_versions = kube_api_versions or os.environ.get('KUBE_API_VERSIONS')
    helm_args = helm_args or os.environ.get('ARGOCD_ENV_HELM_ARGS')
    with observability.start_as_current_span(main, f'({app_name})', attributes=dict(
        chart_path=chart_path, app_name=app_name, namespace=namespace, kube_version=kube_version,
        kube_api_versions=kube_api_versions, helm_args=helm_args, only_generators=only_generators, run_jobs=run_jobs,
        dry_run=dry_run
    )):
        assert namespace, 'namespace is required as argument or as env var ARGOCD_APP_NAMESPACE'
        data_ = data.process(namespace, chart_path)
        observability.set_attributes(data=data_)
        output = [*generators.process(data_)]
        if not only_generators:
            cmd = f'helm template . --namespace {namespace}'
            if app_name:
                cmd += f' --name-template {app_name}'
            if kube_version:
                cmd += f' --kube-version {kube_version}'
            if kube_api_versions:
                for version in kube_api_versions.split(','):
                    if version.strip():
                        cmd += f' --api-versions {version.strip()}'
            if helm_args:
                cmd += f' {helm_args}'
            with observability.start_as_current_span('helm_template', attributes={'cmd': cmd, 'cwd': chart_path}):
                output.append(subprocess.check_output(cmd, shell=True, text=True, cwd=chart_path))
        output = common.render('\n---\n'.join(output), data_)
        output = post_process_output(output, data_)
        observability.add_event('output', attributes={'output': output})
        print(output)
        if run_jobs:
            jobs.main_local(output, dry_run=dry_run)
