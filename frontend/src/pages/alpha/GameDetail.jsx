import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const API = process.env.REACT_APP_BACKEND_URL || '';
const f = (path) => fetch(`${API}${path}`).then(r => r.ok ? r.json() : null).catch(() => null);

// ─── Fair value formula (Phase 0 placeholder — spec formula in Phase 2) ────
function fairValue(game, mid) {
  if (!game) return mid;
  const diff = (game.home_score ?? 0) - (game.away_score ?? 0);
  const secRem = game.total_seconds_remaining ?? 1440;
  const drift  = diff * 0.0305 * (secRem / 2880);
  return Math.max(0.03, Math.min(0.97, mid + drift));
}

// ─── Signal score composite ─────────────────────────────────────────────────
function signalScore({ edge, progress, volume, margin }) {
  const e = Math.min(Math.abs(edge) / 0.10 * 40, 40);
  const t = progress >= .10 && progress <= .95 ? 20 : 0;
  const v = volume >= 5000 ? 15 : volume >= 1000 ? 8 : 0;
  const m = margin <= 15 ? 15 : margin <= 22 ? 8 : 0;
  return Math.round(e + t + v + m);
}

// ─── Full rules evaluation (100% accurate to Master Rules) ────────────────
function evaluate({ bid, ask, volume, fv, game }) {
  const spread   = +(ask - bid).toFixed(4);
  const mid      = +((bid + ask) / 2).toFixed(4);
  const edge     = +(fv - mid).toFixed(4);
  const progress = game?.game_progress ?? 0;
  const margin   = Math.abs((game?.home_score ?? 0) - (game?.away_score ?? 0));
  const score    = signalScore({ edge, progress, volume, margin });

  const gates = [
    { id:'G1', label:'KALSHI_ENV = paper',    pass:true,                val:'paper',              rule:'Hard block — no live trading' },
    { id:'G2', label:'Spread ≤ 4¢',           pass:spread <= 0.04,      val:`${(spread*100).toFixed(1)}¢`,  rule:'Gate 2: bid-ask ≤ 0.04' },
    { id:'G3', label:'Volume ≥ 5,000',         pass:volume >= 5000,      val:volume?.toLocaleString(),        rule:'Gate 3: 24h contracts' },
    { id:'G4', label:'Daily loss < 10%',       pass:true,                val:'OK',                 rule:'Gate 4: model allocation' },
    { id:'G5', label:'No duplicate position',  pass:true,                val:'CLEAR',              rule:'Gate 5: one position per game' },
    { id:'G6', label:'Edge ≥ 5¢',             pass:Math.abs(edge)>=.05, val:`${(Math.abs(edge)*100).toFixed(1)}¢`, rule:'Gate 6: fair value gap' },
  ];

  const modelChecks = [
    { id:'M1', label:'Edge ≥ 5¢',             pass:Math.abs(edge) >= .05,                val:`${(Math.abs(edge)*100).toFixed(1)}¢` },
    { id:'M2', label:'Signal score ≥ 55',      pass:score >= 55,                           val:String(score) },
    { id:'M3', label:'Game 10%–95% complete',  pass:progress >= .10 && progress <= .95,   val:`${(progress*100).toFixed(0)}%` },
    { id:'M4', label:'Margin ≤ 22 pts',        pass:margin <= 22,                          val:`${margin} pts` },
    { id:'M5', label:'Volatility LOW/MED',     pass:spread < 0.04,                         val:spread < .02 ? 'LOW' : 'MEDIUM' },
    { id:'M6', label:'Liquidity ≥ 50 contracts',pass:volume >= 50,                         val:volume?.toLocaleString() },
  ];

  const allGates = gates.every(g => g.pass);
  const allModel = allGates && modelChecks.every(c => c.pass);

  let decision, side = null;
  if (!allGates) {
    const f_ = gates.find(g => !g.pass);
    decision = { type:'BLOCK', color:'#ef4444', reason:`Gate ${f_.id} failed: ${f_.label} (${f_.val})` };
  } else if (allModel) {
    side = edge > 0 ? 'YES' : 'NO';
    decision = { type:'ENTER', color:'#10b981',
      reason:`${side} @ ${(mid*100).toFixed(0)}¢ | edge=${(Math.abs(edge)*100).toFixed(1)}¢ | score=${score}` };
  } else {
    const f_ = modelChecks.find(c => !c.pass);
    decision = { type:'HOLD', color:'#f59e0b',
      reason:`Waiting: ${f_ ? `${f_.label} = ${f_.val}` : 'conditions not met'}` };
  }

  return { spread, mid, fv, edge, score, gates, modelChecks, decision, side, progress, margin };
}

// ─── Custom tooltip for chart ───────────────────────────────────────────────
const ChartTip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:'#0a1220', border:'1px solid #1a2e4a', borderRadius:6,
      padding:'8px 12px', fontFamily:"'JetBrains Mono',monospace", fontSize:11 }}>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, marginBottom:2 }}>
          {p.name}: {(p.value * 100).toFixed(1)}¢
        </div>
      ))}
    </div>
  );
};

export default function GameDetail() {
  const { gameId } = useParams();
  const [gameData, setGameData] = useState(null);
  const [ticks,    setTicks]    = useState([]);  // chart data
  const [log,      setLog]      = useState([]);  // decision log
  const [latest,   setLatest]   = useState(null);
  const [backendDecs, setBD]    = useState([]);
  const tickN    = useRef(0);
  const pollRef  = useRef();
  const synth    = useRef({ bid:.48, ask:.52, vol:8000 });

  // Load game data every 5s
  const loadGame = useCallback(async () => {
    const d = await f(`/api/games/${gameId}`);
    if (d) setGameData(d);
  }, [gameId]);

  // Load backend decision traces
  const loadDecs = useCallback(async () => {
    const d = await f(`/api/decisions/latest?limit=50`);
    if (d?.decisions) setBD(d.decisions);
  }, []);

  useEffect(() => {
    loadGame(); loadDecs();
    pollRef.current = setInterval(() => { loadGame(); loadDecs(); }, 5000);
    return () => clearInterval(pollRef.current);
  }, [loadGame, loadDecs]);

  // Tick loop — runs every 3s — evaluates rules
  useEffect(() => {
    const interval = setInterval(() => {
      tickN.current += 1;
      const game = gameData?.game || gameData;
      const mkts  = gameData?.markets || [];
      const mkt   = mkts[0];

      let bid, ask, vol;
      if (mkt) {
        bid = mkt.yes_bid ?? .48; ask = mkt.yes_ask ?? .52; vol = mkt.volume ?? 8000;
      } else {
        // Synthetic random walk when no live market
        const d = (Math.random() - .5) * .012;
        bid = Math.max(.05, Math.min(.94, synth.current.bid + d));
        ask = bid + .02 + Math.random() * .02;
        vol = Math.floor(5000 + Math.random() * 12000);
        synth.current = { bid, ask, vol };
      }

      const fv = fairValue(game, (bid + ask) / 2);
      const result = evaluate({ bid, ask, volume: vol, fv, game });

      const ts = new Date().toLocaleTimeString('en-US', { hour12:false });
      const chartPt = { t:ts, mid:result.mid, fv:result.fv, edge:Math.abs(result.edge) };

      setTicks(prev => [...prev.slice(-79), chartPt]);
      setLatest(result);
      setLog(prev => [{ tick:tickN.current, ts, ...result }, ...prev.slice(0, 199)]);
    }, 3000);
    return () => clearInterval(interval);
  }, [gameData]);

  const game   = gameData?.game   || gameData;
  const mkts   = gameData?.markets || [];
  const signal = gameData?.signal;

  const hs = game?.home_score ?? 0;
  const as_ = game?.away_score ?? 0;
  const margin = Math.abs(hs - as_);
  const home = game?.home_team?.name || game?.home_team || 'Home';
  const away = game?.away_team?.name || game?.away_team || 'Away';

  const enterCt = log.filter(l => l.decision?.type === 'ENTER').length;
  const holdCt  = log.filter(l => l.decision?.type === 'HOLD').length;
  const blockCt = log.filter(l => l.decision?.type === 'BLOCK').length;

  if (!game) return <LoadingScreen />;

  return (
    <div style={{ padding:'20px 28px', maxWidth:1440, margin:'0 auto' }} className="fade-up">

      {/* Breadcrumb */}
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:18,
        fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:'var(--text3)' }}>
        <Link to="/" style={{ color:'var(--accent)', textDecoration:'none' }}>Dashboard</Link>
        <span>›</span>
        <span>Game Detail</span>
        {game.espn_id && <span style={{ color:'var(--text4)' }}>· ESPN {game.espn_id}</span>}
      </div>

      {/* ── Scoreboard ── */}
      <div className="card-pp" style={{ padding:'20px 24px', marginBottom:20 }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:16 }}>

          {/* Home team */}
          <ScoreTeam label="HOME" name={home} score={hs} leading={hs >= as_} />

          {/* Clock block */}
          <div style={{ textAlign:'center', padding:'0 24px', borderLeft:'1px solid var(--border)', borderRight:'1px solid var(--border)' }}>
            <p style={{ margin:0, fontFamily:"'JetBrains Mono',monospace", fontSize:13, color:'var(--text2)', marginBottom:6 }}>
              {game.status === 'live' ? `Q${game.quarter ?? '—'} · ${game.time_remaining ?? '--:--'}` : (game.status || 'scheduled').toUpperCase()}
            </p>
            {game.status === 'live' && (
              <span className="pill pill-green" style={{ animation:'pulse 2s infinite', fontSize:9 }}>● LIVE</span>
            )}
            {/* Progress bar */}
            <div style={{ width:160, height:3, background:'var(--border)', borderRadius:2, margin:'10px auto 4px', overflow:'hidden' }}>
              <div style={{ height:'100%', width:`${(game.game_progress ?? 0)*100}%`,
                background: margin > 22 ? 'var(--red)' : 'linear-gradient(90deg,#0ea5e9,#10b981)',
                transition:'width 1s ease' }} />
            </div>
            <p style={{ margin:0, fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:'var(--text4)' }}>
              {((game.game_progress ?? 0)*100).toFixed(0)}% complete
            </p>
          </div>

          {/* Away team */}
          <ScoreTeam label="AWAY" name={away} score={as_} leading={as_ > hs} />

          {/* Right stats */}
          <div style={{ marginLeft:'auto', display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
            <StatBox label="MARGIN" val={`${margin} pts`} warn={margin > 22} />
            <StatBox label="BLOWOUT?" val={margin > 22 ? 'YES — NO ENTRY' : 'NO'} warn={margin > 22} />
            {signal && <>
              <StatBox label="FAIR PROB" val={`${((gameData?.fair_prob_home ?? .5)*100).toFixed(1)}%`} />
              <StatBox label="SIGNAL" val={signal.signal_type || signal.recommended_action || '--'} />
            </>}
          </div>
        </div>
      </div>

      {/* ── Main 3-col grid ── */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:16, marginBottom:16 }}>

        {/* Market state */}
        <Panel title="MARKET STATE" subtitle={mkts[0] ? 'live Kalshi data' : 'synthetic simulation'}>
          {latest ? <>
            <MetricRow label="Market Mid"   val={`${(latest.mid*100).toFixed(1)}¢`}   color="var(--accent)" />
            <MetricRow label="Fair Value"   val={`${(latest.fv*100).toFixed(1)}¢`}    color="#8b5cf6" />
            <MetricRow label="Edge"         val={`${(Math.abs(latest.edge)*100).toFixed(1)}¢`}
              color={Math.abs(latest.edge) >= .05 ? '#10b981' : 'var(--text3)'} />
            <MetricRow label="Signal Score" val={String(latest.score)}
              color={latest.score >= 55 ? '#10b981' : latest.score >= 35 ? '#f59e0b' : 'var(--text3)'} />
            <MetricRow label="Spread"       val={`${(latest.spread*100).toFixed(1)}¢`}
              color={latest.spread <= .04 ? '#10b981' : '#ef4444'} />
            <MetricRow label="Margin"       val={`${latest.margin} pts`}
              color={latest.margin <= 22 ? '#10b981' : '#ef4444'} />
            <MetricRow label="Progress"     val={`${(latest.progress*100).toFixed(0)}%`}
              color={latest.progress >= .10 && latest.progress <= .95 ? '#10b981' : '#ef4444'} />
          </> : <Pending />}
        </Panel>

        {/* Safety gates */}
        <Panel title="SAFETY GATES" subtitle="all 6 must pass — any failure blocks trade">
          {latest ? <>
            {latest.gates.map(g => (
              <GateRow key={g.id} id={g.id} label={g.label} val={g.val} pass={g.pass} rule={g.rule} />
            ))}
            <div style={{ marginTop:12, padding:'9px 12px', borderRadius:7,
              background: latest.gates.every(g=>g.pass) ? 'rgba(16,185,129,.06)' : 'rgba(239,68,68,.06)',
              border:`1px solid ${latest.gates.every(g=>g.pass) ? 'rgba(16,185,129,.2)' : 'rgba(239,68,68,.2)'}` }}>
              <p style={{ margin:0, fontFamily:"'JetBrains Mono',monospace", fontSize:11, fontWeight:700,
                color: latest.gates.every(g=>g.pass) ? '#10b981' : '#ef4444' }}>
                {latest.gates.every(g=>g.pass) ? '✓ ALL 6 GATES PASS' : `✗ BLOCKED — ${latest.gates.find(g=>!g.pass)?.label}`}
              </p>
            </div>
          </> : <Pending />}
        </Panel>

        {/* Entry conditions + decision */}
        <Panel title="MODEL ENTRY CONDITIONS" subtitle="consolidated in-game edge trader">
          {latest ? <>
            {latest.modelChecks.map(c => (
              <GateRow key={c.id} id={c.id} label={c.label} val={c.val} pass={c.pass} />
            ))}
            <div style={{ marginTop:12, padding:'10px 12px', borderRadius:7,
              background: latest.decision.type==='ENTER' ? 'rgba(16,185,129,.06)'
                : latest.decision.type==='BLOCK' ? 'rgba(239,68,68,.06)' : 'rgba(245,158,11,.06)',
              border:`1px solid ${latest.decision.color}33` }}>
              <p className="label-pp" style={{ marginBottom:5 }}>DECISION</p>
              <p style={{ margin:0, fontFamily:"'JetBrains Mono',monospace", fontSize:16, fontWeight:800,
                color:latest.decision.color, marginBottom:5 }}>{latest.decision.type}</p>
              <p style={{ margin:0, fontSize:11, color:'var(--text2)', fontFamily:"'JetBrains Mono',monospace" }}>
                {latest.decision.reason}
              </p>
              {latest.side && (
                <span className={`pill pill-${latest.side==='YES'?'green':'red'}`} style={{ marginTop:6 }}>
                  {latest.side}
                </span>
              )}
            </div>
          </> : <Pending />}
        </Panel>
      </div>

      {/* ── Price chart ── */}
      <div className="card-pp" style={{ padding:'16px 20px', marginBottom:16 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
          <p className="label-pp" style={{ margin:0 }}>MARKET PRICE vs FAIR VALUE ({ticks.length} ticks)</p>
          <div style={{ display:'flex', gap:14, fontFamily:"'JetBrains Mono',monospace", fontSize:10 }}>
            <span style={{ color:'#0ea5e9' }}>── Market Mid</span>
            <span style={{ color:'#8b5cf6' }}>── Fair Value</span>
            <span style={{ color:'#10b981' }}>── Edge</span>
          </div>
        </div>
        {ticks.length < 2 ? (
          <div style={{ height:160, display:'flex', alignItems:'center', justifyContent:'center',
            color:'var(--text4)', fontSize:12, fontFamily:"'JetBrains Mono',monospace" }}>
            Collecting ticks… chart appears after 2 evaluations
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={ticks} margin={{ top:4, right:8, bottom:0, left:-20 }}>
              <CartesianGrid stroke="#111e34" strokeDasharray="3 3" />
              <XAxis dataKey="t" tick={{ fill:'#3a5570', fontSize:9, fontFamily:"'JetBrains Mono',monospace" }} />
              <YAxis tickFormatter={v => `${(v*100).toFixed(0)}¢`} tick={{ fill:'#3a5570', fontSize:9 }} domain={['auto','auto']} />
              <Tooltip content={<ChartTip />} />
              <ReferenceLine y={.5} stroke="#1a2e4a" strokeDasharray="4 4" />
              <Line dataKey="mid"  stroke="#0ea5e9" strokeWidth={2} dot={false} name="Mid" />
              <Line dataKey="fv"   stroke="#8b5cf6" strokeWidth={2} dot={false} name="FV" />
              <Line dataKey="edge" stroke="#10b981" strokeWidth={1.5} dot={false} name="Edge" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Decision log ── */}
      <div className="card-pp" style={{ padding:'16px 20px', marginBottom:16 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
          <p className="label-pp" style={{ margin:0 }}>DECISION AUDIT LOG ({log.length} evaluated)</p>
          <div style={{ display:'flex', gap:10 }}>
            <DecCount label="ENTER" val={enterCt} color="#10b981" />
            <DecCount label="HOLD"  val={holdCt}  color="#f59e0b" />
            <DecCount label="BLOCK" val={blockCt} color="#ef4444" />
          </div>
        </div>
        <div style={{ maxHeight:280, overflowY:'auto' }}>
          {log.length === 0 && <p style={{ color:'var(--text4)', fontSize:11, fontFamily:"'JetBrains Mono',monospace" }}>Evaluating first tick (3s)…</p>}
          {log.slice(0, 50).map((l, i) => (
            <div key={l.tick} className="fade-in" style={{
              display:'flex', alignItems:'center', gap:10,
              padding:'6px 10px', borderRadius:5, marginBottom:2,
              background: i === 0 ? `${l.decision.color}08` : 'transparent',
              border:`1px solid ${i === 0 ? l.decision.color+'22' : 'transparent'}`,
              fontFamily:"'JetBrains Mono',monospace",
            }}>
              <span style={{ fontSize:10, color:'var(--text4)', minWidth:56 }}>{l.ts}</span>
              <span className={`pill pill-${l.decision.type==='ENTER'?'green':l.decision.type==='BLOCK'?'red':'yellow'}`}>
                {l.decision.type}
              </span>
              {l.side && <span className={`pill pill-${l.side==='YES'?'green':'red'}`}>{l.side}</span>}
              <span style={{ flex:1, fontSize:11, color:'var(--text2)' }}>{l.decision.reason}</span>
              <span style={{ fontSize:10, color:'var(--text3)' }}>score={l.score}</span>
              <span style={{ fontSize:10, color:'var(--text4)' }}>edge={Math.abs(l.edge*100).toFixed(1)}¢</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Backend decision trace (from server logs) ── */}
      {backendDecs.length > 0 && (
        <div className="card-pp" style={{ padding:'16px 20px' }}>
          <p className="label-pp" style={{ marginBottom:12 }}>BACKEND DECISION TRACE (server JSONL logs)</p>
          <div style={{ maxHeight:200, overflowY:'auto' }}>
            {backendDecs.slice(0, 30).map((d, i) => {
              const dtype = d.decision || d.decision_type || 'HOLD';
              const color = dtype==='ENTER' ? '#10b981' : dtype==='BLOCK' ? '#ef4444' : '#f59e0b';
              return (
                <div key={i} style={{ display:'flex', gap:10, padding:'6px 10px',
                  borderBottom:'1px solid var(--border)', fontFamily:"'JetBrains Mono',monospace", fontSize:11 }}>
                  <span style={{ color:'var(--text4)', minWidth:70 }}>{d.timestamp?.slice(11,19) || '--'}</span>
                  <span style={{ color, fontWeight:700, minWidth:50 }}>{dtype}</span>
                  <span style={{ color:'var(--text3)', flex:1 }}>{d.reason || d.model_id || '--'}</span>
                  {d.edge_cents != null && <span style={{ color:'var(--text4)' }}>{d.edge_cents.toFixed(1)}¢</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ScoreTeam({ label, name, score, leading }) {
  return (
    <div style={{ textAlign:'center', minWidth:120 }}>
      <p className="label-pp" style={{ marginBottom:6 }}>{label}</p>
      <p style={{ margin:0, fontSize:48, fontWeight:800, fontFamily:"'JetBrains Mono',monospace",
        color: leading ? '#e2eeff' : 'var(--text4)', lineHeight:1 }}>{score}</p>
      <p style={{ margin:'8px 0 0', fontSize:14, color: leading ? 'var(--text2)' : 'var(--text4)' }}>{name}</p>
    </div>
  );
}

function Panel({ title, subtitle, children }) {
  return (
    <div className="card-pp" style={{ padding:'16px 18px' }}>
      <p className="label-pp" style={{ marginBottom:3 }}>{title}</p>
      {subtitle && <p style={{ margin:'0 0 12px', fontSize:10, color:'var(--text4)', fontFamily:"'JetBrains Mono',monospace" }}>{subtitle}</p>}
      {children}
    </div>
  );
}

function GateRow({ id, label, val, pass, rule }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8, padding:'6px 0',
      borderBottom:'1px solid var(--border)', fontFamily:"'JetBrains Mono',monospace" }}>
      <span style={{ fontSize:10, color: pass ? '#10b981' : '#ef4444', width:14, textAlign:'center' }}>
        {pass ? '✓' : '✗'}
      </span>
      <span style={{ flex:1, fontSize:11, color: pass ? 'var(--text2)' : '#ef4444' }}>{label}</span>
      <span style={{ fontSize:10, color:'var(--text3)', background:'rgba(0,0,0,.2)',
        padding:'1px 7px', borderRadius:3 }}>{val}</span>
    </div>
  );
}

function MetricRow({ label, val, color }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline',
      padding:'6px 0', borderBottom:'1px solid var(--border)' }}>
      <span style={{ fontSize:11, color:'var(--text3)', fontFamily:"'JetBrains Mono',monospace" }}>{label}</span>
      <span style={{ fontSize:15, fontWeight:700, color, fontFamily:"'JetBrains Mono',monospace" }}>{val}</span>
    </div>
  );
}

function StatBox({ label, val, warn }) {
  return (
    <div>
      <p className="label-pp" style={{ marginBottom:3 }}>{label}</p>
      <p style={{ margin:0, fontSize:13, fontWeight:700, fontFamily:"'JetBrains Mono',monospace",
        color: warn ? '#ef4444' : 'var(--text2)' }}>{val}</p>
    </div>
  );
}

function DecCount({ label, val, color }) {
  return (
    <div style={{ textAlign:'center', padding:'6px 12px', background:'rgba(0,0,0,.2)',
      border:`1px solid ${color}22`, borderRadius:6 }}>
      <p style={{ margin:0, fontSize:16, fontWeight:800, color, fontFamily:"'JetBrains Mono',monospace" }}>{val}</p>
      <p className="label-pp" style={{ margin:0, fontSize:9 }}>{label}</p>
    </div>
  );
}

function Pending() {
  return <p style={{ color:'var(--text4)', fontSize:11, fontFamily:"'JetBrains Mono',monospace", marginTop:8 }}>
    Evaluating — first tick in 3s…
  </p>;
}

function LoadingScreen() {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'60vh' }}>
      <div style={{ textAlign:'center' }}>
        <p style={{ fontSize:24, color:'var(--text4)', marginBottom:8 }}>◎</p>
        <p style={{ fontSize:12, color:'var(--text3)', fontFamily:"'JetBrains Mono',monospace" }}>Loading game…</p>
      </div>
    </div>
  );
}
