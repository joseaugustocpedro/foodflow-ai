import json
import os
import pytest
from desktop.launcher import load_database, offline


def test_database_default_outside_bundle(tmp_path):
    assert load_database(tmp_path) == tmp_path / 'demo.sqlite3'


def test_existing_database_not_overwritten(tmp_path):
    db = tmp_path / 'demo.sqlite3'
    db.write_bytes(b'preserved')
    assert load_database(tmp_path) == db
    assert db.read_bytes() == b'preserved'


def test_active_selector_persists(tmp_path):
    name = 'demo-' + 'a' * 32 + '.sqlite3'
    (tmp_path / 'active.json').write_text(json.dumps({'database': name}))
    assert load_database(tmp_path).name == name


@pytest.mark.parametrize('name', ['../private.sqlite3', 'C:/private.sqlite3'])
def test_selector_rejects_escape(tmp_path, name):
    (tmp_path / 'active.json').write_text(json.dumps({'database': name}))
    with pytest.raises(ValueError):
        load_database(tmp_path)


def test_offline_neutralizes_inherited_flags(monkeypatch, tmp_path):
    for name in ['OPENAI_API_KEY', 'N8N_WEBHOOK_URL', 'FOODFLOW_ALLOW_ONLINE_LLM', 'FOODFLOW_WORKER']:
        monkeypatch.setenv(name, 'synthetic-test-only')
    before = dict(os.environ)
    try:
        offline(tmp_path / 'demo.sqlite3')
        assert 'OPENAI_API_KEY' not in os.environ
        assert 'N8N_WEBHOOK_URL' not in os.environ
        assert os.environ['FOODFLOW_WORKER'] == 'false'
        assert os.environ['FOODFLOW_ALLOW_ONLINE_LLM'] == 'false'
        assert os.environ['FOODFLOW_DB_PATH'] == str(tmp_path / 'demo.sqlite3')
    finally:
        os.environ.clear()
        os.environ.update(before)
