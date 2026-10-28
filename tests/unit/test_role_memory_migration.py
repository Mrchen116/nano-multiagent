"""Migration verification uses synthetic offline copies, never real user data."""
import json
from pathlib import Path
import stat
from unittest.mock import patch

import pytest
import yaml

from scripts import migrate_role_memory as migration


def fixture(tmp_path):
    workspace = tmp_path / 'subject'
    memory = workspace / '.nanoassistant/memory'
    memory.mkdir(parents=True)
    (memory / 'USER.md').write_bytes('偏好\r\n保持原字节\n'.encode())
    (memory / 'MEMORY.md').write_bytes(b'# old\n')
    (memory / 'custom').mkdir()
    (memory / 'custom/fact.md').write_bytes(b'custom source')
    (memory / '.git').mkdir()
    (memory / '.git/config').write_bytes(b'git metadata')
    config = tmp_path / 'node.yaml'
    config.write_text(yaml.safe_dump({'node':{'node_id':'n'}, 'agents':[{'agent_id':'a', 'workspace_root':str(workspace), 'features':{'memory_curation':False,'skill_creation':False}, 'knowledge':{'memoryInterval':17}, 'skills':['skill-creator','other'],'skills_selection_mode':'explicit_denylist','tool_allowlist':['read'],'custom_prompt':'keep'}]}))
    baseline = {'activationAt':1234,'agents':{'a':{'streams':{'root':42}}}}
    return config, workspace, memory, baseline


def test_requires_stopped_writers_and_explicit_persistent_baseline(tmp_path):
    config, _, memory, baseline = fixture(tmp_path)
    before = migration.snapshot(memory)
    with pytest.raises(ValueError, match='Stop'):
        migration.migrate(config, baseline, 'test')
    with pytest.raises(ValueError, match='cursors'):
        migration.migrate(config, {'activationAt':1234,'agents':{}}, 'test', True)
    assert migration.snapshot(memory) == before
    assert not (memory.parent / 'memory-legacy').exists()


def test_preserves_bytes_permissions_choices_and_progress_on_repeat(tmp_path):
    config, workspace, memory, baseline = fixture(tmp_path)
    original = config.read_bytes()
    before = migration.snapshot(memory)
    report = migration.migrate(config, baseline, 'test', True)[0]
    root = memory.parent
    backup = root / 'memory-backups/test'
    assert migration.snapshot(root / 'memory-legacy') == before
    assert migration.contents(migration.snapshot(backup / 'memory')) == migration.contents(before)
    assert (backup / 'node-config.original').read_bytes() == original
    assert stat.S_IMODE(backup.stat().st_mode) == 0o700
    assert stat.S_IMODE((backup / 'memory/USER.md').stat().st_mode) == 0o600
    assert '偏好' not in (memory / 'MEMORY.md').read_text()
    assert 'memory-backups/test/memory' in (memory / 'MEMORY.md').read_text()
    agent = yaml.safe_load(config.read_text())['agents'][0]
    assert agent['knowledge'] == {'enabled':True,'memoryMode':'document','legacyMemory':{'enabled':False,'interval':17}}
    assert agent['features'] == {'dreaming':True}
    assert agent['skills'] == ['other']
    assert agent['skills_selection_mode'] == 'explicit_denylist'
    assert agent['tool_allowlist'] == ['read']
    assert agent['custom_prompt'] == 'keep'
    assert report['missingTools'] == ['write','edit','memory_maintenance']
    state = root / 'maintenance/dreaming-state.json'
    assert json.loads(state.read_text())['streams'] == {'root':{'baseline':42,'cursor':42}}
    state.write_text(json.dumps({'activationAt':1234,'streams':{'root':{'baseline':42,'cursor':75}}}))
    (memory / 'MEMORY.md').write_text('new content must survive')
    (root / 'memory-legacy/USER.md').write_text('new legacy content must survive')
    for mode in ['legacy', 'document']:
        value = yaml.safe_load(config.read_text())
        value['agents'][0]['knowledge']['memoryMode'] = mode
        config.write_text(yaml.safe_dump(value))
        migration.migrate(config, baseline, 'test', True)
        assert yaml.safe_load(config.read_text())['agents'][0]['knowledge']['memoryMode'] == mode
        assert (memory / 'MEMORY.md').read_text() == 'new content must survive'
        assert json.loads(state.read_text())['streams']['root']['cursor'] == 75


@pytest.mark.parametrize('failed_write', range(1, 8))
def test_recovers_each_persistent_write_interruption(tmp_path, failed_write):
    config, _, memory, baseline = fixture(tmp_path)
    before = migration.snapshot(memory)
    write = migration.atomic_write
    count = 0

    def fail_once(path, data):
        nonlocal count
        count += 1
        if count == failed_write:
            raise OSError('simulated process interruption')
        return write(path, data)

    with patch.object(migration, 'atomic_write', fail_once):
        with pytest.raises(OSError, match='interruption'):
            migration.migrate(config, baseline, 'test', True)
    migration.migrate(config, baseline, 'test', True)
    assert migration.snapshot(memory.parent / 'memory-legacy') == before
    assert 'Legacy backup:' in (memory / 'MEMORY.md').read_text()
    assert json.loads((memory.parent / 'memory-backups/test/manifest.json').read_text())['phase'] == 'completed'


def test_refuses_conflicting_library_or_baseline_without_overwrite(tmp_path):
    config, _, memory, baseline = fixture(tmp_path)
    legacy = memory.parent / 'memory-legacy'
    legacy.mkdir()
    (legacy / 'MEMORY.md').write_text('someone else')
    with pytest.raises(ValueError, match='refusing overwrite'):
        migration.migrate(config, baseline, 'test', True)
    assert (legacy / 'MEMORY.md').read_text() == 'someone else'
    assert (memory / 'USER.md').exists()


def test_changed_migration_baseline_cannot_replace_progress(tmp_path):
    config, _, memory, baseline = fixture(tmp_path)
    migration.migrate(config, baseline, 'test', True)
    state = memory.parent / 'maintenance/dreaming-state.json'
    before = state.read_bytes()
    baseline['agents']['a']['streams']['root'] = 99
    with pytest.raises(ValueError, match='baseline changed'):
        migration.migrate(config, baseline, 'test', True)
    assert state.read_bytes() == before
