import React, { useState } from 'react';

const SECTION_COLOR = {
  universal: '#10b981',
  model:     '#0ea5e9',
  conflict:  '#8b5cf6',
  data:      '#f59e0b',
  phase:     '#7dd4ff',
  graduate:  '#ef4444',
  change:    '#94a3b8',
};

const SECTIONS = [
  {
    id: 'universal', title: 'Part 1 — Universal Rules', subtitle: 'Apply to ALL models, ALWAYS',
    content: [
      {
        heading: 'Safety Gates (all 6 must pass — any failure blocks the order)',
        rows: [
          { id:'G1', rule:'KALSHI_ENV = "paper"', detail:'Hard block — system refuses all orders if environment is not explicitly set to paper. No override possible.', type:'gate' },
          { id:'G2', rule:'Bid-ask spread ≤ 4¢',  detail:'If spread > 0.04, market is too illiquid. No order placed.', type:'gate' },
          { id:'G3', rule:'24h volume ≥ 5,000 contracts', detail:'Minimum volume gate. Markets under 5K contracts have insufficient liquidity for a fill at target price.', type:'gate' },
          { id:'G4', rule:'Model daily loss < 10% of allocation', detail:'Each model starts with its own allocation ($200 for the consolidated model). If the model has lost > 10%, it stops trading for the day.', type:'gate' },
          { id:'G5', rule:'No existing open position on this game for this model', detail:'Prevents pyramid sizing. One position per game per model. Models B, D, E also checked against each other via conflict resolver.', type:'gate' },
          { id:'G6', rule:'Fair value differs from market by ≥ 5¢', detail:'Edge must be ≥ 5¢ (0.05) at time of order submission. Edge is recalculated each tick — decay can cause edge to fall before fill.', type:'gate' },
        ],
      },
      {
        heading: 'Order Execution Rules',
        rows: [
          { rule:'Order type',             detail:'Limit orders ONLY. Market orders are prohibited.',           type:'rule' },
          { rule:'Cancel after',           detail:'30 seconds. If not filled, cancel and re-evaluate.',        type:'rule' },
          { rule:'Slippage cap',           detail:'Max 2¢ slippage from signal price. If best ask > signal + 0.02, do not submit.', type:'rule' },
          { rule:'Fill confirmation',      detail:'Position is only tracked after API confirms fill. Pending orders are not counted as positions.', type:'rule' },
        ],
      },
      {
        heading: 'Position Management Rules',
        rows: [
          { rule:'Max open positions (system-wide)', detail:'6 positions total across all models simultaneously.',       type:'rule' },
          { rule:'Cross-model deduplication',        detail:'Models B, D, E: only one can hold a position per game. Models A and C are never blocked by each other.', type:'rule' },
          { rule:'Pre-game close',                   detail:'All pre-game model positions (B, D, E) must close at tip-off if not yet settled.', type:'rule' },
          { rule:'Forced liquidation',               detail:'If system-wide circuit breaker fires (−15% session), ALL positions are liquidated at market immediately.', type:'rule' },
        ],
      },
      {
        heading: 'Risk Limits',
        rows: [
          { rule:'System kill switch',    detail:'If system-wide session P&L drops below −15%, all models halt and all positions are exited.', type:'limit' },
          { rule:'Per-model cap',         detail:'Each model stops trading for the day if it loses more than 10% of its individual allocation.', type:'limit' },
          { rule:'Drawdown limit',        detail:'If any model shows a 15% drawdown over a 100-trade rolling window, trading halts for that model.', type:'limit' },
          { rule:'Max trades per day',    detail:'50 trades system-wide. 20/day and 4/hour per in-game model. 10/day for Model C.', type:'limit' },
        ],
      },
      {
        heading: 'Logging & Audit Requirements',
        rows: [
          { rule:'Every tick evaluated',  detail:'Every 3-second tick is logged with market price, fair value, edge, and gate evaluation.', type:'log' },
          { rule:'Every block logged',    detail:'When any gate or entry condition fails, the specific gate ID and current value are logged.', type:'log' },
          { rule:'CLV required',          detail:'For every closed trade, CLV = entry_price − closing_line is computed and stored. Target avg < −0.02.', type:'log' },
          { rule:'Immutable audit log',   detail:'All decision logs are append-only JSONL files. No modification allowed after write.', type:'log' },
        ],
      },
    ],
  },
  {
    id: 'model', title: 'Part 2 — Model Rules', subtitle: 'Specific conditions per model',
    content: [
      {
        heading: 'Consolidated In-Game Edge Trader (Phase 0 — currently active)',
        rows: [
          { rule:'Entry — Edge',          detail:'≥ 5¢ (0.05) above market mid.',                            type:'entry' },
          { rule:'Entry — Signal score',  detail:'≥ 55 composite score.',                                    type:'entry' },
          { rule:'Entry — Persistence',  detail:'Edge must hold for 3 consecutive ticks (9 seconds).',       type:'entry' },
          { rule:'Entry — Cooldown',     detail:'120 seconds between entries on same game.',                  type:'entry' },
          { rule:'Entry — Max per game', detail:'4 entries per game.',                                        type:'entry' },
          { rule:'Exit — Stop loss',     detail:'−8% from entry price.',                                      type:'exit' },
          { rule:'Exit — Profit target', detail:'+15% from entry price. Trim 50% at +10%.',                  type:'exit' },
          { rule:'Exit — Edge compress', detail:'If edge falls below 2¢ after entry, exit immediately.',      type:'exit' },
          { rule:'Exit — Time limit',    detail:'600 seconds (10 min) max hold time.',                        type:'exit' },
          { rule:'Sizing',               detail:'Half-Kelly based on edge. Max 5% of capital ($10 on $200). 100 contract max.', type:'size' },
        ],
      },
      {
        heading: 'Model A — In-Game Price Drift (Phase 2)',
        rows: [
          { rule:'Fair value formula',   detail:'fair_value = (scoreDiff × 0.0305) + (homeCourtAdv × 0.032) + (ratingDiff × 0.018), scaled by time remaining.', type:'formula' },
          { rule:'Entry edge',           detail:'≥ 7¢ (stricter than consolidated model).',                  type:'entry' },
          { rule:'Entry signal score',   detail:'≥ 60.',                                                     type:'entry' },
          { rule:'Timing window',        detail:'2–45 minutes remaining in game.',                            type:'entry' },
          { rule:'Margin filter',        detail:'Margin must be ≤ 22 pts to enter. Blowout exit if margin > 28 pts after entry.', type:'entry' },
          { rule:'Momentum required',    detail:'Market must be trending toward fair value (not away from it).',  type:'entry' },
          { rule:'Sizing',               detail:'$5.00 max per trade, 2.5% of $200 allocation.',             type:'size' },
          { rule:'Limits',               detail:'20 trades/day, 4/hour.',                                    type:'size' },
        ],
      },
      {
        heading: 'Model C — In-Game Momentum Fade (Phase 3)',
        rows: [
          { rule:'Trigger',              detail:'One team scores ≥ 10 points in a 5-minute window.',         type:'entry' },
          { rule:'Market confirmation',  detail:'Kalshi market must have moved ≥ 10¢ during the run.',       type:'entry' },
          { rule:'Direction',            detail:'FADE the team that got the run (bet AGAINST the market overreaction).', type:'entry' },
          { rule:'Timing window',        detail:'4–30 minutes remaining in game.',                            type:'entry' },
          { rule:'Margin filter',        detail:'≤ 18 pts. Wide margins indicate the run is real, not noise.', type:'entry' },
          { rule:'Max per game',         detail:'2 entries per game.',                                        type:'entry' },
          { rule:'Stop loss',            detail:'−40% (wide — fade trades need room to work).',               type:'exit' },
          { rule:'Profit target',        detail:'+30%.',                                                      type:'exit' },
          { rule:'Thesis invalidation',  detail:'If run extends 6+ more points after entry, exit immediately.', type:'exit' },
          { rule:'Sizing',               detail:'$3.00 flat, boosted to $4.00 if run ≥ 14 pts AND market moved ≥ 14¢.', type:'size' },
          { rule:'Limits',               detail:'10 trades/day, 2/hour.',                                    type:'size' },
        ],
      },
      {
        heading: 'Model B — Pre-Game CLV Tracker (Phase 5)',
        rows: [
          { rule:'Timing window',        detail:'5 minutes to 4 hours before tip-off.',                      type:'entry' },
          { rule:'Gap to sharp line',    detail:'Kalshi price must differ from sharp closing line by ≥ 6¢.',  type:'entry' },
          { rule:'Market open time',     detail:'Market must have been open ≥ 60 minutes (avoids opening noise).', type:'entry' },
          { rule:'Starters confirmed',   detail:'Starting lineups must be confirmed before entry.',           type:'entry' },
          { rule:'Sizing tiers',         detail:'6–9¢ gap → $2.50, 9–12¢ gap → $4.00, ≥ 12¢ gap → $5.00.', type:'size' },
          { rule:'Exit rule',            detail:'Hold to settlement (resolution). No in-game exit.',         type:'exit' },
          { rule:'CLV tracking',         detail:'CLV = entry_price − closing_line at tip-off. Target avg < −0.02.', type:'log' },
        ],
      },
      {
        heading: 'Model D — Pre-Game Late Convergence (Phase 5)',
        rows: [
          { rule:'Timing window',        detail:'5–45 minutes before tip-off.',                              type:'entry' },
          { rule:'Convergence required', detail:'Market must be moving toward sharp line for ≥ 15 minutes (sustained convergence, not a spike).', type:'entry' },
          { rule:'Gap threshold',        detail:'Gap to sharp line ≥ 5¢.',                                   type:'entry' },
          { rule:'Sizing',               detail:'$3.00 base. 1.2× velocity multiplier if convergence rate is fast → $3.60 max. Hard cap $4.50.', type:'size' },
          { rule:'Exit rule',            detail:'Hold to settlement.',                                       type:'exit' },
        ],
      },
      {
        heading: 'Model E — Strong Favorite (Phase 5)',
        rows: [
          { rule:'Fair value formula',   detail:'normalCDF(pointSpread / 11.0) using SportsDataIO spread.', type:'formula' },
          { rule:'Entry conditions',     detail:'Fair value ≥ 72%, Kalshi underpriced by ≥ 6¢.',            type:'entry' },
          { rule:'Timing window',        detail:'30 minutes to 4 hours before tip-off.',                    type:'entry' },
          { rule:'Direction constraint', detail:'YES bets ONLY for first 50 trades. Switch to full bidirectional after Brier score < 0.20.', type:'entry' },
          { rule:'Sizing',               detail:'$2.00 flat during calibration (first 50 trades), then half-Kelly.', type:'size' },
          { rule:'Exit rule',            detail:'Hold to settlement.',                                       type:'exit' },
        ],
      },
    ],
  },
  {
    id: 'conflict', title: 'Part 3 — Conflict Resolver', subtitle: 'Pre-game models B, D, E — one position per game between them',
    content: [
      {
        heading: 'Conflict Resolution Rules',
        rows: [
          { rule:'Model B opens position', detail:'Immediately blocks Models D and E from opening on the same game for the duration of that position.', type:'rule' },
          { rule:'Model D opens position', detail:'Checks B first. If B is open on same game, D is blocked.',    type:'rule' },
          { rule:'Model E opens position', detail:'Checks B then D. If either is open on same game, E is blocked.', type:'rule' },
          { rule:'Models A and C',         detail:'NEVER blocked by conflict resolver. In-game models are always independent.', type:'rule' },
          { rule:'Priority order',         detail:'B > D > E. First model to open "owns" the game for the pre-game session.', type:'rule' },
          { rule:'Why this rule exists',   detail:'All 3 pre-game models can independently conclude the same game is mispriced. Without conflict resolution, they would all open positions simultaneously, creating 3× concentration.', type:'note' },
        ],
      },
    ],
  },
  {
    id: 'data', title: 'Part 4 — Data Dependency Rules', subtitle: 'What each model needs and what to do when data is unavailable',
    content: [
      {
        heading: 'Data Sources per Model',
        rows: [
          { rule:'Consolidated (Phase 0–1)', detail:'ESPN live scores — pause all evaluation if ESPN unavailable for > 45 seconds.', type:'data' },
          { rule:'Model A (Phase 2+)',       detail:'ESPN + SportsDataIO team ratings. Use ratingDiff = 0 if SportsDataIO unavailable (flag degraded mode).', type:'data' },
          { rule:'Model C (Phase 3+)',       detail:'ESPN + rolling 5-minute score per team. Pause if live data unavailable.', type:'data' },
          { rule:'Model B (Phase 5)',        detail:'The Odds API sharp closing lines. Pause entirely if sharp lines unavailable.', type:'data' },
          { rule:'Model D (Phase 5)',        detail:'The Odds API + 15-minute Kalshi price history. Pause if history incomplete.', type:'data' },
          { rule:'Model E (Phase 5)',        detail:'SportsDataIO point spreads + team ratings. Pause if spread unavailable.', type:'data' },
        ],
      },
      {
        heading: 'Staleness Limits',
        rows: [
          { rule:'ESPN game data',          detail:'Reject if > 45 seconds stale. Game is considered paused.',  type:'stale' },
          { rule:'The Odds API',            detail:'Reject if > 10 minutes stale. Use last known if < 10 min with degraded flag.', type:'stale' },
          { rule:'Kalshi orderbook',        detail:'Reject if > 10 seconds stale. Re-fetch before every gate evaluation.', type:'stale' },
          { rule:'SportsDataIO ratings',    detail:'Acceptable up to 7 days stale. Flag if older than 7 days.',  type:'stale' },
        ],
      },
    ],
  },
  {
    id: 'phase', title: 'Part 5 — Phase Gate Rules', subtitle: 'Exit criteria that must ALL pass before next phase unlocks',
    content: [
      {
        heading: 'Phase Gate Summary',
        rows: [
          { rule:'Phase 0 → 1', detail:'≥10 eval/quarter, ≥1 ENTER fires, /api/debug/signals live, zero exceptions.',            type:'gate' },
          { rule:'Phase 1 → 2', detail:'Paper orders in Kalshi dashboard, all 6 gates log correctly, MockAdapter removed.',       type:'gate' },
          { rule:'Phase 2 → 3', detail:'fair_value_engine unit tests pass, spec-correct conditions, 20+ paper trades.',           type:'gate' },
          { rule:'Phase 3 → 4', detail:'Run detector identifies 10pt runs, Model C fires independently, 10+ paper trades.',       type:'gate' },
          { rule:'Phase 4 → 5', detail:'Sharp lines fetched/stored, SportsDataIO ratings live, Model A using real ratingDiff.',   type:'gate' },
          { rule:'Phase 5 → Live', detail:'All graduation criteria met — see Part 6.',                                            type:'gate' },
          { rule:'Critical rule',  detail:'Exit criteria are AND conditions — all must pass. Partial does not count.',            type:'critical' },
        ],
      },
    ],
  },
  {
    id: 'graduate', title: 'Part 6 — Graduation Criteria', subtitle: 'Paper → Live — all 5 models must pass simultaneously',
    content: [
      {
        heading: 'Criteria (all must be met per model, all models must pass at the same time)',
        rows: [
          { rule:'Minimum sample',         detail:'≥ 100 settled trades per model.',                          type:'grad' },
          { rule:'Win rate',               detail:'> 52% across all 100+ trades.',                           type:'grad' },
          { rule:'CLV performance',        detail:'Models B and D: average CLV delta < −0.02 (beating the closing line by 2¢+ on average).', type:'grad' },
          { rule:'Brier score',            detail:'< 0.23. Measures probability calibration quality.',       type:'grad' },
          { rule:'Max drawdown',           detail:'< 15% over any 100-trade rolling window.',                type:'grad' },
          { rule:'No circuit breaker',     detail:'No active circuit breaker at time of evaluation.',        type:'grad' },
          { rule:'Simultaneous pass',      detail:'All 5 models must meet all criteria at the same evaluation. Model-by-model graduation is not permitted because the conflict resolver requires all 5 to be active.', type:'critical' },
        ],
      },
    ],
  },
  {
    id: 'change', title: 'Part 7 — Rule Change Process', subtitle: 'How to modify any rule in this document',
    content: [
      {
        heading: 'Required Steps for Any Rule Change',
        rows: [
          { rule:'Document the change',    detail:'Record: current value, proposed value, reason for change, expected impact.',   type:'process' },
          { rule:'Backtest',               detail:'Run against last 100 paper trades before applying.',                           type:'process' },
          { rule:'Version commit',         detail:'Commit to config_version_service.py with change summary.',                    type:'process' },
          { rule:'Paper validation',       detail:'Run in paper mode for ≥ 50 trades before any live trading.',                 type:'process' },
          { rule:'Timing',                 detail:'Changes take effect at session start only — never mid-session.',              type:'process' },
          { rule:'Emergency exception',    detail:'Kill switch overrides all change process rules. No documentation required for emergency shutdown.', type:'critical' },
        ],
      },
    ],
  },
];

const TYPE_COLOR = {
  gate:     '#ef4444',
  rule:     'var(--text2)',
  limit:    '#f59e0b',
  log:      '#8b5cf6',
  entry:    '#10b981',
  exit:     '#f59e0b',
  size:     '#0ea5e9',
  formula:  '#7dd4ff',
  data:     '#0ea5e9',
  stale:    '#f59e0b',
  grad:     '#10b981',
  critical: '#ef4444',
  note:     '#94a3b8',
  process:  'var(--text2)',
};

export default function Rules() {
  const [active, setActive] = useState('universal');
  const [search, setSearch] = useState('');

  const section = SECTIONS.find(s => s.id === active);

  const allRows = SECTIONS.flatMap(s =>
    s.content.flatMap(c => c.rows.map(r => ({ ...r, section: s.title, heading: c.heading })))
  );

  const filtered = search.length > 1
    ? allRows.filter(r =>
        r.rule.toLowerCase().includes(search.toLowerCase()) ||
        r.detail.toLowerCase().includes(search.toLowerCase())
      )
    : null;

  return (
    <div style={{ padding:'24px 28px', maxWidth:1300, margin:'0 auto' }} className="fade-up">

      <p className="label-pp" style={{ marginBottom:6 }}>MASTER RULES</p>
      <h1 style={{ fontSize:28, fontWeight:800, color:'#e2eeff', margin:'0 0 4px', letterSpacing:'-.02em' }}>
        PredictPod Implementation Rules
      </h1>
      <p style={{ fontSize:12, color:'var(--text3)', margin:'0 0 24px', fontFamily:"'JetBrains Mono',monospace" }}>
        7-part reference document. All models, all phases, all gates. Last updated via Master Rules doc (commit c4c9542).
      </p>

      {/* Search */}
      <div style={{ marginBottom:20 }}>
        <input placeholder="Search rules… (e.g. 'edge' or 'stop loss')"
          value={search} onChange={e => setSearch(e.target.value)}
          style={{ width:'100%', padding:'10px 14px', background:'var(--card)',
            border:'1px solid var(--border)', borderRadius:8, color:'var(--text)',
            fontSize:13, fontFamily:"'JetBrains Mono',monospace", outline:'none' }} />
      </div>

      {/* Search results */}
      {filtered && (
        <div className="card-pp" style={{ marginBottom:20, padding:16 }}>
          <p className="label-pp" style={{ marginBottom:12 }}>{filtered.length} RESULTS</p>
          {filtered.length === 0 ? (
            <p style={{ fontSize:12, color:'var(--text3)' }}>No rules match this search</p>
          ) : (
            filtered.map((r, i) => (
              <div key={i} style={{ padding:'8px 0', borderBottom:'1px solid var(--border)' }}>
                <div style={{ display:'flex', gap:8, alignItems:'flex-start', marginBottom:3 }}>
                  <span style={{ fontSize:9, padding:'2px 7px', borderRadius:3, background:'rgba(14,165,233,.1)',
                    color:'var(--accent)', border:'1px solid rgba(14,165,233,.15)', flexShrink:0,
                    fontFamily:"'JetBrains Mono',monospace" }}>{r.section.split('—')[0].trim()}</span>
                  <span style={{ fontSize:12, fontWeight:600, color: TYPE_COLOR[r.type] || 'var(--text2)' }}>{r.rule}</span>
                </div>
                <p style={{ margin:'0 0 0 8px', fontSize:12, color:'var(--text2)' }}>{r.detail}</p>
              </div>
            ))
          )}
        </div>
      )}

      {!filtered && (
        <div style={{ display:'grid', gridTemplateColumns:'200px 1fr', gap:20 }}>

          {/* Sidebar nav */}
          <div>
            {SECTIONS.map(s => (
              <button key={s.id} onClick={() => setActive(s.id)}
                style={{ display:'block', width:'100%', textAlign:'left', padding:'10px 12px',
                  borderRadius:8, marginBottom:4, cursor:'pointer',
                  background: active===s.id ? `${SECTION_COLOR[s.id]}15` : 'transparent',
                  border: `1px solid ${active===s.id ? SECTION_COLOR[s.id]+'44' : 'transparent'}`,
                  color: active===s.id ? SECTION_COLOR[s.id] : 'var(--text3)',
                  fontSize:11, fontFamily:"'JetBrains Mono',monospace", fontWeight: active===s.id ? 700 : 400,
                }}>
                {s.title.split('—')[0].trim()}
              </button>
            ))}
          </div>

          {/* Main content */}
          <div>
            {section && (
              <>
                <p className="label-pp" style={{ color: SECTION_COLOR[active], marginBottom:4 }}>
                  {section.title}
                </p>
                <p style={{ fontSize:12, color:'var(--text3)', margin:'0 0 20px',
                  fontFamily:"'JetBrains Mono',monospace" }}>{section.subtitle}</p>

                {section.content.map((block, bi) => (
                  <div key={bi} style={{ marginBottom:24 }}>
                    <p style={{ fontSize:13, fontWeight:700, color:'#e2eeff', margin:'0 0 12px',
                      paddingBottom:8, borderBottom:`2px solid ${SECTION_COLOR[active]}22` }}>
                      {block.heading}
                    </p>
                    <div className="card-pp" style={{ overflow:'hidden' }}>
                      {block.rows.map((row, ri) => (
                        <div key={ri} style={{ display:'grid', gridTemplateColumns:'200px 1fr',
                          padding:'10px 16px', borderBottom: ri < block.rows.length-1 ? '1px solid var(--border)' : 'none',
                          gap:16, alignItems:'flex-start' }}>
                          <div style={{ display:'flex', alignItems:'flex-start', gap:8 }}>
                            {row.id && (
                              <span style={{ fontSize:9, padding:'1px 6px', borderRadius:3,
                                background: `${SECTION_COLOR[active]}18`, color: SECTION_COLOR[active],
                                border:`1px solid ${SECTION_COLOR[active]}33`,
                                fontFamily:"'JetBrains Mono',monospace", fontWeight:700, flexShrink:0, marginTop:1 }}>
                                {row.id}
                              </span>
                            )}
                            <span style={{ fontSize:12, fontWeight:600, color: TYPE_COLOR[row.type] || 'var(--text2)',
                              fontFamily:"'JetBrains Mono',monospace", lineHeight:1.4 }}>{row.rule}</span>
                          </div>
                          <p style={{ margin:0, fontSize:12, color:'var(--text2)', lineHeight:1.6 }}>{row.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
