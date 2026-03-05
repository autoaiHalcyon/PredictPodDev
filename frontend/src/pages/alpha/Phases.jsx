import React, { useState, useEffect } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const f = (path) => fetch(`${API}${path}`).then(r => r.ok ? r.json() : null).catch(() => null);

const PHASES = [
  {
    id: 0, color: '#10b981', status: 'active',
    name: 'Phase 0 — Smoke Test',
    tagline: 'Real signals evaluated on real NBA games',
    models: ['Consolidated In-Game Edge Trader'],
    overview: 'Before placing a single paper order, the engine must prove it can discover live Kalshi markets, pull real ESPN scores, compute fair values, run the 6 safety gates, and fire ENTER decisions with a full audit trail.',
    exitCriteria: [
      '≥ 10 signal evaluations logged per quarter on a live NBA game',
      '≥ 1 ENTER decision fires with correct gate evaluation',
      '/api/debug/signals returns live market + score data',
      'Zero Python exceptions during a full 4-quarter game',
    ],
    gates: [
      { id:'G1', desc:'KALSHI_ENV = paper', note:'Hard block — system refuses any order if missing' },
      { id:'G2', desc:'Spread ≤ 4¢',        note:'Gate 2 from Master Rules' },
      { id:'G3', desc:'Volume ≥ 5,000',      note:'24h contract minimum for liquidity' },
      { id:'G4', desc:'Daily loss < 10%',    note:'Per-model allocation gate' },
      { id:'G5', desc:'No duplicate position',note:'One position per game per model' },
      { id:'G6', desc:'Edge ≥ 5¢',           note:'Fair value must exceed market by ≥ 5¢' },
    ],
    data: ['ESPN live scoreboard (score, quarter, clock)', 'Kalshi market data (mock adapter OK)'],
    files: ['autonomous_scheduler.py — discovery + trading loops (bugs #1/#2 fixed)', 'model_ingame_edge.py — consolidated model', 'risk_engine.py — all 6 gates enforced'],
  },
  {
    id: 1, color: '#0ea5e9', status: 'locked',
    name: 'Phase 1 — Kalshi Paper API',
    tagline: 'Real paper orders signed and confirmed in Kalshi dashboard',
    models: ['Consolidated In-Game Edge Trader'],
    overview: 'Switch from MockKalshiAdapter to the real Kalshi demo (paper) environment. Every order is signed with RSA-PSS. The order must appear in the Kalshi dashboard and fill must be confirmed via API response before any position is tracked.',
    exitCriteria: [
      'Paper order appears in Kalshi demo dashboard within 30s',
      'All 6 safety gates log the correct reason when violated',
      'MockKalshiAdapter fully removed from production startup path',
      'Balance, positions, and fills read from real Kalshi API responses',
    ],
    gates: [
      { id:'G1', desc:'KALSHI_ENV = paper', note:'Verified in .env before startup' },
      { id:'RSA', desc:'RSA-PSS auth signing', note:'real_adapter.py — current version uses basic Bearer' },
    ],
    data: ['Kalshi paper API (demo-api.kalshi.co)', 'ESPN live scores'],
    files: ['real_adapter.py — complete RSA-PSS signing', 'server.py — switch to RealKalshiAdapter(demo=True)', 'risk_engine.py — verify all gates enforced before first paper order'],
  },
  {
    id: 2, color: '#7dd4ff', status: 'locked',
    name: 'Phase 2 — Model A Spec Fair Value',
    tagline: 'Replace placeholder probability engine with the Master Rules formula',
    models: ['Model A — In-Game Price Drift'],
    overview: 'The consolidated model uses a generic ProbabilityEngine. This phase replaces it with the exact spec formula. ratingDiff is set to 0 until Phase 4 SportsDataIO connection.',
    formula: 'fair_value = (scoreDiff × 0.0305) + (homeCourtAdv × 0.032) + (ratingDiff × 0.018)',
    exitCriteria: [
      'fair_value_engine.py unit tests pass for known score/time inputs',
      'Model A fires with spec-correct conditions (edge ≥ 7¢, margin ≤ 22)',
      'Blowout filter blocks entries when margin > 22 pts',
      '20+ paper trades placed and logged using real formula',
    ],
    modelRules: {
      entry:  'Edge ≥ 7¢, signal score ≥ 60, 3-tick persistence, 180s cooldown, max 3/game, momentum required',
      exit:   'Stop loss −10%, profit target +15%, edge compression < 2¢, time exit 600s, blowout exit margin > 28',
      sizing: '$5.00 max per trade (2.5% of $200 allocation), half-Kelly based on edge',
      limits: '20 trades/day, 4 trades/hour',
    },
    data: ['ESPN live scores', 'SportsDataIO team ratings — ratingDiff = 0 until Phase 4'],
    files: ['fair_value_engine.py — spec formula complete', 'model_a_ingame.py — new file replacing consolidated', 'configs/model_a.json — edge ≥ 7¢, $5 max, blowout ≤ 22'],
  },
  {
    id: 3, color: '#8b5cf6', status: 'locked',
    name: 'Phase 3 — Model C Momentum Fade',
    tagline: 'Detect 10-point runs and fade the crowd overreaction',
    models: ['Model A — In-Game Price Drift', 'Model C — Momentum Fade'],
    overview: 'Model C is event-triggered, not continuous. When one team goes on a 10+ point run in 5 minutes AND the Kalshi market moved ≥ 10¢ during that run, Model C fades the overreaction. It can coexist with Model A on the same game — they use different signals.',
    exitCriteria: [
      'Run detector correctly identifies ≥ 10pt runs in rolling 5-min score window',
      'Model C fires independently of Model A on same game',
      '10+ Model C paper trades placed and logged',
    ],
    modelRules: {
      entry:  '≥ 10pt run in 5 min, market moved ≥ 10¢, margin ≤ 18 pts, timing 4–30 min remaining, max 2/game',
      exit:   'Stop loss −40%, profit target +30%, time exit 10 min, run extends 6+ pts (thesis wrong)',
      sizing: '$3.00 flat, boosted to $4.00 if run ≥ 14pts AND market move ≥ 14¢',
      limits: '10 trades/day, 2 trades/hour',
    },
    data: ['ESPN live scores + rolling 5-min score per team'],
    files: ['model_c_momentum.py — new file', 'configs/model_c.json — $3 flat, stop −40%', 'strategy_manager.py — add Model C alongside A'],
  },
  {
    id: 4, color: '#f59e0b', status: 'locked',
    name: 'Phase 4 — External Data Sources',
    tagline: 'The Odds API sharp lines + SportsDataIO team ratings',
    models: ['Model A (full formula with ratingDiff)', 'Model C'],
    overview: 'The three pre-game models cannot run without sharp closing lines and team net ratings. This phase connects both external APIs, updates Model A\'s formula with real ratingDiff, and validates against known past game values.',
    exitCriteria: [
      'Sharp closing lines fetched and stored for all active NBA games',
      'Team net ratings available for all NBA teams',
      'Model A fair value using real ratingDiff values (not 0)',
      'Verified against known historical outcomes',
    ],
    data: [
      'The Odds API — sharp closing lines (poll every 5 min pre-game, cache 10 min max)',
      'SportsDataIO — team net ratings (weekly refresh, use stale if fetch fails with flag)',
    ],
    files: ['odds_api_adapter.py — new file', 'sportsdata_adapter.py — new file', 'models/game.py — add sharp_line + team_rating_diff fields'],
  },
  {
    id: 5, color: '#ef4444', status: 'locked',
    name: 'Phase 5 — Pre-Game Models B, D, E + Conflict Resolver',
    tagline: 'Full 5-model system — pre-game and in-game trading simultaneously',
    models: ['Model A', 'Model B — Pre-Game CLV', 'Model C', 'Model D — Late Convergence', 'Model E — Strong Favorite'],
    overview: 'The three pre-game models trade the gap between Kalshi prices and sharp lines before tip-off. They require the conflict resolver to prevent overlapping positions. All pre-game positions close at settlement — never held into the game.',
    exitCriteria: [
      'All 3 pre-game models place paper trades with correct conflict checking',
      'Conflict resolver blocks all 3 overlap scenarios (B≠D, B≠E, D≠E same game)',
      'CLV delta tracked on every Model B trade (entry_price − closing_line)',
      '20+ paper trades per model with full audit logs',
    ],
    conflictRules: [
      { model:'Model B', blocked:'if D or E already open on same game' },
      { model:'Model D', blocked:'if B already open on same game' },
      { model:'Model E', blocked:'if B or D already open on same game' },
      { model:'Model A', blocked:'never blocked — in-game, always independent' },
      { model:'Model C', blocked:'never blocked — in-game, always independent' },
    ],
    data: ['All Phase 4 data +', 'Kalshi 15-min price history (Model D velocity)', 'CLV closing line at tip-off'],
    files: ['model_b_clv.py', 'model_d_convergence.py', 'model_e_favorite.py', 'conflict_resolver.py', 'strategy_manager.py — full 5-model system'],
    graduation: true,
  },
];

const GRADUATION = [
  { label:'≥ 100 settled trades per model',          detail:'minimum sample for statistical validity' },
  { label:'Win rate > 52%',                           detail:'across all 100+ trades per model' },
  { label:'Brier score < 0.23',                       detail:'probability calibration quality' },
  { label:'CLV delta < −0.02 (avg)',                  detail:'Models B and D: consistently beating closing line' },
  { label:'Max drawdown < 15%',                       detail:'over any 100-trade rolling window' },
  { label:'No active circuit breaker',                detail:'at time of graduation evaluation' },
  { label:'All 5 models pass simultaneously',         detail:'no partial graduation — system goes live as a unit' },
];

export default function Phases() {
  const [health, setHealth] = useState(null);
  const [sched,  setSched]  = useState(null);
  const [strat,  setStrat]  = useState(null);
  const [expanded, setExpanded] = useState(new Set([0]));

  useEffect(() => {
    const load = async () => {
      const [h, sc, st] = await Promise.all([
        f('/api/health'),
        f('/api/autonomous/scheduler/status'),
        f('/api/strategies/summary'),
      ]);
      if (h)  setHealth(h);
      if (sc) setSched(sc);
      if (st) setStrat(st);
    };
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const toggle = (id) => setExpanded(prev => {
    const n = new Set(prev);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  const engineOn  = health?.autonomous_enabled ?? false;
  const ticks     = health?.strategy_loop_ticks_total ?? 0;
  const trades    = strat?.total_trades ?? 0;
  const openMkts  = sched?.open_markets ?? 0;

  return (
    <div style={{ padding:'24px 28px', maxWidth:1100, margin:'0 auto' }} className="fade-up">

      {/* Header */}
      <p className="label-pp" style={{ marginBottom:6 }}>IMPLEMENTATION ROADMAP</p>
      <h1 style={{ fontSize:28, fontWeight:800, color:'#e2eeff', margin:'0 0 8px', letterSpacing:'-.02em' }}>
        6-Phase Build Plan
      </h1>
      <p style={{ fontSize:12, color:'var(--text3)', margin:'0 0 24px', fontFamily:"'JetBrains Mono',monospace" }}>
        Each phase is gated — all exit criteria must be met before the next phase unlocks.
        Partial completion does not count.
      </p>

      {/* Live counters */}
      <div className="stagger" style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:28 }}>
        {[
          { l:'Current Phase',   v:'0 — Smoke Test',                   c:'#10b981' },
          { l:'Engine Status',   v: engineOn ? 'RUNNING' : 'STOPPED',  c: engineOn ? '#10b981' : '#ef4444' },
          { l:'Signal Ticks',    v: ticks,                              c:'#0ea5e9' },
          { l:'Paper Trades',    v: trades,                             c:'#8b5cf6' },
        ].map(s => (
          <div key={s.l} className="card-pp fade-up" style={{ padding:'12px 16px' }}>
            <p className="label-pp" style={{ marginBottom:6 }}>{s.l}</p>
            <p style={{ margin:0, fontSize:18, fontWeight:800, color:s.c, fontFamily:"'JetBrains Mono',monospace" }}>{s.v}</p>
          </div>
        ))}
      </div>

      {/* Phase cards */}
      <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
        {PHASES.map(p => {
          const open   = expanded.has(p.id);
          const active = p.status === 'active';
          return (
            <div key={p.id} className={`phase-card ${p.status}`}
              style={{ borderColor: active ? p.color+'55' : 'var(--border)' }}>

              {/* Header bar */}
              <div onClick={() => toggle(p.id)} style={{ padding:'14px 20px', cursor:'pointer',
                display:'flex', alignItems:'center', gap:14, position:'relative',
                borderBottom: open ? `1px solid ${active ? p.color+'22' : 'var(--border)'}` : 'none' }}>

                {active && (
                  <div style={{ position:'absolute', top:0, left:0, right:0, height:2,
                    background:`linear-gradient(90deg,transparent,${p.color},transparent)`,
                    animation:'pulse 3s infinite' }} />
                )}

                {/* Phase number */}
                <div style={{ width:36, height:36, borderRadius:'50%', flexShrink:0,
                  display:'flex', alignItems:'center', justifyContent:'center',
                  background: active ? p.color+'18' : 'rgba(0,0,0,.2)',
                  border:`1px solid ${active ? p.color+'44' : 'var(--border)'}` }}>
                  <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:14, fontWeight:800,
                    color: active ? p.color : 'var(--text4)' }}>{p.id}</span>
                </div>

                {/* Title */}
                <div style={{ flex:1 }}>
                  <p style={{ margin:0, fontSize:14, fontWeight:700, color: active ? '#e2eeff' : 'var(--text3)',
                    letterSpacing:'-.01em' }}>{p.name}</p>
                  <p style={{ margin:'3px 0 0', fontSize:11, color: active ? 'var(--text2)' : 'var(--text4)',
                    fontFamily:"'JetBrains Mono',monospace" }}>{p.tagline}</p>
                </div>

                {/* Status + expand */}
                <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                  {active ? (
                    <span className="pill pill-green" style={{ animation:'pulse 2s infinite' }}>● ACTIVE</span>
                  ) : (
                    <span className="pill pill-dim">⬤ LOCKED</span>
                  )}
                  <span style={{ color:'var(--text3)', fontSize:12 }}>{open ? '▲' : '▼'}</span>
                </div>
              </div>

              {/* Expanded body */}
              {open && (
                <div style={{ padding:'20px', display:'grid', gridTemplateColumns:'1fr 1fr', gap:24 }}>

                  {/* Left col */}
                  <div>
                    <p style={{ fontSize:12, color:'var(--text2)', lineHeight:1.7, marginBottom:16 }}>{p.overview}</p>

                    {p.formula && (
                      <div style={{ padding:'10px 14px', background:'rgba(0,0,0,.3)',
                        border:'1px solid var(--border)', borderRadius:7, marginBottom:14,
                        fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:'var(--text2)' }}>
                        {p.formula}
                      </div>
                    )}

                    <p className="label-pp" style={{ marginBottom:8 }}>EXIT CRITERIA</p>
                    {p.exitCriteria.map((c,i) => (
                      <div key={i} style={{ display:'flex', gap:8, marginBottom:6 }}>
                        <span style={{ color: active ? p.color : 'var(--text4)', fontSize:11, flexShrink:0, marginTop:1 }}>○</span>
                        <span style={{ fontSize:12, color:'var(--text2)' }}>{c}</span>
                      </div>
                    ))}

                    {p.conflictRules && (
                      <>
                        <p className="label-pp" style={{ marginTop:16, marginBottom:8 }}>CONFLICT RESOLVER RULES</p>
                        {p.conflictRules.map((r,i) => (
                          <div key={i} style={{ display:'flex', gap:8, marginBottom:5,
                            fontFamily:"'JetBrains Mono',monospace", fontSize:11 }}>
                            <span style={{ color:'var(--text3)', minWidth:80, flexShrink:0 }}>{r.model}</span>
                            <span style={{ color:'var(--text4)' }}>→ blocked {r.blocked}</span>
                          </div>
                        ))}
                      </>
                    )}
                  </div>

                  {/* Right col */}
                  <div>
                    {/* Models */}
                    <p className="label-pp" style={{ marginBottom:8 }}>MODELS ACTIVE THIS PHASE</p>
                    <div style={{ display:'flex', flexDirection:'column', gap:4, marginBottom:16 }}>
                      {p.models.map(m => (
                        <span key={m} style={{ display:'inline-block', padding:'4px 10px', borderRadius:5,
                          background:'rgba(0,0,0,.2)', border:'1px solid var(--border)',
                          fontSize:11, color:'var(--text2)', fontFamily:"'JetBrains Mono',monospace" }}>{m}</span>
                      ))}
                    </div>

                    {/* Model rules (if defined) */}
                    {p.modelRules && (
                      <>
                        <p className="label-pp" style={{ marginBottom:8 }}>MODEL RULES</p>
                        {Object.entries(p.modelRules).map(([k,v]) => (
                          <div key={k} style={{ marginBottom:8 }}>
                            <p className="label-pp" style={{ marginBottom:3, fontSize:9 }}>{k.toUpperCase()}</p>
                            <p style={{ margin:0, fontSize:11, color:'var(--text2)', fontFamily:"'JetBrains Mono',monospace",
                              lineHeight:1.5 }}>{v}</p>
                          </div>
                        ))}
                      </>
                    )}

                    {/* Gates (Phase 0 + 1) */}
                    {p.gates && (
                      <>
                        <p className="label-pp" style={{ marginBottom:8, marginTop: p.modelRules ? 14 : 0 }}>
                          {p.id === 0 ? 'SAFETY GATES' : 'KEY REQUIREMENTS'}
                        </p>
                        {p.gates.map(g => (
                          <div key={g.id} style={{ display:'flex', gap:8, padding:'5px 0',
                            borderBottom:'1px solid var(--border)', fontFamily:"'JetBrains Mono',monospace" }}>
                            <span style={{ color: active ? p.color : 'var(--text3)', fontSize:10, minWidth:28 }}>{g.id}</span>
                            <div>
                              <p style={{ margin:0, fontSize:11, color:'var(--text2)' }}>{g.desc}</p>
                              {g.note && <p style={{ margin:0, fontSize:10, color:'var(--text4)' }}>{g.note}</p>}
                            </div>
                          </div>
                        ))}
                      </>
                    )}

                    {/* Data & files */}
                    <p className="label-pp" style={{ marginTop:16, marginBottom:6 }}>DATA REQUIRED</p>
                    {p.data.map((d,i) => <p key={i} style={{ margin:'0 0 3px', fontSize:11, color:'var(--text3)',
                      fontFamily:"'JetBrains Mono',monospace" }}>· {d}</p>)}

                    <p className="label-pp" style={{ marginTop:12, marginBottom:6 }}>KEY FILES</p>
                    {p.files.map((f_,i) => <p key={i} style={{ margin:'0 0 3px', fontSize:10, color:'var(--text4)',
                      fontFamily:"'JetBrains Mono',monospace" }}>{f_}</p>)}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Graduation criteria */}
      <div style={{ marginTop:28, padding:'20px 24px', borderRadius:12,
        background:'rgba(239,68,68,.03)', border:'1px solid rgba(239,68,68,.15)' }}>
        <p className="label-pp" style={{ color:'rgba(239,68,68,.5)', marginBottom:6 }}>
          GRADUATION — PAPER → LIVE TRADING
        </p>
        <p style={{ fontSize:12, color:'rgba(239,68,68,.35)', margin:'0 0 16px', fontFamily:"'JetBrains Mono',monospace" }}>
          All 5 models must independently satisfy ALL criteria simultaneously. No partial graduation.
          Live trading for one model while others are still in paper mode is not permitted.
        </p>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(260px,1fr))', gap:10 }}>
          {GRADUATION.map(g => (
            <div key={g.label} style={{ padding:'10px 12px', background:'rgba(0,0,0,.2)',
              border:'1px solid rgba(239,68,68,.08)', borderRadius:7 }}>
              <div style={{ display:'flex', gap:8 }}>
                <span style={{ color:'rgba(239,68,68,.3)', fontSize:11, flexShrink:0, marginTop:1 }}>○</span>
                <div>
                  <p style={{ margin:0, fontSize:11, color:'rgba(239,68,68,.45)', fontFamily:"'JetBrains Mono',monospace" }}>{g.label}</p>
                  <p style={{ margin:'3px 0 0', fontSize:10, color:'rgba(239,68,68,.2)' }}>{g.detail}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
