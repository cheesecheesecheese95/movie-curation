// api/track.js — 방문자 이벤트 수집 + 집계 조회 (Upstash Redis)
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const url   = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) return res.status(500).json({ error: 'env missing' });

  const today = new Date().toISOString().slice(0, 10);

  async function redis(cmd) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(cmd),
    });
    return (await r.json()).result;
  }

  async function hgetall(key) {
    const raw = await redis(['HGETALL', key]) || [];
    const obj = {};
    for (let i = 0; i < raw.length; i += 2) obj[raw[i]] = parseInt(raw[i + 1]) || 0;
    return obj;
  }

  // ── GET: 집계 조회 ──
  if (req.method === 'GET') {
    if (req.query.mode === 'daily') {
      const days = Math.min(parseInt(req.query.days) || 14, 60);
      const dates = [];
      for (let i = 0; i < days; i++) {
        const d = new Date(); d.setDate(d.getDate() - i);
        dates.push(d.toISOString().slice(0, 10));
      }
      const results = await Promise.all(dates.map(date => hgetall(`dwia:daily:${date}`)));
      const daily = {};
      dates.forEach((date, i) => { daily[date] = results[i]; });
      return res.json({ daily });
    }

    const [total, todayData] = await Promise.all([
      hgetall('dwia:total'),
      hgetall(`dwia:daily:${today}`),
    ]);
    return res.json({ total, today: todayData });
  }

  // ── POST: 이벤트 수집 ──
  if (req.method !== 'POST') return res.status(405).end();

  const { event } = req.body || {};
  if (!event || typeof event !== 'string' || event.length > 60) {
    return res.status(400).json({ error: 'invalid event' });
  }

  await Promise.all([
    redis(['HINCRBY', 'dwia:total', event, 1]),
    redis(['HINCRBY', `dwia:daily:${today}`, event, 1]),
  ]);

  return res.json({ ok: true });
}
