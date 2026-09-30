import { useEffect, useState } from "react";
export function useAuthCooldown() {
  const [until, setUntil] = useState(0);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (until <= Date.now()) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  return { remaining: Math.max(0, Math.ceil((until - now) / 1000)), start: (seconds: number) => { setNow(Date.now()); setUntil(Date.now() + Math.max(1, seconds) * 1000); } };
}
