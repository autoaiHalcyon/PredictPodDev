import React, { useState, useEffect, useCallback } from 'react';
import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts';

const API = process.env.REACT_APP_BACKEND_URL || '';
const f = (path) => fetch(`${API}${path}`).then(r => r.ok ? r.json() : null).catch(() => null);

// ─── Gauge bar ────────────────────────────────────────────────────────────────
function Gauge({ label, pct, color, val, limit }) {
  const clamped = Math.min(100, Math.max(0, pct));
  const warn    = clamped > 75;
  const crit    = clamped > 90;
  const c       = crit ? '#ef4444' : warn ? '#f59e0b' : color;
  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
        <span style={{ fontSize:11, color:'var(--text3)', fontFamily:"'JetBrains Mono',monospace" }}>{label}</span>
        <span style={{ fontSize:11, color:c, fontWeight:700, fontFamily:"'JetBrains Mono',monospace" }}>
          {val} / {limit}
        </span>
      </div>
      <div style={{ height:4, background:'var(--border)', borderRadius:2, overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${clamped}%`, background:c, borderRadius:2,
          transition:'width .5s ease', boxShadow: crit ? `0 0 6px ${c}` : 'none' }} />
      </div>
      <div style={{ textAlign:'right', marginTop:3, fontSize:9, color:'var(--text4)',
        fontFamily:"'JetBrains Mono',monospace" }}>{clamped.toFixed(0)}%</div>
    </div>
  );
}

export default function Portfolio() {
  const [port,   setPort]   = useState(null);
  const [pos,    setPos]    = useState([]);
  const [risk,   setRisk]   = useState(null);
  const [strat,  setStrat]  = useState(null);
  const [perf,   setPerf]   = useState(null);
  const [loading,setLoad]   = useState(true);

  const load = useCallback(async () => {
    const [po, p, r, s, pf] = await Promise.all([
      f('/api/portfolio'),
      f('/api/portfolio/positions'),
      f('/api/risk/status'),
      f('/api/strategies/summary'),
      f('/api/portfolio/performance?days=30'),
    ]);
    if (po) setPort(po);
    if (p)  setPos(p.positions || p || []);
    if (r)  setRisk(r);
    if (s)  setStrat(s);
    if (pf) setPerf(pf);
    setLoad(false);
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const balance    = port?.balance ?? 200;
  const exposure   = port?.total_exposure ?? risk?.current_exposure ?? 0;
  const upnl       = port?.unrealized_pnl ?? 0;
  const rpnl       = port?.realized_pnl ?? 0;
  const totalPnl   = port?.total_pnl ?? (upnl + rpnl);
  const openPos    = port?.open_positions ?? pos.filter(p => p.is_open).length;

  const dailyPnl      = risk?.daily_pnl ?? 0;
  const tradesToday   = risk?.trades_today ?? 0;
  const maxTrades     = risk?.max_trades_per_day ?? 50;
  const maxExposure   = risk?.max_open_exposure ?? 1000;
  const maxLoss       = risk?.max_daily_loss ?? 500;
  const isLocked      = risk?.is_locked_out ?? false;
  const lockReason    = risk?.lockout_reason ?? '';
  const canTrade      = risk?.can_trade ?? true;

  const expPct  = (exposure / maxExposure) * 100;
  const lossPct = (Math.abs(Math.min(0, dailyPnl)) / maxLoss) * 100;
  const tradePct = (tradesToday / maxTrades) * 100;

  const models = strat?.strategies ? Object.entries(strat.strategies) : [];

  return (
    <div style={{ padding:'24px 28px', maxWidth:1300, margin:'0 auto' }} className="fade-up">

      <p className="label-pp" style={{ marginBottom:6 }}>PORTFOLIO</p>
      <h1 style={{ fontSize:28, fontWeight:800, color:'#e2eeff', margin:'0 0 20px', letterSpacing:'-.02em' }}>Capital Overview</h1>

      {/* Kill switch banner */}
      {isLocked && (
        <div style={{ padding:'12px 18px', borderRadius:8, marginBottom:20,
          background:'rgba(239,68,68,.1)', border:'2px solid rgba(239,68,68,.4)' }}>
          <p style={{ margin:0, fontFamily:"'JetBrains Mono',monospace", fontWeight:700, color:'#ef4444', fontSize:13 }}>
            ⚠ CIRCUIT BREAKER ACTIVE — {lockReason}
          </p>
        </div>
      )}

      {/* Capital metrics row */}
      <div className="stagger" style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:14, marginBottom:24 }}>
        <BigStat label="CAPITAL" val={`$${balance.toFixed(2)}`} sub="paper allocation" color="var(--accent)" />
        <BigStat label="OPEN EXPOSURE" val={`$${exposure.toFixed(2)}`}
          sub={`${((exposure/balance)*100).toFixed(1)}% of capital`}
          color={exposure > balance * 0.7 ? '#f59e0b' : '#10b981'} />
        <BigStat label="UNREALIZED P&L" val={`${upnl>=0?'+':''}$${upnl.toFixed(2)}`}
          sub="open positions" color={upnl>=0?'#10b981':'#ef4444'} />
        <BigStat label="REALIZED P&L" val={`${rpnl>=0?'+':''}$${rpnl.toFixed(2)}`}
          sub="settled trades" color={rpnl>=0?'#10b981':'#ef4444'} />
        <BigStat label="OPEN POSITIONS" val={openPos} sub="across all models" color="#8b5cf6" />
      </div>

      {/* Two-column middle */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 320px', gap:16, marginBottom:16 }}>

        {/* Open positions table */}
        <div>
          <p className="label-pp" style={{ marginBottom:10 }}>OPEN POSITIONS</p>
          <div className="card-pp" style={{ overflow:'hidden' }}>
            {loading ? (
              <div style={{ padding:16 }}><div className="skeleton" style={{ height:80 }} /></div>
            ) : pos.filter(p => p.is_open !== false).length === 0 ? (
              <div style={{ padding:'32px', textAlign:'center' }}>
                <p style={{ fontSize:13, color:'var(--text3)' }}>No open positions</p>
                <p style={{ fontSize:11, color:'var(--text4)', fontFamily:"'JetBrains Mono',monospace", marginTop:4 }}>
                  System is in signal-evaluation mode
                </p>
              </div>
            ) : (
              <table className="pp-table">
                <thead>
                  <tr>{['MARKET','MODEL','SIDE','ENTRY','CURRENT','EDGE CAPTURED','STATUS','UNRLZD'].map(h=><th key={h}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {pos.filter(p => p.is_open !== false).map((p, i) => {
                    const upnl_ = p.unrealized_pnl ?? 0;
                    const edge  = p.edge_captured ?? 0;
                    return (
                      <tr key={p.id || i}>
                        <td style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, maxWidth:160,
                          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                          {p.market_id?.slice(0,22) || '--'}
                        </td>
                        <td style={{ fontSize:10, fontFamily:"'JetBrains Mono',monospace", color:'var(--accent)' }}>
                          {p.model_id || 'Model A'}
                        </td>
                        <td>
                          <span className={`pill pill-${(p.side||'yes')==='yes'?'green':'red'}`}>
                            {(p.side||'YES').toUpperCase()}
                          </span>
                        </td>
                        <td style={{ fontFamily:"'JetBrains Mono',monospace" }}>
                          {p.entry_price || p.avg_entry_price ? `${((p.entry_price||p.avg_entry_price)*100).toFixed(0)}¢` : '--'}
                        </td>
                        <td style={{ fontFamily:"'JetBrains Mono',monospace" }}>
                          {p.current_price || p.current_prob ? `${((p.current_price||p.current_prob/100)*100).toFixed(0)}¢` : '--'}
                        </td>
                        <td style={{ fontFamily:"'JetBrains Mono',monospace",
                          color: edge >= 0 ? '#10b981' : '#ef4444' }}>
                          {edge ? `${(edge).toFixed(1)}¢` : '--'}
                        </td>
                        <td>
                          <span className="pill pill-blue">
                            {p.game_status ? p.game_status.toUpperCase() : 'OPEN'}
                          </span>
                        </td>
                        <td style={{ fontFamily:"'JetBrains Mono',monospace", fontWeight:700,
                          color: upnl_>=0?'#10b981':'#ef4444' }}>
                          {upnl_>=0?'+':''}${upnl_.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Risk panel */}
        <div>
          <p className="label-pp" style={{ marginBottom:10 }}>RISK STATUS</p>
          <div className="card-pp" style={{ padding:'16px 18px' }}>

            {/* Can trade indicator */}
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:16, padding:'8px 12px',
              borderRadius:6, background: canTrade ? 'rgba(16,185,129,.06)' : 'rgba(239,68,68,.06)',
              border:`1px solid ${canTrade?'rgba(16,185,129,.2)':'rgba(239,68,68,.2)'}` }}>
              <div style={{ width:8, height:8, borderRadius:'50%',
                background: canTrade?'#10b981':'#ef4444',
                boxShadow: `0 0 5px ${canTrade?'#10b981':'#ef4444'}` }} />
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, fontWeight:700,
                color: canTrade?'#10b981':'#ef4444' }}>
                {canTrade ? 'TRADING ALLOWED' : 'TRADING BLOCKED'}
              </span>
            </div>

            {/* Gauges */}
            <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
              <Gauge label="Exposure" pct={expPct}
                val={`$${exposure.toFixed(0)}`} limit={`$${maxExposure.toFixed(0)}`} color="#0ea5e9" />
              <Gauge label="Daily Loss" pct={lossPct}
                val={`$${Math.abs(Math.min(0,dailyPnl)).toFixed(0)}`} limit={`$${maxLoss.toFixed(0)}`} color="#ef4444" />
              <Gauge label="Trades Today" pct={tradePct}
                val={tradesToday} limit={maxTrades} color="#8b5cf6" />
            </div>

            {/* Risk limits table */}
            <div style={{ marginTop:16 }}>
              <p className="label-pp" style={{ marginBottom:8 }}>MASTER RULES LIMITS</p>
              {[
                { l:'Max position size',  v:'$5.00 / trade' },
                { l:'Max open positions', v:'6 system-wide' },
                { l:'Kill switch (system)', v:'−15% session' },
                { l:'Kill switch (model)',  v:'−10% allocation' },
                { l:'Max drawdown',        v:'−15% / 100 trades' },
                { l:'Trades / day',        v:'50 system-wide' },
                { l:'Trades / hour',       v:'10 system-wide' },
              ].map(r => (
                <div key={r.l} style={{ display:'flex', justifyContent:'space-between',
                  padding:'5px 0', borderBottom:'1px solid var(--border)',
                  fontFamily:"'JetBrains Mono',monospace", fontSize:10 }}>
                  <span style={{ color:'var(--text3)' }}>{r.l}</span>
                  <span style={{ color:'var(--text2)' }}>{r.v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Model breakdown */}
      {models.length > 0 && (
        <div>
          <p className="label-pp" style={{ marginBottom:10 }}>MODEL COMPARISON</p>
          <div className="card-pp" style={{ overflow:'hidden' }}>
            <table className="pp-table">
              <thead>
                <tr>{['MODEL','TRADES','WIN RATE','TOTAL P&L','REALIZED','UNREALIZED','MAX DD','STATUS'].map(h=><th key={h}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {models.map(([id, s]) => {
                  const p   = s.portfolio || {};
                  const pnl = p.total_pnl ?? 0;
                  return (
                    <tr key={id}>
                      <td style={{ fontFamily:"'JetBrains Mono',monospace", color:'var(--accent)', fontWeight:600 }}>
                        {id.replace('model_','M').replace('_disciplined','A').replace('_high_frequency','B').replace('_institutional','C').replace('ingame_edge_trader','Edge')}
                      </td>
                      <td style={{ fontFamily:"'JetBrains Mono',monospace" }}>{p.total_trades ?? 0}</td>
                      <td style={{ fontFamily:"'JetBrains Mono',monospace",
                        color: (p.win_rate??0)>52?'#10b981':'var(--text2)' }}>
                        {p.win_rate != null ? `${p.win_rate}%` : '--'}
                      </td>
                      <td style={{ fontFamily:"'JetBrains Mono',monospace", fontWeight:700,
                        color: pnl>0?'#10b981':pnl<0?'#ef4444':'var(--text3)' }}>
                        {pnl>=0?'+':''}${pnl.toFixed(2)}
                      </td>
                      <td style={{ fontFamily:"'JetBrains Mono',monospace" }}>
                        ${(p.realized_pnl??0).toFixed(2)}
                      </td>
                      <td style={{ fontFamily:"'JetBrains Mono',monospace" }}>
                        ${(p.unrealized_pnl??0).toFixed(2)}
                      </td>
                      <td style={{ fontFamily:"'JetBrains Mono',monospace",
                        color:(p.max_drawdown_pct??0)>10?'#ef4444':'var(--text2)' }}>
                        {p.max_drawdown_pct != null ? `${p.max_drawdown_pct.toFixed(1)}%` : '--'}
                      </td>
                      <td>
                        <span className={`pill ${s.enabled ? 'pill-green' : 'pill-dim'}`}>
                          {s.enabled ? 'ACTIVE' : 'IDLE'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function BigStat({ label, val, sub, color }) {
  return (
    <div className="card-pp fade-up" style={{ padding:'14px 16px' }}>
      <p className="label-pp" style={{ marginBottom:6 }}>{label}</p>
      <p style={{ margin:0, fontSize:22, fontWeight:800, color, fontFamily:"'JetBrains Mono',monospace",
        letterSpacing:'-.01em', marginBottom:4 }}>{val}</p>
      {sub && <p style={{ margin:0, fontSize:10, color:'var(--text4)', fontFamily:"'JetBrains Mono',monospace" }}>{sub}</p>}
    </div>
  );
}
