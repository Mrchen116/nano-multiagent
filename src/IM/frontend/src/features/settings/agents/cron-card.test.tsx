import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {render, screen, fireEvent, waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {describe,it,expect,vi} from 'vitest';
import {CronCard} from './agent-detail-page';
import {i18n} from '../../../i18n';
import {formatSchedule} from './schedule-display';
vi.mock('./im-agent-config-api', async importOriginal => ({...await importOriginal<object>(),deleteAgentCronJob:vi.fn().mockResolvedValue(undefined),getAgentSettingsSection:vi.fn().mockResolvedValue({source:'current',data:[]})}));
import {deleteAgentCronJob} from './im-agent-config-api';
const job=(id:string,enabled:boolean)=>({id,name:id,instruction:'Saved instructions',enabled,schedule:{kind:'after',scheduledAt:'2020-01-01T00:00:00Z'},delete_after_run:false});
function show(jobs:ReturnType<typeof job>[]) {
 const client=new QueryClient();client.setQueryData(['settings','agents','a','cron'],{source:'current',data:jobs});
 return render(<MemoryRouter><QueryClientProvider client={client}><CronCard readOnly={false} operationReadOnly={false} agentId="a" draft={{features:{cron_scheduling:true}}} onToggle={()=>{}} hideEnableToggle/></QueryClientProvider></MemoryRouter>);
}
describe('current plans',()=>{
 it('hides inactive plans, preserves overdue active plans, and cancels by id',async()=>{
  show([job('expired',false),job('pending',true)]);
  expect(screen.queryByText('expired')).not.toBeInTheDocument();expect(screen.getByText('pending')).toBeInTheDocument();
  expect(screen.getByText('Saved instructions').closest('details')).not.toHaveAttribute('open');
  fireEvent.click(screen.getByText('View details'));expect(screen.getByText('Saved instructions').closest('details')).toHaveAttribute('open');
  fireEvent.click(screen.getByRole('button',{name:'Cancel plan pending'}));await waitFor(()=>expect(deleteAgentCronJob).toHaveBeenCalledWith('a','pending'));
 });
 it('shows the empty state when only inactive history remains',()=>{show([job('expired',false)]);expect(screen.getByText('No scheduled tasks pending')).toBeInTheDocument();});
 it('formats all recurring native schedule kinds without exposing JSON',()=>{
  const format=(s:Record<string,unknown>)=>formatSchedule({scheduledAt:'2026-11-01T10:00:00Z',...s},'en',i18n.t.bind(i18n));
  expect(format({kind:'every',everySeconds:3600})).toContain('Every 1 hour');
  expect(format({kind:'daily',time:'18:00:00.000',timeZone:'Asia/Shanghai'})).toContain('Daily at 18:00 (Asia/Shanghai)');
  expect(format({kind:'weekly',weekdays:[1,7],time:'18:00:00.000',timeZone:'UTC'})).toContain('Mon and Sun');
  expect(format({kind:'cron',expression:'0 18 * * *',timeZone:'UTC'})).toContain('Custom recurrence');
 });
});
