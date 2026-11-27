import { expect, it } from 'vitest';
import { decodeNodeInput, decodeNodeResult, isNodeCommand, nodeCommands } from '../src/node-rpc.js';

it('validates node.wechat.setup.request actions and results without exposing invalid PINs', () => {
  expect(isNodeCommand('node.wechat.setup.request')).toBe(true);
  expect(nodeCommands['node.wechat.setup.request'].responseType).toBe('node.wechat.setup.result');

  expect(decodeNodeInput('node.wechat.setup.request', {
    action: 'start',
    agent_id: 'pa-main',
    editing_channel_id: 'ch_existing',
  })).toEqual({
    action: 'start',
    agent_id: 'pa-main',
    editing_channel_id: 'ch_existing',
  });

  expect(decodeNodeInput('node.wechat.setup.request', {
    action: 'verify_code',
    agent_id: 'pa-main',
    setup_id: 'setup-1',
    code: '482916',
  })).toEqual({
    action: 'verify_code',
    agent_id: 'pa-main',
    setup_id: 'setup-1',
    code: '482916',
  });

  expect(() => decodeNodeInput('node.wechat.setup.request', {
    action: 'verify_code',
    agent_id: 'pa-main',
    setup_id: 'setup-1',
    code: '12ab',
  })).toThrow(/Invalid node\.wechat\.setup\.request field code/);

  expect(decodeNodeResult('node.wechat.setup.request', {
    setup_id: 'setup-1',
    state: 'confirmed',
    binding: {
      bot_token: 'tok_secret_123',
      bot_id: 'wxbot_001',
      owner_user_id: 'wxid_owner_001',
      base_url: 'https://ilinkai.weixin.qq.com',
    },
  })).toMatchObject({
    setup_id: 'setup-1',
    state: 'confirmed',
    binding: {
      bot_id: 'wxbot_001',
      owner_user_id: 'wxid_owner_001',
    },
  });
});
