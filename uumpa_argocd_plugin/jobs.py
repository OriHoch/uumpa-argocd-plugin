import os
import glob
import json
import base64
import tempfile
import traceback
import importlib
import subprocess

from ruamel.yaml import safe_load

from . import data, generators, common


def dry_run_print_dir(tmpdir):
    for path in [*glob.glob(os.path.join(tmpdir, '**'), recursive=True),
                 *glob.glob(os.path.join(tmpdir, '.**'), recursive=True)]:
        if os.path.isfile(path):
            filemode = oct(os.stat(path).st_mode)[-3:]
            print(f'-- {path} -- {filemode}')
            with open(path) as f:
                print(f.read())


def run_job_script(generator, tmpdir, env, dry_run):
    script = generator['script']
    os.chmod(os.path.join(tmpdir, script), 0o755)
    if dry_run:
        print('\n-----------------\n')
        print(f'Run script: {script}\nenv: {env}')
        dry_run_print_dir(tmpdir)
        print('\n-----------------\n')
    else:
        subprocess.check_call([os.path.join(tmpdir, script)], cwd=tmpdir, env={**os.environ, **env})


def run_job_python(generator, tmpdir, env, dry_run):
    module, method = generator['python-module-function'].split(':')
    if dry_run:
        print(f'Run Python module: {module} method: {method}\nenv: {env}')
        dry_run_print_dir(tmpdir)
    else:
        getattr(importlib.import_module(module), method)(tmpdir, env)


def run_job_subgenerators(job_status, generator, data_, dry_run):
    print('running subgenerators...')
    subgenerators = []
    for subgenerator in generator.get('generators', []):
        if_ = subgenerator.get('if', '_job_status in ["skip", "success"]')
        if common.process_if(if_, {**data_, '_job_status': job_status}):
            subgenerators.append(subgenerator)
    loaded_modules = set()
    for item in generators.post_process_generator_items(generators.process_generators(subgenerators, data_, loaded_modules), data_, loaded_modules):
        if dry_run:
            print('---')
            print(item)
        else:
            subprocess.run(['kubectl', 'apply', '-f', '-'], input=json.dumps(item), text=True, check=True)


def run_job(job, job_files_b64, generator, data_, dry_run=False):
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, file_path in enumerate(job.get('file_paths', [])):
            os.makedirs(os.path.dirname(os.path.join(tmpdir, file_path)), exist_ok=True)
            with open(os.path.join(tmpdir, file_path), 'w') as f:
                f.write(base64.b64decode(job_files_b64[f'file_{i}']).decode())
        env = {}
        for k, v in generator.get('env', {}).items():
            v = common.render(v, data_)
            if v.startswith('FILE::'):
                env[k] = os.path.join(tmpdir, f'.{k}')
                with open(os.path.join(tmpdir, f'.{k}'), 'w') as f:
                    f.write(v[6:])
                os.chmod(os.path.join(tmpdir, f'.{k}'), 0o600)
            else:
                env[k] = v
        if generator.get('script'):
            assert not generator.get('python-module-function')
            run_job_script(generator, tmpdir, env, dry_run)
        elif generator.get('python-module-function'):
            run_job_python(generator, tmpdir, env, dry_run)
        else:
            raise ValueError(f'Job has neither script nor python-module-function: {generator}')


def _run_job(job, job_files_b64, generator, data_, dry_run=False):
    try:
        run_job(job, job_files_b64, generator, data_, dry_run=dry_run)
    except Exception:
        traceback.print_exc()
        job_status = 'fail'
    else:
        job_status = 'success'
    run_job_subgenerators(job_status, generator, data_, dry_run)
    return job_status == 'success'


def run_local(namespace_name, chart_path, *args):
    dry_run = '--dry-run' in args
    data_ = data.process(namespace_name, chart_path)
    job_files_b64 = {}
    jobs = {}
    for item in generators.process(data_):
        item = safe_load(item)
        item_type = item.get('metadata', {}).get('labels', {}).get('uumpa.argocd.plugin/item-type')
        if item_type == 'job-files':
            job_files_b64[item['metadata']['name']] = item['data']
        elif item_type == 'job':
            jobs[item['metadata']['generateName']] = json.loads(item['spec']['template']['spec']['containers'][0]['args'][1])
    has_failures = False
    for job_name, job in jobs.items():
        print(f'Running job {job_name}...')
        data_ = job.get('data', {})
        generator = job['generator']
        if not _run_job(job, job_files_b64.get(f'{job_name}-files', {}), generator, data_, dry_run=dry_run):
            has_failures = True
    if has_failures:
        raise Exception('Some jobs failed')


def run_argocd(job_json_b64, uumpa_job_files_path='/var/uumpa-job-files'):
    job = json.loads(base64.b64decode(job_json_b64).decode())
    generator = job['generator']
    data_ = job['data']
    job_files_b64 = {}
    for i, file_path in enumerate(job.get('file_paths', [])):
        with open(os.path.join(uumpa_job_files_path, f'file_{i}')) as f:
            job_files_b64[f'file_{i}'] = f.read().strip()
    assert _run_job(job, job_files_b64, generator, data_)
