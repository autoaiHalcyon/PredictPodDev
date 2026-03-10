/**
 * TopNavbar Component
 * Global navigation bar visible on all pages
 * Contains: Logo, Navigation Links, Status Indicators, User Profile
 */
import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Activity, Zap, FileText, Settings, BarChart3, Target, Home, TrendingUp, LogOut, Lock, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ThemeToggle from './ThemeToggle';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

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
    { to: '/strategy-command-center', icon: Zap, label: 'Strategy Center' },
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
          
          {/* Right Side - Theme Toggle & User Profile */}
          <div className="flex items-center gap-3">
            <ThemeToggle />
            {isAuthenticated && <UserProfileDropdown />}
          </div>
        </div>
      </div>
    </nav>
  );
}
