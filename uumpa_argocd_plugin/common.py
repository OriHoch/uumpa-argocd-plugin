import os
import json

from ruamel.yaml import YAML


yaml = YAML(typ='safe', pure=True)


def yaml_load(stream):
    return yaml.load(stream)


def yaml_load_all(stream):
    return yaml.load_all(stream)


def yaml_dump_dict(d):
    assert isinstance(d, dict)
    out = []
    for k, v in d.items():
        out.append(f'{k}: {json.dumps(v)}')
    return '\n'.join(out) + '\n'


def render_string(v):
    if v or v in ['0', 0]:
        return str(v)
    else:
        return ''


def render(value, data_):
    for k, v in {**os.environ, **data_}.items():
        if isinstance(v, dict):
            value = value.replace(f'~{k}~', json.dumps(v))
            for k2, v2 in v.items():
                value = value.replace(f'~{k}.{k2}~', render_string(v2))
        else:
            value = value.replace(f'~{k}~', render_string(v))
    return value


def process_keyed_value(d, key, value, data_):
    key_ = value.get('key')
    keys = value.get('keys')
    assert not (key_ and keys), "can't specify both key and keys"
    if key_:
        data_[key] = d.get(key_)
    elif keys:
        data_[key] = {k: d.get(k) for k in keys}
    else:
        data_[key] = d


class IfLocalDict:
    def __init__(self, d):
        self.d = d

    def __getattr__(self, key):
        return self.d.get(key)


def process_if(if_, data_):
    if not if_:
        return True
    else:
        assert isinstance(if_, str)
        if_locals = {}
        for k, v in data_.items():
            if isinstance(v, dict):
                if_locals[k] = IfLocalDict(v)
            else:
                if_locals[k] = v
        return bool(eval(if_, {}, if_locals))
