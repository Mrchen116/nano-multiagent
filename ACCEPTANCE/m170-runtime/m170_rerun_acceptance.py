import asyncio
import json
import re
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

RUNTIME_ROOT = Path('/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime')
DB_PATH = RUNTIME_ROOT / 'im_service.sqlite3'
BASE_URL = 'http://127.0.0.1:18031'
CHAT_URL = f'{BASE_URL}/chat'
IM_LOG_PATH = RUNTIME_ROOT / 'im.log'

RESULT_ARTIFACT_NAME = 'm170-rerun-result.json'
SHOT_HOME_NAME = 'm170-rerun-home.png'
SHOT_GROUP_PANEL_NAME = 'm170-rerun-group-panel.png'
SHOT_THREAD_NAME = 'm170-rerun-group-thread.png'
SHOT_PICKER_NAME = 'm170-rerun-picker.png'
SHOT_NO_REPLY_NAME = 'm170-rerun-no-reply.png'

OUT_JSON = RUNTIME_ROOT / RESULT_ARTIFACT_NAME
SHOT_HOME = RUNTIME_ROOT / SHOT_HOME_NAME
SHOT_GROUP_PANEL = RUNTIME_ROOT / SHOT_GROUP_PANEL_NAME
SHOT_THREAD = RUNTIME_ROOT / SHOT_THREAD_NAME
SHOT_PICKER = RUNTIME_ROOT / SHOT_PICKER_NAME
SHOT_NO_REPLY = RUNTIME_ROOT / SHOT_NO_REPLY_NAME
FIRST_TURN_SETTLE_MS = 6000
TURN_TIMEOUT_MS = 90000
RERUN_SCREENSHOT_TARGETS = {
    SHOT_HOME_NAME: SHOT_HOME,
    SHOT_GROUP_PANEL_NAME: SHOT_GROUP_PANEL,
    SHOT_THREAD_NAME: SHOT_THREAD,
    SHOT_PICKER_NAME: SHOT_PICKER,
    SHOT_NO_REPLY_NAME: SHOT_NO_REPLY,
}
RERUN_REQUIRED_ARTIFACT_NAMES = (RESULT_ARTIFACT_NAME, *RERUN_SCREENSHOT_TARGETS.keys())


def _artifact_target_map() -> dict[str, Path]:
    return {
        RESULT_ARTIFACT_NAME: OUT_JSON,
        SHOT_HOME_NAME: SHOT_HOME,
        SHOT_GROUP_PANEL_NAME: SHOT_GROUP_PANEL,
        SHOT_THREAD_NAME: SHOT_THREAD,
        SHOT_PICKER_NAME: SHOT_PICKER,
        SHOT_NO_REPLY_NAME: SHOT_NO_REPLY,
    }


def _stage_artifact_path(staged_dir: Path, artifact_name: str) -> Path:
    return staged_dir / artifact_name


def _copy_into_place(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f'.{target_path.name}.tmp')
    shutil.copy2(source_path, temp_path)
    temp_path.replace(target_path)


def finalize_run_artifacts(*, result: dict[str, Any], staged_dir: Path) -> dict[str, Any]:
    staged_result_path = _stage_artifact_path(staged_dir, RESULT_ARTIFACT_NAME)
    if not staged_result_path.is_file():
        raise FileNotFoundError(staged_result_path.name)

    artifact_targets = _artifact_target_map()
    staged_screenshots = [Path(raw_path) for raw_path in result.get('screenshots') or []]
    for staged_path in staged_screenshots:
        if not staged_path.is_file():
            raise FileNotFoundError(staged_path.name)
        if staged_path.name not in RERUN_SCREENSHOT_TARGETS:
            raise ValueError(f'Unexpected screenshot artifact: {staged_path.name}')

    run_id = str(result.get('run_id') or 'unknown-run')
    archive_dir = staged_dir.parent / 'runs' / run_id
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_result_path = archive_dir / RESULT_ARTIFACT_NAME
    shutil.copy2(staged_result_path, archived_result_path)
    archived_screenshots: list[Path] = []
    for staged_path in staged_screenshots:
        archived_path = archive_dir / staged_path.name
        shutil.copy2(staged_path, archived_path)
        archived_screenshots.append(archived_path)

    published_result = dict(result)
    published_result['artifact_dir'] = str(archive_dir)
    published_result['screenshots'] = [str(artifact_targets[path.name]) for path in staged_screenshots]

    published_result_json = json.dumps(published_result, ensure_ascii=False, indent=2)
    archived_result_path.write_text(published_result_json, encoding='utf-8')
    temp_result_path = artifact_targets[RESULT_ARTIFACT_NAME].with_name(f'.{artifact_targets[RESULT_ARTIFACT_NAME].name}.tmp')
    temp_result_path.write_text(published_result_json, encoding='utf-8')
    temp_result_path.replace(artifact_targets[RESULT_ARTIFACT_NAME])
    for archived_path in archived_screenshots:
        _copy_into_place(archived_path, artifact_targets[archived_path.name])

    for staged_path in [staged_result_path, *staged_screenshots]:
        staged_path.unlink(missing_ok=True)
    staged_dir.rmdir()
    return published_result

ALPHA_ID = 'agent-m170-alpha'
BETA_ID = 'agent-m170-beta'
ALPHA_NAME = 'Agent M170 Alpha'
BETA_NAME = 'Agent M170 Beta'
ALPHA_ACK = 'ALPHA_ACK_M170'
BETA_ACK = 'BETA_ACK_M170'
NO_REPLY_TEXT = 'NO_REPLY'
NO_REPLY_FORBIDDEN_TEXTS = [
    NO_REPLY_TEXT,
    'suppressed_by=no_reply_token',
    'Agent is working',
    'Agent replied',
    'The latest agent response finished successfully.',
]


def fetchall_dicts(query: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()



def fetchone_dict(query: str, params: tuple = ()):
    rows = fetchall_dicts(query, params)
    return rows[0] if rows else None


async def send_message(page, text: str):
    composer = page.locator('textarea[placeholder="Type message"]')
    await composer.wait_for(timeout=20000)
    await composer.fill(text)
    await page.get_by_role('button', name='Send').click()



def latest_message_matching(snippet: str, *, conversation_id: str | None = None):
    if conversation_id:
        return fetchone_dict(
            'SELECT id, conversation_id, sender_user_id, sender_type, content, created_at FROM messages WHERE content = ? AND conversation_id = ? ORDER BY rowid DESC LIMIT 1',
            (snippet, conversation_id),
        )
    return fetchone_dict(
        'SELECT id, conversation_id, sender_user_id, sender_type, content, created_at FROM messages WHERE content = ? ORDER BY rowid DESC LIMIT 1',
        (snippet,),
    )



def latest_message_starting_with(prefix: str, *, conversation_id: str | None = None):
    if conversation_id:
        return fetchone_dict(
            'SELECT id, conversation_id, sender_user_id, sender_type, content, created_at FROM messages WHERE content LIKE ? AND conversation_id = ? ORDER BY rowid DESC LIMIT 1',
            (f'{prefix}%', conversation_id),
        )
    return fetchone_dict(
        'SELECT id, conversation_id, sender_user_id, sender_type, content, created_at FROM messages WHERE content LIKE ? ORDER BY rowid DESC LIMIT 1',
        (f'{prefix}%',),
    )



def _message_lookup_candidates(text: str) -> list[str]:
    candidates = [text]
    normalized = text.replace(' please', '\nplease', 1) if ' please' in text else text
    if normalized not in candidates:
        candidates.append(normalized)
    return candidates



def _latest_message_for_turn(text: str, *, conversation_id: str | None = None):
    for candidate in _message_lookup_candidates(text):
        message = latest_message_matching(candidate, conversation_id=conversation_id)
        if message:
            return message
    return latest_message_starting_with(text, conversation_id=conversation_id)



def relay_for_message(message_id: str):
    return fetchone_dict(
        'SELECT relay_task_id, message_id, conversation_id, target_node_id, payload_json, status, receipt_status, receipt_detail FROM relay_tasks WHERE message_id = ? ORDER BY rowid DESC LIMIT 1',
        (message_id,),
    )



def events_for_message(message_id: str):
    return fetchall_dicts(
        'SELECT event_id, event_type, delivery_status, payload_json, created_at FROM conversation_events WHERE message_id = ? ORDER BY rowid ASC',
        (message_id,),
    )



def _parse_payload_json(payload_json: str | None) -> dict[str, Any]:
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}



def _read_gateway_connection_state() -> str | None:
    if not IM_LOG_PATH.is_file():
        return None
    for line in reversed(IM_LOG_PATH.read_text(encoding='utf-8', errors='replace').splitlines()):
        if 'connection open' in line:
            return 'open'
        if 'connection closed' in line:
            return 'closed'
    return None



async def wait_for_gateway_connection_stable(page, *, timeout_ms: int = 30000, quiet_ms: int = 12000) -> dict[str, int | str | None]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1000)
    last_state = _read_gateway_connection_state()
    last_transition_at = loop.time()
    while True:
        current_state = _read_gateway_connection_state()
        now = loop.time()
        if current_state != last_state:
            last_state = current_state
            last_transition_at = now
        if last_state == 'open' and ((now - last_transition_at) * 1000) >= quiet_ms:
            return {'state': last_state, 'quiet_ms': quiet_ms}
        if now >= deadline:
            raise TimeoutError(f'Gateway websocket did not stay open for {quiet_ms}ms; last_state={last_state}')
        await page.wait_for_timeout(250)



def build_turn_result(*, message: dict[str, Any] | None, relay: dict[str, Any] | None, events: list[dict[str, Any]]) -> dict[str, Any]:
    relay_payload = _parse_payload_json(relay.get('payload_json') if relay else None)
    return {
        'message_id': message.get('id') if message else None,
        'conversation_id': message.get('conversation_id') if message else None,
        'relay_task_id': relay.get('relay_task_id') if relay else None,
        'receipt_detail': relay.get('receipt_detail') if relay else None,
        'mentioned_agent_ids': relay_payload.get('mentioned_agent_ids') or [],
        'config_profile_version': relay_payload.get('config_profile_version'),
        'event_types': [event.get('event_type') for event in events],
        'message': message,
        'relay': relay,
        'events': events,
    }



def build_no_reply_probe(*, body_text: str, message: dict[str, Any] | None, relay: dict[str, Any] | None, events: list[dict[str, Any]]) -> dict[str, Any]:
    violations = [text for text in NO_REPLY_FORBIDDEN_TEXTS if text in body_text]
    if relay and relay.get('receipt_detail') == NO_REPLY_TEXT and NO_REPLY_TEXT not in violations:
        violations.insert(0, NO_REPLY_TEXT)
    turn = build_turn_result(message=message, relay=relay, events=events)
    return {
        **turn,
        'status': 'passed' if not violations else 'failed',
        'violations': violations,
        'body_excerpt': body_text[:1000],
    }


async def wait_for_turn_completion(
    page,
    *,
    text: str,
    conversation_id: str | None = None,
    timeout_ms: int = 20000,
    poll_interval_ms: int = 500,
) -> dict[str, Any]:
    """Wait for a sent turn to finish in runtime storage.

    Args:
        page: Playwright page used for timeout pacing between polling attempts.
        text: Exact human message body sent through the composer.
        conversation_id: Optional conversation scope used to ignore stale matching turns from older chats.
        timeout_ms: Maximum wait budget in milliseconds.
        poll_interval_ms: Delay between DB polls in milliseconds.

    Returns:
        Structured turn result assembled from messages, relay tasks, and events.

    Raises:
        TimeoutError: When the runtime never records a completed relay for the message.

    Side Effects:
        Reads the runtime SQLite database until the turn reaches a stable completed state.
    """
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    while True:
        message = _latest_message_for_turn(text, conversation_id=conversation_id)
        if message:
            relay = relay_for_message(message['id'])
            events = events_for_message(message['id'])
            relay_completed = bool(relay) and relay.get('status') == 'completed'
            has_completion_event = any(event.get('event_type') == 'relay.completed' for event in events)
            if relay_completed and has_completion_event:
                return build_turn_result(message=message, relay=relay, events=events)
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f'Timed out waiting for completed relay for message: {text}')
        await page.wait_for_timeout(poll_interval_ms)


async def patch_agent(agent_id: str, system_prompt: str):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0, trust_env=False) as client:
        current = (await client.get(f'/im/v1/agents/{agent_id}/config')).json()
        payload = {
            'profile_version': current['profile_version'],
            'display_name': current['display_name'],
            'description': current.get('description') or '',
            'system_prompt': system_prompt,
            'skills': current.get('skills') or [],
            'tool_allowlist': current.get('tool_allowlist') or [],
            'group_reply_policy': current.get('group_reply_policy') or 'MENTION',
            'default_model': current.get('default_model'),
            'workspace_root': current.get('workspace_root') or '',
        }
        resp = await client.patch(f'/im/v1/agents/{agent_id}/config', json=payload)
        return {
            'status_code': resp.status_code,
            'body': resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text,
        }


async def _select_group_participant(page, label: str) -> None:
    candidate = page.locator('label').filter(has=page.get_by_text(label, exact=True)).first
    await candidate.wait_for(timeout=20000)
    await candidate.click()


async def _pick_mention_candidate(page, *, label: str, handle: str) -> None:
    del handle
    option_pattern = re.compile(rf'{re.escape(label)}\s+{re.escape(label)} mention', re.IGNORECASE)
    option = page.get_by_role('option').filter(has_text=option_pattern).first
    try:
        await option.wait_for(timeout=3000)
        await option.click()
        return
    except PlaywrightTimeoutError:
        pass

    options = page.get_by_role('option')
    deadline = asyncio.get_running_loop().time() + 20
    while True:
        count = await options.count()
        for index in range(count):
            candidate = options.nth(index)
            candidate_text = await candidate.inner_text()
            if label.lower() in candidate_text.lower():
                await candidate.click()
                return
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f'Timed out waiting for mention option matching {label}')
        await page.wait_for_timeout(250)


async def main():
    run_id = f"run-{uuid.uuid4().hex}"
    staged_dir = RUNTIME_ROOT / '.staging' / run_id
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged_home = _stage_artifact_path(staged_dir, SHOT_HOME_NAME)
    staged_group_panel = _stage_artifact_path(staged_dir, SHOT_GROUP_PANEL_NAME)
    staged_thread = _stage_artifact_path(staged_dir, SHOT_THREAD_NAME)
    staged_picker = _stage_artifact_path(staged_dir, SHOT_PICKER_NAME)
    staged_no_reply = _stage_artifact_path(staged_dir, SHOT_NO_REPLY_NAME)

    result = {
        'run_id': run_id,
        'chat_url': CHAT_URL,
        'runtime_db': str(DB_PATH),
        'screenshots': [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1440, 'height': 1100})
        await page.goto(CHAT_URL, wait_until='networkidle')
        await page.screenshot(path=str(staged_home), full_page=True)
        result['screenshots'].append(str(staged_home))

        await page.get_by_role('button', name='Create group chat').click()
        await page.get_by_text('Select participants').wait_for(timeout=20000)
        await page.screenshot(path=str(staged_group_panel), full_page=True)
        result['screenshots'].append(str(staged_group_panel))

        await _select_group_participant(page, ALPHA_NAME)
        await _select_group_participant(page, BETA_NAME)
        await page.get_by_role('button', name='Create selected group chat').click()
        await page.get_by_text(f'{ALPHA_NAME} + {BETA_NAME}', exact=False).first.wait_for(timeout=20000)
        await page.screenshot(path=str(staged_thread), full_page=True)
        result['screenshots'].append(str(staged_thread))

        conv = fetchone_dict('SELECT id, title, type, owner_id, config_profile_version FROM conversations ORDER BY rowid DESC LIMIT 1')
        result['conversation'] = conv
        result['participants'] = fetchall_dicts('SELECT conversation_id, user_id FROM conversation_participants WHERE conversation_id = ?', (conv['id'],))

        conversation_id = conv['id']
        result['gateway_connection_ready'] = await wait_for_gateway_connection_stable(page)
        await page.wait_for_timeout(FIRST_TURN_SETTLE_MS)

        alpha_text = '@agent-m170-alpha please answer exactly as configured.'
        await send_message(page, alpha_text)
        result['alpha_turn'] = await wait_for_turn_completion(
            page,
            text=alpha_text,
            conversation_id=conversation_id,
            timeout_ms=TURN_TIMEOUT_MS,
        )

        beta_text = '@agent-m170-beta please answer exactly as configured.'
        await send_message(page, beta_text)
        result['beta_turn'] = await wait_for_turn_completion(
            page,
            text=beta_text,
            conversation_id=conversation_id,
            timeout_ms=TURN_TIMEOUT_MS,
        )

        composer = page.locator('textarea[placeholder="Type message"]')
        await composer.fill('@agent:')
        await page.get_by_role('listbox', name='Mention candidates').wait_for(timeout=20000)
        picker_options = page.get_by_role('option')
        picker_texts = []
        for i in range(await picker_options.count()):
            picker_texts.append(await picker_options.nth(i).inner_text())
        picker_handle = '@agent:agent-m170-beta'
        await _pick_mention_candidate(page, label=BETA_NAME, handle=picker_handle)
        composer_value = await composer.input_value()
        picker_prompt = 'please answer via picker route.'
        picker_text = composer_value + picker_prompt
        picker_lookup_text = f'{picker_handle} {picker_prompt}'
        await send_message(page, picker_text)
        await page.screenshot(path=str(staged_picker), full_page=True)
        result['screenshots'].append(str(staged_picker))
        result['picker_turn'] = {
            **await wait_for_turn_completion(
                page,
                text=picker_lookup_text,
                conversation_id=conversation_id,
                timeout_ms=TURN_TIMEOUT_MS,
            ),
            'picker_options': picker_texts,
            'composer_value': composer_value,
            'submitted_text': picker_text,
            'expected_message_text': picker_lookup_text,
        }

        patch = await patch_agent(ALPHA_ID, 'Reply exactly with NO_REPLY.')
        result['alpha_patch_to_no_reply'] = patch

        no_reply_text = '@agent-m170-alpha please stay silent now.'
        await send_message(page, no_reply_text)
        await asyncio.sleep(5)
        body_text = await page.locator('body').inner_text()
        await page.screenshot(path=str(staged_no_reply), full_page=True)
        result['screenshots'].append(str(staged_no_reply))
        no_reply_msg = latest_message_matching(no_reply_text, conversation_id=conversation_id)
        no_reply_events = events_for_message(no_reply_msg['id'])
        no_reply_relay = relay_for_message(no_reply_msg['id'])
        result['no_reply_turn'] = build_no_reply_probe(
            body_text=body_text,
            message=no_reply_msg,
            relay=no_reply_relay,
            events=no_reply_events,
        )

        await browser.close()

    staged_result_path = _stage_artifact_path(staged_dir, RESULT_ARTIFACT_NAME)
    staged_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    published_result = finalize_run_artifacts(result=result, staged_dir=staged_dir)
    print(json.dumps(published_result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
