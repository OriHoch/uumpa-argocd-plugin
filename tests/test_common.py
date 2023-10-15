import os
import json
import base64

import pytest

from uumpa_argocd_plugin import common


@pytest.mark.parametrize("v, expected", [
    ('test', 'test'),
    (0, '0'),
    ('0', '0'),
    (False, 'False'),
    (True, 'True'),
    (None, ''),
])
def test_render_string(v, expected):
    assert common.render_string(v) == expected


@pytest.mark.parametrize("value, data, expected", [
    ('Hello ~name~, how are you?', {'name': 'user'}, 'Hello user, how are you?'),
    ('Hello ~name~, how are you?', {}, 'Hello ~name~, how are you?'),
    ('Hello ~user.name~, how are you?', {'user': {'name': 'user'}}, 'Hello user, how are you?'),
    ('Hello ~user.name~, how are you?', {'user': {}}, 'Hello ~user.name~, how are you?'),
    (
        json.dumps({'production': {'alertmanager_secret': '~alertmanager_secret:base64~'}}),
        {'alertmanager_secret': {'user': 'admin'}},
        json.dumps({'production': {'alertmanager_secret': base64.b64encode(json.dumps({'user': 'admin'}).encode()).decode()}})
    ),
])
def test_render(value, data, expected):
    assert common.render(value, data) == expected


def test_render_env():
    path = os.environ['PATH']
    assert common.render('your path is: ~PATH~', {}) == f'your path is: {path}'


@pytest.mark.parametrize("d, key, value, data, expected", [
    # value has neither key nor keys attribute - copy d as-is
    ({}, "key", {}, {}, {}),
    ({"foo": "bar", "baz": "bax"}, "key", {}, {}, {"foo": "bar", "baz": "bax"}),
    # value has key attribute - set the value of the key from d
    ({}, "key", {"key": "foo"}, {}, None),
    ({"foo": "bar"}, "key", {"key": "foo"}, {}, "bar"),
    # value has keys attribute - set the value of the keys from d
    ({"foo": "bar", "baz": "bax", "xxx": "yyy"}, "key", {"keys": ["foo", "baz"]}, {}, {"foo": "bar", "baz": "bax"}),
    ({"foo": "bar", "xxx": "yyy"}, "key", {"keys": ["foo", "baz"]}, {}, {"foo": "bar", "baz": None}),
])
def test_process_keyed_value(d, key, value, data, expected):
    common.process_keyed_value(d, key, value, data)
    assert data[key] == expected


def test_process_keyed_value_exception():
    with pytest.raises(AssertionError, match="^can't specify both key and keys$"):
        common.process_keyed_value({}, "key", {"key": "a", "keys": ["b", "c"]}, {})


@pytest.mark.parametrize("if_, data, expected", [
    (None, {}, True),
    ("", {}, True),
    ("True", {}, True),
    ("False", {}, False),
    ("True", {"foo": "bar"}, True),
    ("False", {"foo": "bar"}, False),
    ("foo == 'bar'", {"foo": "bar"}, True),
    ("foo == 'bar'", {"foo": "baz"}, False),
    ("foo == 'bar' and baz == 'bax'", {"foo": "bar", "baz": "bax"}, True),
    ("foo == 'bar' and baz == 'bax'", {"foo": "bar", "baz": "baz"}, False),
    ("user.admin", {"user": {"admin": True}}, True),
    ("user.admin", {"user": {"admin": False}}, False),
    ("user.admin", {"user": {}}, False),
])
def test_process_if(if_, data, expected):
    assert common.process_if(if_, data) == expected

