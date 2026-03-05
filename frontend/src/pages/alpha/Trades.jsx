import React, { useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const f = (path) => fetch(`${API}${path}`).then(r => r.ok ? r.json() : null).catch(() => null);

const MODEL_LABELS = {
  ingame_edge_trader:      'In-Game Edge',
  model_a_disciplined:     'Model A',
  model_b_high_frequency:  'Model B',
  model_c_institutional:   'Model C',
};

export default function Trades() {
  const [trades,    setTrades]  = useState([]);
  const [decisions, setDecs]    = useState([]);
  const [strat,     setStrat]   = useState(null);
  const [loading,   setLoading] = useState(true);
  const [filter,    setFilter]  = useState('all');  // all | open | closed
  const [modelFilter, setMF]    = useState('all');

  const load = useCallback(async () => {
    const [t, d, s] = await Promise.all([
      f('/api/trades?limit=200'),
      f('/api/decisions/latest?limit=200'),
      f('/api/strategies/summary'),
    ]);
    if (t) setTrades(t.trades || t || []);
    if (d) setDecs(d.decisions || []);
    if (s) setStrat(s);
    setLoading(false);
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const allTrades  = trades;
  const filtTrades = allTrades.filter(t => {
    if (filter === 'open')   return t.status === 'open';
    if (filter === 'closed') return t.status !== 'open';
    return true;
  }).filter(t => {
    if (modelFilter === 'all') return true;
    return (t.model_id || t.signal_type || '').toLowerCase().includes(modelFilter);
  });

  const totalPnl   = strat?.comparison?.total_pnl ? Object.values(strat.comparison.total_pnl).reduce((a,b) => a+b, 0) : 0;
  const totalTrades = allTrades.length;
  const openCount  = allTrades.filter(t => t.status === 'open').length;
  const enterCount = decisions.filter(d => (d.decision||d.decision_type) === 'ENTER').length;
  const blockCount = decisions.filter(d => (d.decision||d.decision_type) === 'BLOCK').length;
  const holdCount  = decisions.filter(d => (d.decision||d.decision_type) === 'HOLD').length;

  // Per-model breakdown from strategy_manager summary
  const models = strat?.strategies ? Object.entries(strat.strategies) : [];

  return (
    <div style={{ padding:'24px 28px', maxWidth:1440, margin:'0 auto' }} className="fade-up">

      {/* Header */}
      <p className="label-pp" style={{ marginBottom:6 }}>PAPER TRADING</p>
      <h1 style={{ fontSize:28, fontWeight:800, color:'#e2eeff', margin:'0 0 20px', letterSpacing:'-.02em' }}>Trade Blotter</h1>

      {/* Top stats */}
      <div className="stagger" style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:12, marginBottom:24 }}>
        <StatCard label="SESSION P&L"   val={`${totalPnl>=0?'+':''}$${totalPnl.toFixed(2)}`}  color={totalPnl>0?'#10b981':totalPnl<0?'#ef4444':'var(--text3)'} />
        <StatCard label="TOTAL TRADES"  val={totalTrades}  color="var(--accent)" />
        <StatCard label="OPEN POSITIONS" val={openCount}   color="#f59e0b" />
        <StatCard label="ENTER SIGNALS" val={enterCount}   color="#10b981" />
        <StatCard label="HOLD"          val={holdCount}    color="#f59e0b" />
        <StatCard label="BLOCKED"       val={blockCount}   color="#ef4444" />
      </div>

      {/* Per-model summary strip */}
      {models.length > 0 && (
        <div style={{ marginBottom:20 }}>
          <p className="label-pp" style={{ marginBottom:8 }}>PER-MODEL PERFORMANCE</p>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:10 }}>
            {models.map(([id, s]) => {
              const port = s.portfolio || {};
              const pnl  = port.total_pnl ?? 0;
              return (
                <div key={id} className="card-pp" style={{ padding:'12px 14px' }}>
                  <p className="label-pp" style={{ marginBottom:4 }}>{MODEL_LABELS[id] || id}</p>
                  <p style={{ margin:'0 0 4px', fontSize:18, fontWeight:800, fontFamily:"'JetBrains Mono',monospace",
                    color: pnl>0?'#10b981':pnl<0?'#ef4444':'var(--text3)' }}>
                    {pnl>=0?'+':''}${pnl.toFixed(2)}
                  </p>
                  <div style={{ display:'flex', gap:8, fontSize:10, color:'var(--text3)',
                    fontFamily:"'JetBrains Mono',monospace" }}>
                    <span>{port.total_trades ?? 0} trades</span>
                    <span>·</span>
                    <span>{port.win_rate != null ? `${port.win_rate}% win` : '--'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Two-column layout: trades + decision log */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 420px', gap:16 }}>

        {/* ── Trade blotter ── */}
        <div>
          {/* Filters */}
          <div style={{ display:'flex', gap:8, marginBottom:12, alignItems:'center' }}>
            <p className="label-pp" style={{ margin:0 }}>TRADES</p>
            <div style={{ marginLeft:'auto', display:'flex', gap:6 }}>
              {['all','open','closed'].map(v => (
                <button key={v} onClick={() => setFilter(v)}
                  style={{ padding:'4px 10px', borderRadius:5, border:'1px solid var(--border)',
                    background: filter===v ? 'rgba(14,165,233,.15)' : 'var(--card)',
                    color: filter===v ? 'var(--accent)' : 'var(--text3)',
                    fontSize:10, cursor:'pointer', fontFamily:'inherit', letterSpacing:'.05em' }}>
                  {v.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="card-pp" style={{ overflow:'hidden' }}>
            {loading ? (
              <div style={{ padding:20 }}>
                {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height:44, marginBottom:6 }} />)}
              </div>
            ) : filtTrades.length === 0 ? (
              <div style={{ padding:'40px', textAlign:'center' }}>
                <p style={{ fontSize:13, color:'var(--text3)' }}>No paper trades yet</p>
                <p style={{ fontSize:11, color:'var(--text4)', fontFamily:"'JetBrains Mono',monospace", marginTop:4 }}>
                  Engine is running in signal-evaluation mode (Phase 0)
                </p>
              </div>
            ) : (
              <div style={{ overflowX:'auto' }}>
                <table className="pp-table">
                  <thead>
                    <tr>
                      {['TIME','MODEL','TICKER','SIDE','ENTRY','SIZE','STATUS','P&L','CLV'].map(h => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filtTrades.map((t, i) => {
                      const pnl  = t.pnl ?? t.unrealized_pnl ?? t.realized_pnl ?? 0;
                      const clv  = t.clv_delta ?? t.edge_at_entry ?? null;
                      const open = t.status === 'open';
                      return (
                        <tr key={t.id || i}>
                          <td style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:'var(--text3)' }}>
                            {t.created_at ? new Date(t.created_at).toLocaleTimeString('en-US',{hour12:false}) : '--'}
                          </td>
                          <td>
                            <span style={{ fontSize:10, padding:'2px 7px', borderRadius:4,
                              background:'rgba(14,165,233,.08)', color:'#0ea5e9',
                              border:'1px solid rgba(14,165,233,.15)',
                              fontFamily:"'JetBrains Mono',monospace" }}>
                              {MODEL_LABELS[t.model_id || t.signal_type] || t.model_id || 'Edge'}
                            </span>
                          </td>
                          <td style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:'var(--text4)',
                            maxWidth:160, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                            {t.market_id?.slice(0,22) || '--'}
                          </td>
                          <td>
                            <span className={`pill pill-${(t.side||'yes')==='yes'?'green':'red'}`}>
                              {(t.side||'YES').toUpperCase()}
                            </span>
                          </td>
                          <td style={{ fontFamily:"'JetBrains Mono',monospace" }}>
                            {t.price ? `${(t.price*100).toFixed(0)}¢` : t.avg_fill_price ? `${(t.avg_fill_price*100).toFixed(0)}¢` : '--'}
                          </td>
                          <td style={{ fontFamily:"'JetBrains Mono',monospace" }}>
                            ${(t.amount ?? t.quantity ?? 0).toFixed ? (t.amount ?? t.quantity ?? 0).toFixed(2) : '--'}
                          </td>
                          <td>
                            <span className={`pill pill-${open?'blue':'dim'}`}>
                              {(t.status||'OPEN').toUpperCase()}
                            </span>
                          </td>
                          <td style={{ fontFamily:"'JetBrains Mono',monospace", fontWeight:700,
                            color: pnl>0?'#10b981':pnl<0?'#ef4444':'var(--text3)' }}>
                            {pnl>=0?'+':''}${pnl.toFixed(2)}
                          </td>
                          <td style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10,
                            color: clv != null && clv < 0 ? '#10b981' : 'var(--text4)' }}>
                            {clv != null ? `${(clv*100).toFixed(1)}¢` : '--'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* CLV explanation */}
          <div style={{ marginTop:10, padding:'8px 14px', borderRadius:6,
            background:'rgba(0,0,0,.2)', border:'1px solid var(--border)' }}>
            <p style={{ margin:0, fontSize:10, color:'var(--text4)', fontFamily:"'JetBrains Mono',monospace" }}>
              CLV = Closing Line Value. Negative = entry beat closing line (good). Model B/D target avg CLV &lt; −0.02.
            </p>
          </div>
        </div>

        {/* ── Decision audit log ── */}
        <div>
          <p className="label-pp" style={{ marginBottom:12 }}>DECISION AUDIT LOG</p>

          {/* Decision counts */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8, marginBottom:12 }}>
            {[
              { l:'ENTER', v:enterCount, c:'#10b981' },
              { l:'HOLD',  v:holdCount,  c:'#f59e0b' },
              { l:'BLOCK', v:blockCount, c:'#ef4444' },
            ].map(s => (
              <div key={s.l} className="card-pp" style={{ padding:'10px', textAlign:'center' }}>
                <p style={{ margin:0, fontSize:20, fontWeight:800, color:s.c, fontFamily:"'JetBrains Mono',monospace" }}>{s.v}</p>
                <p className="label-pp" style={{ margin:'3px 0 0', fontSize:9 }}>{s.l}</p>
              </div>
            ))}
          </div>

          <div className="card-pp" style={{ maxHeight:560, overflowY:'auto' }}>
            {decisions.length === 0 ? (
              <div style={{ padding:'24px', textAlign:'center', fontSize:11, color:'var(--text4)',
                fontFamily:"'JetBrains Mono',monospace" }}>
                No decisions logged yet
              </div>
            ) : decisions.slice(0, 100).map((d, i) => {
              const dtype = d.decision || d.decision_type || 'HOLD';
              const color = dtype==='ENTER'?'#10b981':dtype==='BLOCK'?'#ef4444':'#f59e0b';
              return (
                <div key={i} style={{ display:'flex', gap:8, padding:'7px 12px',
                  borderBottom:'1px solid var(--border)', alignItems:'flex-start' }}>
                  <span style={{ fontSize:10, color:'var(--text4)', minWidth:56,
                    fontFamily:"'JetBrains Mono',monospace", flexShrink:0, marginTop:1 }}>
                    {d.timestamp?.slice(11,19) || '--'}
                  </span>
                  <span className={`pill pill-${dtype==='ENTER'?'green':dtype==='BLOCK'?'red':'yellow'}`}
                    style={{ flexShrink:0 }}>
                    {dtype}
                  </span>
                  <span style={{ fontSize:11, color:'var(--text2)', flex:1, lineHeight:1.4 }}>
                    {d.reason || d.model_id || '--'}
                  </span>
                  {d.edge_cents != null && (
                    <span style={{ fontSize:10, color:'var(--text4)',
                      fontFamily:"'JetBrains Mono',monospace", flexShrink:0 }}>
                      {d.edge_cents.toFixed(1)}¢
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Gate violation breakdown */}
          {blockCount > 0 && (
            <div style={{ marginTop:10 }}>
              <p className="label-pp" style={{ marginBottom:8 }}>TOP BLOCK REASONS</p>
              {(() => {
                const reasons = {};
                decisions.filter(d => (d.decision||d.decision_type) === 'BLOCK').forEach(d => {
                  const k = (d.reason||'Unknown').slice(0,40);
                  reasons[k] = (reasons[k]||0)+1;
                });
                return Object.entries(reasons)
                  .sort((a,b) => b[1]-a[1])
                  .slice(0,5)
                  .map(([k,v]) => (
                    <div key={k} style={{ display:'flex', justifyContent:'space-between',
                      padding:'5px 10px', borderRadius:5, marginBottom:4,
                      background:'rgba(239,68,68,.05)', border:'1px solid rgba(239,68,68,.1)' }}>
                      <span style={{ fontSize:11, color:'var(--text3)', fontFamily:"'JetBrains Mono',monospace" }}>{k}</span>
                      <span style={{ fontSize:11, color:'#ef4444', fontWeight:700,
                        fontFamily:"'JetBrains Mono',monospace" }}>{v}×</span>
                    </div>
                  ));
              })()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, val, color }) {
  return (
    <div className="card-pp fade-up" style={{ padding:'12px 14px' }}>
      <p className="label-pp" style={{ marginBottom:6 }}>{label}</p>
      <p style={{ margin:0, fontSize:18, fontWeight:800, color, fontFamily:"'JetBrains Mono',monospace" }}>{val}</p>
    </div>
  );
}
