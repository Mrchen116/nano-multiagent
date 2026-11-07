"""Real IM and native DSH evidence adapter for the shared coordination engine."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

import httpx
from case import matches
from tests.e2e.critical_paths._im_client import IMClient


def read_wire(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.endswith('}')]


def native_events(run, session):
    archives = list((Path(run) / '.dsh-runtime').glob(f'*/sessions/*/{session}/session.v4.jsonl.zstd'))
    if len(archives) != 1:
        return []
    raw = subprocess.check_output(['zstd', '-qdc', str(archives[0])], text=True)
    return [json.loads(line) for line in raw.splitlines()]


def content_text(content):
    if isinstance(content, str):
        return content
    return '\n'.join(b.get('text', '') for b in content if b.get('type') == 'text')


def recipient_text(events):
    for event in events:
        data = event.get('data', {})
        if event['type'] == 'user/message' and data.get('source', {}).get('kind') in {'user', 'agent-message'}:
            yield {'seq': event['seq'], 'time': event.get('time'), 'text': content_text(data.get('content', []))}


def consumed_rows(events, wire, child, since=0):
    """Pair native receipt with an actual provider request containing that message."""
    compact = lambda text: re.sub(r'\s+', '', text)
    for receipt in recipient_text(events):
        if receipt['time'] < since * 1000:
            continue
        text = compact(receipt['text'])
        request = next((event for event in wire if event['type'] == 'child_request' and event['id'] == child
                        and event['at'] >= receipt['time'] and any(
                            message['role'] == 'user' and text in compact(content_text(message['content']))
                            for message in event['messages'])), None)
        if request:
            yield {**receipt, 'request_at': request['at']}


class Runtime:
    def __init__(self, run, case, arm, url, control, images, checkpoint=None):
        self.run, self.case, self.arm = Path(run), case, arm
        self.control, self.images = control, images
        self.client = IMClient(url)
        self.login_at = 0
        self.login()
        self.chat = checkpoint['chat'] if checkpoint else self.client.create_direct_conversation(
            'coord-' + arm.lower(), title=case['id'].upper() + ' ' + arm)
        self.root = checkpoint.get('root') if checkpoint else None
        self.wire, self.native = [], {}
        self.messages = []
        self.state = None

    def login(self):
        if time.monotonic() - self.login_at >= 600:
            self.client.register_or_login('nano', 'nano1234')
            self.login_at = time.monotonic()

    def refresh(self):
        self.login()
        self.wire = read_wire(self.run / 'wire.jsonl')
        self.root = next((e['root'] for e in self.wire if e['type'] == 'root_request' and e['arm'] == self.arm), self.root)
        self.messages = self.client.list_messages(self.chat, limit=100)
        self.native = {}

    def events(self, child):
        if child not in self.native:
            self.native[child] = native_events(self.run, child)
        return self.native[child]

    def children(self):
        return list(dict.fromkeys(e['id'] for e in self.wire
                                  if e['type'] == 'child_request' and e['root'] == self.root))

    def condition(self, when, node, state):
        if not when:
            return {}
        if when.get('evidence_node'):
            receipt = state['nodes'][when['evidence_node']].get('receipt', {})
            return receipt if matches(receipt.get('text', ''), when['matcher'], state['nodes']) else None
        return self.public_match(node, state, when['matcher'])

    def public_match(self, node, state, matcher):
        lower = max((state['nodes'][d].get('receipt', {}).get('at', state['nodes'][d]['completed_at'])
                     for d in node.get('after', []) + node.get('order_after', [])), default=0)
        reports = node.get('after_report', [])
        if isinstance(reports, str):
            reports = [reports]
        report_request = None
        for report in reports:
            body = state['nodes'][report]['text']
            child = state['nodes'][report]['receipt']['child']
            report_request = next((e for e in self.wire if e['type'] == 'root_request' and e['root'] == self.root
                                   and any(m.get('role') == 'user' and f'Agent {child} sent a message:' in content_text(m['content'])
                                           and body in content_text(m['content']) for m in e['messages'])), None)
            if not report_request:
                return None
            lower = max(lower, report_request['at'] / 1000)
        for message in self.messages:
            at = datetime.fromisoformat(message['created_at']).timestamp()
            if message['sender']['type'] != 'agent' or at < lower:
                continue
            if matches(message['content'], matcher, state['nodes']):
                return {'message_id': message['id'], 'text': message['content'], 'at': at,
                        'root_request_at': report_request['at'] if report_request else None}
        return None

    def observe(self, node, state):
        self.state = state
        if node['type'] == 'user_reply':
            return self.public_match(node, state, node['matcher'])
        worker = node['worker']
        source = node['matcher'].get('source_node')
        since = state['nodes'].get(source, {}).get('receipt', {}).get('at', 0)
        if node['type'] == 'delegate':
            candidates = []
            for child in self.children():
                receipt = next((r for r in consumed_rows(self.events(child), self.wire, child, since)
                                if matches(r['text'], node['matcher'], state['nodes'])), None)
                if receipt:
                    candidates.append((child, receipt))
            selected = None
            binding_file = self.run / 'bindings.json'
            if binding_file.exists():
                selected = json.loads(binding_file.read_text()).get(self.arm, {}).get(worker)
            if selected:
                candidates = [c for c in candidates if c[0] == selected]
            if len(candidates) != 1:
                state['nodes'][node['id']]['candidates'] = [c[0] for c in candidates]
                if not candidates and node['matcher'].get('source_node'):
                    for child in self.children():
                        self.advance_queued(node, state, child)
                return None
            child, receipt = candidates[0]
            state['workers'][worker] = child
            return {'child': child, **receipt, 'at': receipt['time'] / 1000}
        child = state['workers'].get(worker)
        if not child:
            return None
        receipt = next((r for r in consumed_rows(self.events(child), self.wire, child, since)
                        if matches(r['text'], node['matcher'], state['nodes'])), None)
        if receipt:
            return {'child': child, **receipt, 'at': receipt['time'] / 1000, 'delivery': 'consumed'}
        self.advance_queued(node, state, child)
        return None

    def advance_queued(self, node, state, child):
        source = node['matcher'].get('source_node')
        since = state['nodes'].get(source, {}).get('receipt', {}).get('at', 0)
        queued = next((e for e in self.events(child) if e['type'] == 'agent/inbox/spliced' and e.get('time', 0) >= since * 1000
                       and any(matches(content_text(item.get('content', [])), node['matcher'], state['nodes'])
                               for item in e['data'].get('inserted', []))), None)
        if queued:
            progress = state['nodes'][node['id']]
            progress['queued'] = {'child': child, 'seq': queued['seq'], 'delivery': 'queued'}
            if source and not progress.get('advance'):
                progress['advance'] = {'child': child, 'seq': queued['seq'], 'at': time.time(), 'fixture': True}
                # Persist before dispatch, so resume cannot repeat a fixture action.
                self.save(state)
                self.control_action({'id': child, 'step': node['id'] + '-advance', 'tool': 'read',
                                     'path': 'AGENTS.md'})

    def control_action(self, body):
        response = httpx.post(self.control + '/control', json=body)
        response.raise_for_status()
        return response.json()

    def dispatch(self, node, text, state):
        self.login()
        at = time.time()
        if node['type'] == 'worker_message':
            child = state['workers'][node['worker']]
            receipt = self.control_action({'id': child, 'step': node['id'], 'text': text, 'final': node.get('final', False)})
            return {'child': child, 'at': at, 'delivery': 'queued', **receipt}
        attachments = []
        for key in node.get('attachments', []):
            path = Path(self.images[key])
            response = self.client._http.post('/im/v1/uploads', headers={**self.client._auth_headers, 'Content-Type': 'image/png'},
                                             params={'file_name': key + path.suffix, 'conversation_id': self.chat}, content=path.read_bytes())
            response.raise_for_status()
            attachments.append(response.json())
        response = self.client._http.post(f'/im/v1/conversations/{self.chat}/messages',
                                         headers={**self.client._auth_headers, 'Idempotency-Key': f'{self.case["id"]}-{self.arm}-{node["id"]}'},
                                         json={'sender': {'type': 'user', 'id': self.client.user_id},
                                               'content': text, 'attachments': attachments})
        response.raise_for_status()
        return {'message_id': response.json()['id'], 'at': at, 'attachments': attachments}

    def probe_images(self, state):
        if not self.images:
            return
        probes = state.setdefault('image_probes', {})
        for child in self.children():
            for receipt in recipient_text(self.events(child)):
                for token in re.findall(r"/[^\s\x60'\"<>：（）()「」]+/attachments/v1/objects/[0-9a-f]{2}/[0-9a-f]{64}", receipt['text']):
                    start = token.find(str(self.run) + '/')
                    if start < 0:
                        continue
                    path = Path(token[start:]).resolve()
                    if self.run.resolve() not in path.parents or not path.is_file():
                        continue
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    for key, original in self.images.items():
                        identity = child + ':' + key
                        if identity in probes or digest != hashlib.sha256(Path(original).read_bytes()).hexdigest():
                            continue
                        probes[identity] = {'child': child, 'attachment': key, 'path': str(path), 'sha256': digest}
                        self.save(state)
                        self.control_action({'id': child, 'step': key + '-probe', 'tool': 'read_image', 'path': str(path)})

    def close(self):
        self.client.close()
