import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const API = process.env.REACT_APP_BACKEND_URL || '';

const NAV = [
  { to: '/',         label: 'Dashboard',  exact: true },
  { to: '/trades',   label: 'Trades' },
  { to: '/portfolio',label: 'Portfolio' },
  { to: '/phases',   label: 'Phases' },
  { to: '/rules',    label: 'Rules' },
];

export default function TopNavbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [health, setHealth] = useState(null);
  const [open, setOpen] = useState(false);
  const ref = useRef();

  useEffect(() => {
    const fetch_ = () =>
      fetch(`${API}/api/health`).then(r => r.json()).then(setHealth).catch(() => {});
    fetch_();
    const t = setInterval(fetch_, 10000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const engineOn = health?.autonomous_enabled ?? false;
  const dbOk     = health?.db_ping ?? false;

  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 100,
      background: 'rgba(5,9,17,.92)',
      borderBottom: '1px solid #111e34',
      backdropFilter: 'blur(12px)',
      display: 'flex', alignItems: 'center',
      padding: '0 24px', height: 52,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      {/* Logo */}
      <Link to="/" style={{ textDecoration:'none', display:'flex', alignItems:'center', gap:8, marginRight:32 }}>
        <span style={{ width:28, height:28, borderRadius:6, background:'linear-gradient(135deg,#0ea5e9,#10b981)',
          display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, fontWeight:700, color:'#fff', flexShrink:0 }}>P</span>
        <span style={{ fontSize:14, fontWeight:700, color:'#e2eeff', letterSpacing:'.02em' }}>
          Predict<span style={{ color:'#0ea5e9' }}>Pod</span>
        </span>
        <span style={{ fontSize:9, padding:'1px 6px', borderRadius:3, background:'rgba(14,165,233,.15)',
          color:'#0ea5e9', letterSpacing:'.1em', border:'1px solid rgba(14,165,233,.2)' }}>ALPHA</span>
      </Link>

      {/* Nav links */}
      <div style={{ display:'flex', gap:2, flex:1 }}>
        {NAV.map(n => {
          const active = n.exact ? location.pathname === n.to : location.pathname.startsWith(n.to);
          return (
            <Link key={n.to} to={n.to} style={{ textDecoration:'none' }}>
              <div style={{
                padding:'6px 12px', borderRadius:6, fontSize:12, fontWeight:500,
                color: active ? '#e2eeff' : '#3a5570',
                background: active ? 'rgba(14,165,233,.1)' : 'transparent',
                borderBottom: active ? '2px solid #0ea5e9' : '2px solid transparent',
                transition: 'all .15s', letterSpacing:'.04em',
              }}>
                {n.label}
              </div>
            </Link>
          );
        })}
      </div>

      {/* Status indicators */}
      <div style={{ display:'flex', alignItems:'center', gap:16, marginRight:16 }}>
        <StatusDot on={engineOn} label="ENGINE" />
        <StatusDot on={dbOk}    label="DB" />
        <StatusDot on={true}    label="PAPER" color="#f59e0b" />
      </div>

      {/* User menu */}
      <div ref={ref} style={{ position:'relative' }}>
        <button onClick={() => setOpen(o => !o)} style={{
          display:'flex', alignItems:'center', gap:8, padding:'5px 10px',
          background:'rgba(14,165,233,.08)', border:'1px solid rgba(14,165,233,.15)',
          borderRadius:6, cursor:'pointer', color:'#7a9bbf', fontSize:11,
        }}>
          <span>{user?.username || user?.email?.split('@')[0] || 'user'}</span>
          <span style={{ fontSize:8 }}>▾</span>
        </button>
        {open && (
          <div style={{
            position:'absolute', top:'calc(100% + 6px)', right:0, minWidth:140,
            background:'#0a1220', border:'1px solid #1a2e4a', borderRadius:8,
            padding:'4px 0', zIndex:200,
            boxShadow:'0 8px 24px rgba(0,0,0,.5)',
          }}>
            <MenuItem onClick={() => { navigate('/rules'); setOpen(false); }}>Master Rules</MenuItem>
            <MenuItem onClick={() => { navigate('/phases'); setOpen(false); }}>Phases</MenuItem>
            <div style={{ borderTop:'1px solid #111e34', margin:'4px 0' }} />
            <MenuItem onClick={() => { logout(); navigate('/login'); }} danger>Sign out</MenuItem>
          </div>
        )}
      </div>
    </nav>
  );
}

function StatusDot({ on, label, color }) {
  const c = color || (on ? '#10b981' : '#3a5570');
  return (
    <div style={{ display:'flex', alignItems:'center', gap:5 }}>
      <div style={{ width:6, height:6, borderRadius:'50%', background:c,
        boxShadow: on ? `0 0 5px ${c}` : 'none',
        animation: on && !color ? 'pulse 2s infinite' : 'none' }} />
      <span style={{ fontSize:9, color:c, letterSpacing:'.1em' }}>{label}</span>
    </div>
  );
}

function MenuItem({ onClick, danger, children }) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        width:'100%', textAlign:'left', padding:'8px 14px', background: hover ? 'rgba(255,255,255,.04)' : 'transparent',
        border:'none', cursor:'pointer', fontSize:12, fontFamily:'inherit',
        color: danger ? '#ef4444' : '#7a9bbf',
      }}>
      {children}
    </button>
  );
}
