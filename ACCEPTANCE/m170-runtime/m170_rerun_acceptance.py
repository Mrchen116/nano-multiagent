import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import async_playwright

RUNTIME_ROOT = Path('/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime')
DB_PATH = RUNTIME_ROOT / 'im_service.sqlite3'
BASE_URL = 'http://127.0.0.1:18031'
CHAT_URL = f'{BASE_URL}/chat'

OUT_JSON = RUNTIME_ROOT / 'm170-rerun-result.json'
SHOT_HOME = RUNTIME_ROOT / 'm170-rerun-home.png'
SHOT_GROUP_PANEL = RUNTIME_ROOT / 'm170-rerun-group-panel.png'
SHOT_THREAD = RUNTIME_ROOT / 'm170-rerun-group-thread.png'
SHOT_PICKER = RUNTIME_ROOT / 'm170-rerun-picker.png'
SHOT_NO_REPLY = RUNTIME_ROOT / 'm170-rerun-no-reply.png'

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



def latest_message_matching(snippet: str):
    return fetchone_dict(
        'SELECT id, conversation_id, sender_user_id, sender_type, content, created_at FROM messages WHERE content = ? ORDER BY rowid DESC LIMIT 1',
        (snippet,),
    )



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


async def wait_for_turn_completion(page, *, text: str, timeout_ms: int = 20000, poll_interval_ms: int = 500) -> dict[str, Any]:
    """Wait for a sent turn to finish in runtime storage.

    Args:
        page: Playwright page used for timeout pacing between polling attempts.
        text: Exact human message body sent through the composer.
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
        message = latest_message_matching(text)
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
    option = page.get_by_role('option', name=f'{label} {handle}').first
    await option.wait_for(timeout=20000)
    await option.click()


async def main():
    result = {
        'chat_url': CHAT_URL,
        'runtime_db': str(DB_PATH),
        'screenshots': [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1440, 'height': 1100})
        await page.goto(CHAT_URL, wait_until='networkidle')
        await page.screenshot(path=str(SHOT_HOME), full_page=True)
        result['screenshots'].append(str(SHOT_HOME))

        await page.get_by_role('button', name='Create group chat').click()
        await page.get_by_text('Select participants').wait_for(timeout=20000)
        await page.screenshot(path=str(SHOT_GROUP_PANEL), full_page=True)
        result['screenshots'].append(str(SHOT_GROUP_PANEL))

        await _select_group_participant(page, ALPHA_NAME)
        await _select_group_participant(page, BETA_NAME)
        await page.get_by_role('button', name='Create selected group chat').click()
        await page.get_by_text(f'{ALPHA_NAME} + {BETA_NAME}', exact=False).first.wait_for(timeout=20000)
        await page.screenshot(path=str(SHOT_THREAD), full_page=True)
        result['screenshots'].append(str(SHOT_THREAD))

        conv = fetchone_dict('SELECT id, title, type, owner_id, config_profile_version FROM conversations ORDER BY rowid DESC LIMIT 1')
        result['conversation'] = conv
        result['participants'] = fetchall_dicts('SELECT conversation_id, user_id FROM conversation_participants WHERE conversation_id = ?', (conv['id'],))

        alpha_text = '@agent-m170-alpha please answer exactly as configured.'
        await send_message(page, alpha_text)
        result['alpha_turn'] = await wait_for_turn_completion(page, text=alpha_text)

        beta_text = '@agent-m170-beta please answer exactly as configured.'
        await send_message(page, beta_text)
        result['beta_turn'] = await wait_for_turn_completion(page, text=beta_text)

        composer = page.locator('textarea[placeholder="Type message"]')
        await composer.fill('@agent:')
        await page.get_by_role('listbox', name='Mention candidates').wait_for(timeout=20000)
        picker_options = page.get_by_role('option')
        picker_texts = []
        for i in range(await picker_options.count()):
            picker_texts.append(await picker_options.nth(i).inner_text())
        await _pick_mention_candidate(page, label=BETA_NAME, handle='@agent:agent-m170-beta')
        composer_value = await composer.input_value()
        picker_text = composer_value + 'please answer via picker route.'
        await send_message(page, picker_text)
        await page.screenshot(path=str(SHOT_PICKER), full_page=True)
        result['screenshots'].append(str(SHOT_PICKER))
        result['picker_turn'] = {
            **await wait_for_turn_completion(page, text=picker_text),
            'picker_options': picker_texts,
            'composer_value': composer_value,
        }

        patch = await patch_agent(ALPHA_ID, 'Reply exactly with NO_REPLY.')
        result['alpha_patch_to_no_reply'] = patch

        no_reply_text = '@agent-m170-alpha please stay silent now.'
        await send_message(page, no_reply_text)
        await asyncio.sleep(5)
        body_text = await page.locator('body').inner_text()
        await page.screenshot(path=str(SHOT_NO_REPLY), full_page=True)
        result['screenshots'].append(str(SHOT_NO_REPLY))
        no_reply_msg = latest_message_matching(no_reply_text)
        no_reply_events = events_for_message(no_reply_msg['id'])
        no_reply_relay = relay_for_message(no_reply_msg['id'])
        result['no_reply_turn'] = build_no_reply_probe(
            body_text=body_text,
            message=no_reply_msg,
            relay=no_reply_relay,
            events=no_reply_events,
        )

        await browser.close()

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
