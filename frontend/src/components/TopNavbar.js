/**
 * TopNavbar Component
 * Global navigation bar visible on all pages
 * Contains: Logo, Navigation Links, Status Indicators, User Profile
 */
import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Activity, Zap, FileText, Settings, BarChart3, Target, Home, TrendingUp, LogOut, Lock, User, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ThemeToggle from './ThemeToggle';
import { Switch } from './ui/switch';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// Trading Mode Indicator Component
const TradingModeIndicator = () => {
  const [isPaperMode, setIsPaperMode] = useState(true); // Default to Paper trading
  const [loading, setLoading] = useState(false);

  // Fetch current trading mode on mount
  useEffect(() => {
    const fetchTradingMode = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/settings/kalshi_keys`);
        if (res.ok) {
          const data = await res.json();
          setIsPaperMode(data.trading_mode === 'paper' || !data.is_live_trading_active);
        }
      } catch (e) {
        console.error('Failed to fetch trading mode:', e);
      }
    };
    fetchTradingMode();
  }, []);

  const handleToggle = async (checked) => {
    // checked = true means Paper mode (safe), false means Live mode (dangerous)
    const newMode = checked ? 'paper' : 'live';
    
    // For Live mode, show confirmation
    if (!checked) {
      const confirmed = window.confirm(
        '⚠️ WARNING: You are about to enable LIVE TRADING mode.\n\n' +
        'This will execute REAL trades with REAL money on your Kalshi account.\n\n' +
        'Are you sure you want to continue?'
      );
      if (!confirmed) return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/settings/trading_mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });
      if (res.ok) {
        setIsPaperMode(checked);
      }
    } catch (e) {
      console.error('Failed to update trading mode:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
        isPaperMode 
          ? 'bg-amber-500/10 border-amber-500/30' 
          : 'bg-red-500/10 border-red-500/30'
      }`}
      data-testid="trading-mode-indicator"
    >
      <Shield className={`w-4 h-4 ${isPaperMode ? 'text-amber-400' : 'text-red-400'}`} />
      <span className={`text-xs font-bold ${isPaperMode ? 'text-amber-400' : 'text-red-400'}`}>
        {isPaperMode ? 'PAPER' : 'LIVE'}
      </span>
      <Switch
        checked={isPaperMode}
        onCheckedChange={handleToggle}
        disabled={loading}
        className="data-[state=checked]:bg-amber-500 data-[state=unchecked]:bg-red-500"
        data-testid="trading-mode-switch"
      />
    </div>
  );
};

// Logo Component
const Logo = () => (
  <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity" data-testid="logo">
    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
      <Activity className="w-5 h-5 text-white" />
    </div>
    <span className="text-xl font-bold tracking-tight">
      Predict<span className="text-primary">Pod</span>
    </span>
    <span className="text-xs px-2 py-0.5 bg-primary/20 rounded text-primary font-medium">v2.0</span>
  </Link>
);

// Navigation Link Component
const NavLink = ({ to, icon: Icon, children, isActive }) => (
  <Link
    to={to}
    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
      isActive
        ? 'bg-primary/20 text-primary border-b-2 border-primary'
        : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
    }`}
    data-testid={`nav-${to.replace('/', '') || 'home'}`}
  >
    {Icon && <Icon className="w-4 h-4" />}
    {children}
  </Link>
);

// User Profile Dropdown Component
const UserProfileDropdown = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
    setIsOpen(false);
  };

  if (!user) {
    return null;
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg text-foreground hover:bg-muted/50 transition-colors"
        title={user.email}
      >
        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
          {user.name.charAt(0).toUpperCase()}
        </div>
        <span className="hidden sm:inline text-xs">{user.name.split(' ')[0]}</span>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-card border border-border rounded-lg shadow-lg z-50">
          {/* User Info */}
          <div className="px-4 py-3 border-b border-border">
            <p className="text-sm font-semibold text-foreground">{user.name}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>

          {/* Menu Items */}
          <div className="py-2">
            <Link
              to="/"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-4 py-2 text-sm text-foreground hover:bg-muted/50 transition-colors"
            >
              <Home className="w-4 h-4" />
              Dashboard
            </Link>
            <Link
              to="/change-password"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-4 py-2 text-sm text-foreground hover:bg-muted/50 transition-colors"
            >
              <Lock className="w-4 h-4" />
              Change Password
            </Link>
          </div>

          {/* Logout Button */}
          <div className="px-4 py-2 border-t border-border">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-0 py-2 text-sm text-red-600 hover:text-red-700 font-medium transition-colors w-full"
            >
              <LogOut className="w-4 h-4" />
              Log Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// Main TopNavbar Component
export default function TopNavbar() {
  const location = useLocation();
  const currentPath = location.pathname;
  const { isAuthenticated } = useAuth();

  const navItems = [
    { to: '/', icon: Home, label: 'Terminal' },
    { to: '/all-games', icon: Activity, label: 'All Games' },
    { to: '/strategy-center', icon: Zap, label: 'Strategy Center' },
    { to: '/trades', icon: FileText, label: 'Trades' },
    { to: '/portfolio', icon: BarChart3, label: 'Portfolio' },
    { to: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <nav 
      className="sticky top-10 z-40 bg-card/95 backdrop-blur border-b border-border"
      data-testid="top-navbar"
    >
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Logo />
          
          {/* Navigation Links */}
          {isAuthenticated && (
            <div className="flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  icon={item.icon}
                  isActive={currentPath === item.to || (item.to !== '/' && currentPath.startsWith(item.to))}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          )}
          
          {/* Right Side - Trading Mode, Theme Toggle & User Profile */}
          <div className="flex items-center gap-3">
            {isAuthenticated && <TradingModeIndicator />}
            <ThemeToggle />
            {isAuthenticated && <UserProfileDropdown />}
          </div>
        </div>
      </div>
    </nav>
  );
}
