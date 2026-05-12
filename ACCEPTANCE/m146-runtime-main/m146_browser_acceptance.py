import asyncio
import json
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

RUNTIME_ROOT = Path('/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m146-runtime-main')
BASE_URL = 'http://127.0.0.1:18146'
BIND_URL = 'http://127.0.0.1:18146/bind/confirm?token=7093d60da3d74c3d8c9af2c543ca497d'
USER_ID = 'm146-browser-user'
AGENT_ID = 'agent-m146-main-browser-final'
AGENT_NAME = 'Agent M146 Main Browser Final'
OLD_TOKEN = 'M146_OLD_PROMPT_TOKEN'
NEW_TOKEN = 'M146_NEW_PROMPT_TOKEN'
OLD_EXPECT = 'OLD_PROMPT_OK_M146'
NEW_EXPECT = 'NEW_PROMPT_OK_M146'

SHOT_AGENTS_LIST = RUNTIME_ROOT / 'm146-agents-list.png'
SHOT_AGENT_CREATE = RUNTIME_ROOT / 'm146-agent-create.png'
SHOT_AGENT_DETAIL = RUNTIME_ROOT / 'm146-agent-detail.png'
SHOT_CHAT_BEFORE = RUNTIME_ROOT / 'm146-chat-before-send.png'
SHOT_CHAT_AFTER = RUNTIME_ROOT / 'm146-chat-after-send.png'
SHOT_FRESH_ENTRY = RUNTIME_ROOT / 'm146-fresh-session-entry.png'
SHOT_OLD_AFTER_EDIT = RUNTIME_ROOT / 'm146-old-session-after-edit.png'
SHOT_NEW_AFTER_FRESH = RUNTIME_ROOT / 'm146-new-session-after-fresh.png'
OUT_JSON = RUNTIME_ROOT / 'm146-browser-evidence.json'


async def api(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, trust_env=False) as client:
        resp = await client.request(method, path, **kwargs)
        content_type = resp.headers.get('content-type', '')
        body = resp.json() if content_type.startswith('application/json') else resp.text
        return resp.status_code, body


async def ensure_user():
    payload = {'user_id': USER_ID, 'display_name': 'M146 Browser Reviewer'}
    return await api('PATCH', f'/im/v1/me?user_id={USER_ID}', json=payload)


async def agent_config(agent_id: str):
    status, body = await api('GET', f'/im/v1/agents/{agent_id}/config')
    if status != 200:
        raise RuntimeError(f'agent_config failed: {status} {body}')
    return body


async def patch_prompt(agent_id: str, system_prompt: str):
    current = await agent_config(agent_id)
    payload = {
        'profile_version': current['profile_version'],
        'display_name': current['display_name'],
        'description': current.get('description') or '',
        'system_prompt': system_prompt,
        'skills': current.get('skills') or [],
        'tool_allowlist': current.get('tool_allowlist') or [],
        'group_reply_policy': current.get('group_reply_policy') or 'mentioned_only',
        'default_model': current.get('default_model'),
        'workspace_root': current.get('workspace_root') or '',
    }
    return await api('PATCH', f'/im/v1/agents/{agent_id}/config', json=payload)


async def wait_for_text(page, text: str, timeout: int = 60000):
    await page.get_by_text(text, exact=False).first.wait_for(timeout=timeout)


async def wait_for_response_snippet(page, snippet: str, timeout_ms: int = 90000):
    deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
    while True:
        body = await page.locator('body').inner_text()
        if snippet in body:
            return body
        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError(f'missing snippet: {snippet}')
        await asyncio.sleep(1)


async def main():
    result = {
        'base_url': BASE_URL,
        'bind_url': BIND_URL,
        'user_id': USER_ID,
        'agent_id': AGENT_ID,
        'screenshots': [],
    }

    result['ensure_user'] = {
        'status_code': (await ensure_user())[0],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1440, 'height': 1200})

        await page.goto(BIND_URL, wait_until='networkidle')
        await page.screenshot(path=str(RUNTIME_ROOT / 'm146-bind-confirm.png'), full_page=True)
        result['screenshots'].append(str(RUNTIME_ROOT / 'm146-bind-confirm.png'))
        result['bind_page_url_after_confirm'] = page.url

        await page.goto(f'{BASE_URL}/settings/agents', wait_until='networkidle')
        await wait_for_text(page, 'Agents', timeout=30000)
        await page.wait_for_timeout(1000)

        status_code, nodes_body = await api('GET', '/im/v1/nodes')
        result['nodes_after_bind'] = {'status_code': status_code, 'body': nodes_body}
        node_owner = None
        for item in nodes_body:
            if item.get('node_id') == 'm146-main-node':
                node_owner = item.get('owner_id')
                break
        result['node_owner_after_bind'] = node_owner

        await page.goto(f'{BASE_URL}/settings/agents', wait_until='networkidle')
        await wait_for_text(page, 'Agents', timeout=30000)
        await page.wait_for_timeout(1000)

        await page.screenshot(path=str(SHOT_AGENTS_LIST), full_page=True)
        result['screenshots'].append(str(SHOT_AGENTS_LIST))

        await page.get_by_role('link', name='New Agent').click()
        await page.wait_for_url('**/settings/agents/new', timeout=30000)
        await page.screenshot(path=str(SHOT_AGENT_CREATE), full_page=True)
        result['screenshots'].append(str(SHOT_AGENT_CREATE))

        await page.get_by_label('Agent ID').fill(AGENT_ID)
        await page.get_by_label('Display Name').fill(AGENT_NAME)
        await page.get_by_label('Description').fill('M146 current main fresh browser acceptance agent')
        await page.get_by_label('System Prompt').fill(
            f'Always reply with {OLD_EXPECT} when the user message contains {OLD_TOKEN}. '
            f'Always reply with {NEW_EXPECT} when the user message contains {NEW_TOKEN}. '
            'For any other message, reply briefly in plain text.'
        )
        await page.get_by_label('Node').select_option('m146-main-node')
        await page.get_by_role('button', name='Create Agent').click()
        await wait_for_text(page, 'Agent created. Open its dedicated direct chat now or keep editing in Settings.', timeout=30000)
        await page.screenshot(path=str(SHOT_AGENT_DETAIL), full_page=True)
        result['screenshots'].append(str(SHOT_AGENT_DETAIL))

        status_code, agents_body = await api('GET', '/im/v1/agents')
        result['agents_after_create'] = {'status_code': status_code, 'body': agents_body}
        created_agent = None
        for item in agents_body:
            if item.get('agent_id') == AGENT_ID:
                created_agent = item
                break
        result['created_agent_summary'] = created_agent
        if created_agent is None:
            raise RuntimeError('Browser create flow did not persist the new agent in /im/v1/agents')

        await page.goto(f'{BASE_URL}/settings/agents/{AGENT_ID}', wait_until='networkidle')
        await wait_for_text(page, 'Agent Detail', timeout=30000)
        await wait_for_text(page, AGENT_ID, timeout=30000)
        result['agent_detail_url'] = page.url
        await page.screenshot(path=str(SHOT_AGENT_DETAIL), full_page=True)

        await page.get_by_role('button', name='Open direct chat').click()
        await page.wait_for_url('**/chat/**', timeout=30000)
        result['old_chat_url'] = page.url
        await page.screenshot(path=str(SHOT_CHAT_BEFORE), full_page=True)
        result['screenshots'].append(str(SHOT_CHAT_BEFORE))

        composer = page.locator('textarea[placeholder="Type message"]')
        await composer.wait_for(timeout=30000)
        await composer.fill(f'{OLD_TOKEN} please verify old session behavior')
        await page.get_by_role('button', name='Send').click()
        await wait_for_response_snippet(page, OLD_EXPECT)
        await page.screenshot(path=str(SHOT_CHAT_AFTER), full_page=True)
        result['screenshots'].append(str(SHOT_CHAT_AFTER))

        await page.goto(f'{BASE_URL}/settings/agents/{AGENT_ID}', wait_until='networkidle')
        prompt_box = page.get_by_label('System prompt')
        await prompt_box.fill(
            f'Always reply with {NEW_EXPECT} when the user message contains {NEW_TOKEN}. '
            f'If the message contains {OLD_TOKEN}, reply with {NEW_EXPECT} instead of the old token. '
            'For any other message, reply briefly in plain text.'
        )
        await page.get_by_role('button', name='Save Agent').click()
        await wait_for_text(page, 'Saved just now', timeout=30000)

        await page.goto(result['old_chat_url'], wait_until='networkidle')
        await composer.wait_for(timeout=30000)
        await composer.fill(f'{OLD_TOKEN} old session should stay old')
        await page.get_by_role('button', name='Send').click()
        await wait_for_response_snippet(page, OLD_EXPECT)
        await page.screenshot(path=str(SHOT_OLD_AFTER_EDIT), full_page=True)
        result['screenshots'].append(str(SHOT_OLD_AFTER_EDIT))

        fresh_button = page.get_by_role('button', name='Start fresh session')
        await fresh_button.wait_for(timeout=30000)
        await page.screenshot(path=str(SHOT_FRESH_ENTRY), full_page=True)
        result['screenshots'].append(str(SHOT_FRESH_ENTRY))
        await fresh_button.click()
        await page.wait_for_url('**/chat/**', timeout=30000)
        result['new_chat_url'] = page.url
        await composer.wait_for(timeout=30000)
        await composer.fill(f'{NEW_TOKEN} new session should use new prompt')
        await page.get_by_role('button', name='Send').click()
        await wait_for_response_snippet(page, NEW_EXPECT)
        await page.screenshot(path=str(SHOT_NEW_AFTER_FRESH), full_page=True)
        result['screenshots'].append(str(SHOT_NEW_AFTER_FRESH))

        await browser.close()

    cfg = await agent_config(AGENT_ID)
    result['agent_config_after_test'] = cfg
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


asyncio.run(main())
