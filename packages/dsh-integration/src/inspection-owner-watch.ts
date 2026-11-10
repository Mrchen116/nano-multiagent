import {isMainThread, Worker, workerData} from 'node:worker_threads';

if (isMainThread) {
  // Preload before DSH boots so plugin code cannot block watchdog startup.
  const ownerPid = Number(process.env.NANO_CONFIGURATION_INSPECTION_OWNER_PID);
  const watchdog = new Worker(new URL(import.meta.url), {execArgv: [], workerData: ownerPid});
  watchdog.unref();
} else {
  // The inspector launched this process as its own POSIX process group.
  setInterval(() => {
    if (process.ppid !== workerData) process.kill(-process.pid, 'SIGKILL');
  }, 100);
}
