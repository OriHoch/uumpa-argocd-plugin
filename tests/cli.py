import click

from . import common


@click.group()
def main():
    pass


@main.command()
@click.option('--with-observability', is_flag=True)
@click.option('--build', is_flag=True)
@click.option('--skip-create-cluster', is_flag=True)
def start_infra(with_observability, build, skip_create_cluster):
    with common.start_infra(with_observability, build, skip_create_cluster):
        input('Test infra is running, press enter to stop port forwards')
    print("Port forwards stopped, but infra is still running, to destroy run: kind delete cluster")


if __name__ == '__main__':
    main()
