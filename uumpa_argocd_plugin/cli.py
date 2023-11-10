import click


@click.group()
def main():
    pass


@main.command()
@click.option('--chart-path', help='Path to the chart (defaults to current directory)')
@click.option('--app-name', help='Target app name (ARGOCD_APP_NAME)')
@click.option('--namespace', help='Target namespace (ARGOCD_APP_NAMESPACE)')
@click.option('--kube-version',
              help='Kubernetes version to pass to helm template (KUBE_VERSION)')
@click.option('--kube-api-versions',
              help='Comma-separated list of supported Kubernetes API versions to pass to helm template (KUBE_API_VERSIONS)')
@click.option('--helm-args', help='Additional arguments to pass to helm template command (ARGOCD_ENV_HELM_ARGS)')
@click.option('--only-generators', is_flag=True,
              help='Only generate the generators, do not run helm template')
@click.option('--run-jobs', is_flag=True, help='Run the jobs after generating the manifests')
@click.option('--dry-run', is_flag=True,
              help="Don't perform any actions, just print the output (relevant only when running jobs)")
def generate(**kwargs):
    """Generate manifests for the given chart"""
    from . import generate
    generate.main(**kwargs)


@main.command()
@click.argument('job-json-b64')
def run_generator_job(job_json_b64):
    """Internal command to run a generator job from within the job container, for testing call generate with --run-jobs"""
    from . import jobs
    jobs.main(job_json_b64)


@main.command()
@click.option('--chart-path', help='Path to the chart (defaults to current directory)')
def init(**kwargs):
    """Initialize the given chart - called by ArgoCD before running generate"""
    from . import init
    init.main(**kwargs)


if __name__ == '__main__':
    main()
