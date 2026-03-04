import React from 'react';
import { useTheme } from '../context/ThemeContext';
import { Sun, Moon } from 'lucide-react';

const ThemeToggle = ({ className = '' }) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      data-testid="theme-toggle"
      className={`p-2 rounded-lg transition-all duration-200 hover:bg-muted ${className}`}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? (
        <Sun className="h-5 w-5 text-amber-400 hover:text-amber-300 transition-colors" />
      ) : (
        <Moon className="h-5 w-5 text-slate-600 hover:text-slate-800 transition-colors" />
      )}
    </button>
  );
};

export default ThemeToggle;
