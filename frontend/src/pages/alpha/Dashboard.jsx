import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const API = process.env.REACT_APP_BACKEND_URL || '';
const f = (path) => fetch(`${API}${path}`).then(r => r.ok ? r.json() : null).catch(() => null);

// ─── Master Rules engine (mirrors backend exactly) ───────────────────────────
function runGates({ spread, volume, edge }) {
  return [
    { id: 'G1', label: 'KALSHI_ENV = paper',   pass: true,               val: 'paper' },
    { id: 'G2', label: 'Spread ≤ 4¢',          pass: spread <= 0.04,     val: `${(spread*100).toFixed(1)}¢` },
    { id: 'G3', label: 'Volume ≥ 5,000',        pass: volume >= 5000,     val: volume?.toLocaleString() },
    { id: 'G4', label: 'Daily loss < 10%',      pass: true,               val: 'OK' },
    { id: 'G5', label: 'No duplicate position', pass: true,               val: 'CLEAR' },
    { id: 'G6', label: 'Edge ≥ 5¢',            pass: Math.abs(edge)>=.05, val: `${(Math.abs(edge)*100).toFixed(1)}¢` },
  ];
}

const PHASES = [
  { id:0, label:'P0',  name:'Smoke Test',       color:'#10b981', status:'active'  },
  { id:1, label:'P1',  name:'Paper API',         color:'#0ea5e9', status:'locked'  },
  { id:2, label:'P2',  name:'Model A Spec',      color:'#7dd4ff', status:'locked'  },
  { id:3, label:'P3',  name:'Model C Momentum',  color:'#8b5cf6', status:'locked'  },
  { id:4, label:'P4',  name:'External Data',     color:'#f59e0b', status:'locked'  },
  { id:5, label:'P5',  name:'Pre-Game B/D/E',    color:'#ef4444', status:'locked'  },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [games,   setGames]   = useState([]);
  const [health,  setHealth]  = useState(null);
  const [sched,   setSched]   = useState(null);
  const [strat,   setStrat]   = useState(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef();

  const load = useCallback(async () => {
    const [g, h, sc, st] = await Promise.all([
      f('/api/games'),
      f('/api/health'),
      f('/api/autonomous/scheduler/status'),
      f('/api/strategies/summary'),
    ]);
    if (g) setGames(g.games || g || []);
    if (h) setHealth(h);
    if (sc) setSched(sc);
    if (st) setStrat(st);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    pollRef.current = setInterval(load, 5000);
    return () => clearInterval(pollRef.current);
  }, [load]);

  const allGames  = games;
  const live      = allGames.filter(g => (g.game?.status || g.status) === 'live');
  const upcoming  = allGames.filter(g => ['scheduled','pre_game'].includes(g.game?.status || g.status));
  const engineOn  = health?.autonomous_enabled ?? false;
  const dbOk      = health?.db_ping ?? false;
  const openMkts  = sched?.open_markets ?? sched?.scanning?.open_markets_found_last_min ?? 0;
  const totalPnl  = strat?.total_pnl ?? 0;
  const winRate   = strat?.win_rate ?? 0;
  const totalTrades = strat?.total_trades ?? 0;

  return (
    <div style={{ padding:'24px 28px', maxWidth:1440, margin:'0 auto' }} className="fade-up">

      {/* ── Header ── */}
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:24 }}>
        <div>
          <p className="label-pp" style={{ marginBottom:6 }}>LIVE DASHBOARD · alpha.predictpod.co</p>
          <h1 style={{ fontSize:28, fontWeight:800, color:'#e2eeff', margin:0, letterSpacing:'-.02em' }}>
            {loading ? 'Loading…' : live.length > 0 ? `${live.length} Game${live.length>1?'s':''} Live` : 'No Games Live'}
          </h1>
          <p style={{ fontSize:12, color:'var(--text3)', marginTop:4, fontFamily:"'JetBrains Mono',monospace" }}>
            {openMkts} Kalshi markets open · {allGames.length} games today · paper mode
          </p>
        </div>
        <button onClick={load} style={{ display:'flex', alignItems:'center', gap:6, padding:'8px 14px',
          background:'var(--card)', border:'1px solid var(--border)', borderRadius:7,
          color:'var(--text2)', fontSize:11, cursor:'pointer', fontFamily:'inherit' }}>
          ↻ Refresh
        </button>
      </div>

      {/* ── Phase strip ── */}
      <div style={{ marginBottom:24 }}>
        <p className="label-pp" style={{ marginBottom:8 }}>IMPLEMENTATION PHASES</p>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:8 }}>
          {PHASES.map(p => (
            <PhaseChip key={p.id} phase={p} onClick={() => navigate('/phases')} />
          ))}
        </div>
      </div>

      {/* ── Vitals strip ── */}
      <div className="stagger" style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:12, marginBottom:28 }}>
        <Vital label="ENGINE"      val={engineOn ? 'RUNNING' : 'STOPPED'} color={engineOn ? '#10b981' : '#ef4444'}
          sub="autonomous scheduler" glow={engineOn} />
        <Vital label="DATABASE"    val={dbOk ? 'CONNECTED' : 'OFFLINE'} color={dbOk ? '#10b981' : '#ef4444'}
          sub="MongoDB" />
        <Vital label="OPEN MARKETS" val={openMkts} color={openMkts > 0 ? '#0ea5e9' : 'var(--text3)'}
          sub="Kalshi basketball" />
        <Vital label="SESSION P&L"  val={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`}
          color={totalPnl > 0 ? '#10b981' : totalPnl < 0 ? '#ef4444' : 'var(--text3)'}
          sub={`${totalTrades} trades · ${winRate}% win`} />
        <Vital label="PAPER MODE"   val="ACTIVE" color="#f59e0b"
          sub="no live capital at risk" />
      </div>

      {/* ── Live games ── */}
      <Section label="LIVE GAMES" count={live.length}>
        {loading && <SkeletonGrid />}
        {!loading && live.length === 0 && (
          <Empty icon="◯" text="No games live right now" sub="Check back during NBA hours (7–11 PM ET)" />
        )}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(380px,1fr))', gap:14 }} className="stagger">
          {live.map(g => <GameCard key={g.game?.id||g.id} data={g} onClick={() => navigate(`/game/${g.game?.id||g.id}`)} live />)}
        </div>
      </Section>

      {/* ── Today's schedule ── */}
      <Section label="TODAY'S SCHEDULE" count={upcoming.length} style={{ marginTop:28 }}>
        {!loading && upcoming.length === 0 && (
          <Empty icon="◷" text="No upcoming games" sub="Schedule refreshes as Kalshi opens markets" />
        )}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(380px,1fr))', gap:14 }} className="stagger">
          {upcoming.map(g => <GameCard key={g.game?.id||g.id} data={g} onClick={() => navigate(`/game/${g.game?.id||g.id}`)} />)}
        </div>
      </Section>
    </div>
  );
}

// ─── Game Card ───────────────────────────────────────────────────────────────
function GameCard({ data, onClick, live }) {
  const game  = data.game  || data;
  const mkts  = data.markets || [];
  const sig   = data.signal;
  const mkt   = mkts[0];

  const home  = game.home_team?.name || game.home_team || 'Home';
  const away  = game.away_team?.name || game.away_team || 'Away';
  const hs    = game.home_score ?? 0;
  const as_   = game.away_score ?? 0;
  const margin= Math.abs(hs - as_);
  const prog  = game.game_progress ?? 0;
  const qtr   = game.quarter ?? 0;
  const clk   = game.time_remaining ?? '';

  const yesB  = mkt?.yes_bid  ?? 0;
  const yesA  = mkt?.yes_ask  ?? 0;
  const yesP  = mkt?.yes_price ?? mkt?.last_price ?? .5;
  const spread= yesA - yesB;
  const vol   = mkt?.volume ?? 0;
  const edge  = sig ? Math.abs(sig.edge ?? 0) : 0;
  const score = sig?.signal_score ?? 0;

  const gates = mkt ? runGates({ spread, volume: vol, edge }) : null;
  const gatesOk = gates ? gates.every(g => g.pass) : false;
  const signalType = sig?.signal_type || sig?.recommended_action || '';

  const [hov, setHov] = useState(false);

  return (
    <div className="card-pp fade-up" onClick={onClick}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ cursor:'pointer', padding:'16px 18px',
        borderColor: hov ? (live ? '#0ea5e9' : 'var(--border-lit)') : 'var(--border)',
        boxShadow: live && hov ? '0 0 20px rgba(14,165,233,.08)' : 'none' }}>

      {/* Live badge */}
      {live && (
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:10 }}>
          <span className="pill pill-green" style={{ animation:'pulse 2s infinite' }}>● LIVE</span>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, color:'var(--text3)' }}>
            Q{qtr} · {clk}
          </span>
        </div>
      )}

      {/* Teams + scores */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
        <div style={{ flex:1 }}>
          <TeamRow name={home} score={hs} leading={hs >= as_} home />
          <TeamRow name={away} score={as_} leading={as_ > hs} />
        </div>
        {!live && <span className="pill pill-dim">PRE-GAME</span>}
      </div>

      {/* Progress bar */}
      {live && (
        <div style={{ height:2, background:'var(--border)', borderRadius:2, marginBottom:12, overflow:'hidden' }}>
          <div style={{ height:'100%', width:`${prog*100}%`,
            background: margin > 22 ? 'var(--red)' : 'linear-gradient(90deg,#0ea5e9,#10b981)',
            borderRadius:2, transition:'width 1s ease' }} />
        </div>
      )}

      {/* Market row */}
      {mkt ? (
        <div style={{ display:'flex', gap:12, alignItems:'center', paddingTop:8, borderTop:'1px solid var(--border)' }}>
          <MktStat label="YES" val={`${(yesP*100).toFixed(0)}¢`} color="#0ea5e9" />
          <MktStat label="SPREAD" val={`${(spread*100).toFixed(1)}¢`} color={spread <= .04 ? '#10b981' : '#ef4444'} />
          <MktStat label="VOL" val={vol >= 1000 ? `${(vol/1000).toFixed(0)}K` : String(vol)} color={vol >= 5000 ? '#10b981' : '#ef4444'} />
          {score > 0 && <MktStat label="SCORE" val={String(score)} color={score >= 55 ? '#10b981' : '#f59e0b'} />}
          <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:5 }}>
            <div style={{ width:6, height:6, borderRadius:'50%', background: gatesOk ? '#10b981' : '#ef4444',
              boxShadow: gatesOk ? '0 0 5px #10b981' : 'none' }} />
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9,
              color: gatesOk ? '#065f46' : '#7f1d1d' }}>{gatesOk ? 'GATES OK' : 'GATES FAIL'}</span>
          </div>
        </div>
      ) : (
        <p style={{ fontSize:11, color:'var(--text4)', marginTop:8, fontFamily:"'JetBrains Mono',monospace" }}>
          Awaiting Kalshi market data…
        </p>
      )}

      {/* Signal */}
      {signalType && signalType !== 'WAIT' && (
        <div style={{ marginTop:8, padding:'5px 10px', borderRadius:5,
          background: signalType === 'STRONG_BUY' || signalType === 'BUY' ? 'rgba(16,185,129,.08)' : 'rgba(239,68,68,.08)',
          border: `1px solid ${signalType.includes('BUY') ? 'rgba(16,185,129,.2)' : 'rgba(239,68,68,.2)'}`,
          display:'flex', alignItems:'center', gap:8 }}>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:700,
            color: signalType.includes('BUY') ? '#10b981' : '#ef4444' }}>{signalType}</span>
          {edge > 0 && <span style={{ fontSize:10, color:'var(--text3)', fontFamily:"'JetBrains Mono',monospace" }}>edge={`${(edge*100).toFixed(1)}¢`}</span>}
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function TeamRow({ name, score, leading, home }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:4 }}>
      <div style={{ display:'flex', gap:8, alignItems:'center' }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:'var(--text4)', width:10 }}>
          {home ? 'H' : 'A'}
        </span>
        <span style={{ fontSize:13, fontWeight: leading ? 700 : 400, color: leading ? '#e2eeff' : 'var(--text3)' }}>{name}</span>
      </div>
      <span style={{ fontSize:16, fontWeight:800, fontFamily:"'JetBrains Mono',monospace",
        color: leading ? '#e2eeff' : 'var(--text4)' }}>{score}</span>
    </div>
  );
}

function MktStat({ label, val, color }) {
  return (
    <div>
      <p className="label-pp" style={{ marginBottom:2, fontSize:9 }}>{label}</p>
      <p style={{ margin:0, fontSize:13, fontWeight:700, color, fontFamily:"'JetBrains Mono',monospace" }}>{val}</p>
    </div>
  );
}

function Vital({ label, val, color, sub, glow }) {
  return (
    <div className="card-pp fade-up" style={{ padding:'14px 16px' }}>
      <p className="label-pp" style={{ marginBottom:8 }}>{label}</p>
      <p style={{ margin:0, fontSize:18, fontWeight:800, color, fontFamily:"'JetBrains Mono',monospace",
        textShadow: glow ? `0 0 10px ${color}` : 'none', marginBottom:4 }}>{val}</p>
      {sub && <p style={{ margin:0, fontSize:10, color:'var(--text4)', fontFamily:"'JetBrains Mono',monospace" }}>{sub}</p>}
    </div>
  );
}

function PhaseChip({ phase, onClick }) {
  const active = phase.status === 'active';
  return (
    <div onClick={onClick} style={{ padding:'10px 12px', borderRadius:8, cursor:'pointer',
      background: active ? `${phase.color}10` : 'var(--card)',
      border: `1px solid ${active ? phase.color + '44' : 'var(--border)'}`,
      position:'relative', overflow:'hidden', transition:'all .15s' }}>
      {active && (
        <div style={{ position:'absolute', top:0, left:0, right:0, height:2,
          background:`linear-gradient(90deg,transparent,${phase.color},transparent)`,
          animation:'pulse 2s infinite' }} />
      )}
      <p className="label-pp" style={{ marginBottom:3, fontSize:9, color: active ? phase.color : 'var(--text4)' }}>
        {phase.label} {active ? '● ACTIVE' : '○ LOCKED'}
      </p>
      <p style={{ margin:0, fontSize:11, fontWeight:600, color: active ? '#e2eeff' : 'var(--text4)',
        fontFamily:"'JetBrains Mono',monospace" }}>{phase.name}</p>
    </div>
  );
}

function Section({ label, count, children, style }) {
  return (
    <div style={style}>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
        <p className="label-pp" style={{ margin:0 }}>{label}</p>
        {count > 0 && <span className="pill pill-dim">{count}</span>}
      </div>
      {children}
    </div>
  );
}

function Empty({ icon, text, sub }) {
  return (
    <div style={{ padding:'40px 0', textAlign:'center' }}>
      <div style={{ fontSize:32, color:'var(--text4)', marginBottom:8 }}>{icon}</div>
      <p style={{ margin:0, fontSize:13, color:'var(--text3)' }}>{text}</p>
      {sub && <p style={{ margin:'4px 0 0', fontSize:11, color:'var(--text4)' }}>{sub}</p>}
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(380px,1fr))', gap:14, marginBottom:14 }}>
      {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height:130 }} />)}
    </div>
  );
}
