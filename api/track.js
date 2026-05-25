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

    // 영화별 랭킹 조회
    if (req.query.mode === 'ranking') {
      const [clicks, plays, searches] = await Promise.all([
        hgetall('dwia:movie:click'),
        hgetall('dwia:movie:play'),
        hgetall('dwia:search'),
      ]);
      return res.json({ clicks, plays, searches });
    }

    const [total, todayData] = await Promise.all([
      hgetall('dwia:total'),
      hgetall(`dwia:daily:${today}`),
    ]);
    return res.json({ total, today: todayData });
  }

  // ── POST: 이벤트 수집 ──
  if (req.method !== 'POST') return res.status(405).end();

  const { event, movie, query } = req.body || {};
  if (!event || typeof event !== 'string' || event.length > 60) {
    return res.status(400).json({ error: 'invalid event' });
  }

  const tasks = [
    redis(['HINCRBY', 'dwia:total', event, 1]),
    redis(['HINCRBY', `dwia:daily:${today}`, event, 1]),
  ];

  // 영화별 클릭/재생 카운트
  if (movie && typeof movie === 'string' && movie.length <= 50) {
    if (event === 'card_click') {
      tasks.push(redis(['HINCRBY', 'dwia:movie:click', movie, 1]));
    }
    if (event === 'video_play') {
      tasks.push(redis(['HINCRBY', 'dwia:movie:play', movie, 1]));
    }
  }

  // 검색어 카운트
  if (event === 'search' && query && typeof query === 'string' && query.length <= 30) {
    tasks.push(redis(['HINCRBY', 'dwia:search', query, 1]));
  }

  await Promise.all(tasks);

  return res.json({ ok: true });
}
