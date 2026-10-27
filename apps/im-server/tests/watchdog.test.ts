import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it, vi } from 'vitest';
import { createServer } from '../src/server.js';

it('times out only running replies whose latest event or creation predates the cutoff', async () => {
  vi.useFakeTimers({toFake:['setInterval','clearInterval','Date']});
  const base = Date.parse('2026-10-27T00:00:00Z');
  vi.setSystemTime(base);
  vi.stubEnv('IM_RELAY_WATCHDOG_INTERVAL_SECONDS', '30');
  vi.stubEnv('IM_RELAY_WATCHDOG_TIMEOUT_SECONDS', '120');
  const directory = mkdtempSync(join(tmpdir(), 'im-watchdog-'));
  const app = await createServer({dbPath:join(directory,'im.db'),publicUrl:'http://localhost',jwtSecret:'watchdog-test'});
  const db = app.im.db, time = (offset: number) => new Date(base + offset * 1000).toISOString();
  try {
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('u','u','U','u',?)").run(time(-300));
    db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('c','C',?)").run(time(-300));
    const message = db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,content,delivery_status,created_at) VALUES(?,'c','u',?,?,?)");
    message.run('stale-empty','','running',time(-200));
    message.run('stale-text','Keep this','running',time(-200));
    message.run('active','Live','running',time(-200));
    message.run('boundary','Boundary','running',time(-90));
    message.run('completed','Done','completed',time(-200));
    const event = db.prepare("INSERT INTO conversation_events(conversation_id,message_id,event_type,delivery_status,payload_json,created_at) VALUES('c',?,'message.delta','running','{}',?)");
    event.run('stale-text',time(-100));
    // Late insertion of an older event must not replace the actual latest activity.
    event.run('active',time(0)); event.run('active',time(-180));
    await vi.advanceTimersByTimeAsync(30_000);
    const rows = db.prepare('SELECT id,content,delivery_status FROM messages ORDER BY id').all();
    expect(rows).toEqual([
      {id:'active',content:'Live',delivery_status:'running'},
      {id:'boundary',content:'Boundary',delivery_status:'running'},
      {id:'completed',content:'Done',delivery_status:'completed'},
      {id:'stale-empty',content:'relay idle for 120s with no new event',delivery_status:'failed'},
      {id:'stale-text',content:'Keep this\n\nrelay idle for 120s with no new event',delivery_status:'failed'},
    ]);
    expect(db.prepare("SELECT message_id FROM conversation_events WHERE event_type='relay.failed' ORDER BY message_id").all()).toEqual([{message_id:'stale-empty'},{message_id:'stale-text'}]);
  } finally { await app.close(); rmSync(directory,{recursive:true,force:true}); vi.useRealTimers(); vi.unstubAllEnvs(); }
});
