import { describe, expect, it } from 'vitest';
import { loadCases, parseHistoryDate } from './dataset.js';

const raw = () => ({
  question_id: 'sample_abs', question_type: 'knowledge-update', question: 'FUTURE_QUESTION',
  answer: 'GOLD_ONLY', question_date: '2024/04/01 (Mon) 09:00',
  haystack_session_ids: ['later', 'earlier'],
  haystack_dates: ['2024/03/02 (Sat) 10:30', '2024/01/02 (Tue) 08:00'],
  haystack_sessions: [
    [{role:'user',content:'Latest fact. '.repeat(900),has_answer:true},{role:'assistant',content:'Noted latest.'}],
    [{role:'assistant',content:'Earlier answer.'},{role:'user',content:'Earlier fact.'},{role:'user',content:'More detail.'}],
  ], answer_session_ids: ['later'],
});

describe('LongMemEval data boundary', () => {
  it('retains every turn and date while keeping future questions and labels outside preparation', () => {
    const source=raw(); const [item]=loadCases([source]);
    expect(item.history.sessions.map(s=>s.date)).toEqual([source.haystack_dates[1],source.haystack_dates[0]]);
    expect(item.history.sessions[0].turns).toEqual(source.haystack_sessions[1]);
    expect(item.history.sessions[1].turns[0]).toEqual({role:'user',content:source.haystack_sessions[0][0].content});
    const visible=JSON.stringify(item.history);
    for(const hidden of ['FUTURE_QUESTION','GOLD_ONLY','has_answer','sample_abs','knowledge-update','answer_session_ids','2024/04/01']) expect(visible).not.toContain(hidden);
    expect(item.question).toMatchObject({text:'FUTURE_QUESTION',date:source.question_date});
    expect(JSON.stringify(item.question)).not.toContain('_abs');
    expect(item.gold).toMatchObject({questionId:'sample_abs',answer:'GOLD_ONLY',abstention:true});
  });
  it('preserves date precision and deterministic order without depending on the host timezone', () => {
    expect(parseHistoryDate('2024/01/02 (Tue) 08:00')).toBe(Date.UTC(2024,0,2,8));
    expect(parseHistoryDate('2024-01-02T08:00:00+08:00')).toBe(Date.UTC(2024,0,2));
    expect(parseHistoryDate('2024/01/02')).toBe(Date.UTC(2024,0,2));
    expect(()=>parseHistoryDate('unknown')).toThrow(/date/i);
    const source=raw();source.haystack_dates.fill('2024/01/02');
    expect(loadCases([source])[0].history.sessions[0].turns[0].content).toBe(source.haystack_sessions[0][0].content);
  });
  it('refuses ambiguous or incomplete selection instead of silently dropping questions or history', () => {
    const source=raw(); expect(()=>loadCases([source,source])).toThrow(/duplicate/i);
    expect(()=>loadCases([source],['missing'])).toThrow(/missing/i);
    expect(()=>loadCases([{...source,haystack_dates:[]}])).toThrow(/length/i);
    expect(()=>loadCases([{...source,haystack_sessions:[[{role:'system',content:'x'}],[]]}])).toThrow(/role/i);
  });
});
