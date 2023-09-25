import sys

from . import generate, jobs


def main():
    cmd, *args = sys.argv[1:]
    if cmd == 'local-generate':
        generate.generate_local(*args)
    elif cmd == 'local-generate-generators':
        generate.generate_local(*args, only_generators=True)
    elif cmd == 'local-run-jobs':
        jobs.run_local(*args)
    elif cmd == 'generate':
        generate.generate_argocd()
    elif cmd == 'run-generator-job':
        jobs.run_argocd(*args)
    else:
        raise ValueError(f'Unknown command {cmd}')
