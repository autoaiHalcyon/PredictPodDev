import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Textarea } from '../components/ui/textarea';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  ArrowLeft,
  RefreshCw,
  Settings as SettingsIcon,
  Shield,
  Key,
  Save,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Power,
  DollarSign,
  Zap,
  TestTube,
  Activity
} from 'lucide-react';
import { 
  getSettings, 
  getRiskLimits, 
  updateRiskLimits, 
  formatCurrency,
  getKalshiKeys,
  saveKalshiKeys,
  deleteKalshiKeys,
  validateKalshiKeys,
  enableLiveTrading,
  disableLiveTrading,
  activateKillSwitch,
  getGuardrails,
  updateGuardrails,
  getSandboxStatus,
  getCapitalDeployment,
  setCapitalDeployment,
  getReconciliationStatus,
  forceReconciliation
} from '../services/api';
import { toast } from 'sonner';

const Settings = () => {
  const [settings, setSettings] = useState(null);
  const [limits, setLimits] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editedLimits, setEditedLimits] = useState({});
  
  // Sandbox state
  const [sandboxStatus, setSandboxStatus] = useState(null);
  const [capitalDeployment, setCapitalDeploymentState] = useState(null);
  const [reconStatus, setReconStatus] = useState(null);
  const [changingMode, setChangingMode] = useState(false);
  const [showAggressiveConfirm, setShowAggressiveConfirm] = useState(false);
  
  // Kalshi credentials state
  const [kalshiStatus, setKalshiStatus] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [privateKey, setPrivateKey] = useState('');
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [validating, setValidating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  
  // Live trading confirmation dialog
  const [showLiveConfirm, setShowLiveConfirm] = useState(false);
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [togglingLive, setTogglingLive] = useState(false);
  
  // Guardrails state
  const [guardrails, setGuardrails] = useState(null);
  const [editedGuardrails, setEditedGuardrails] = useState({});
  const [savingGuardrails, setSavingGuardrails] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [settingsData, limitsData, kalshiData, guardrailsData, sandboxData, capitalData, reconData] = await Promise.all([
        getSettings(),
        getRiskLimits(),
        getKalshiKeys().catch(() => null),
        getGuardrails().catch(() => null),
        getSandboxStatus().catch(() => null),
        getCapitalDeployment().catch(() => null),
        getReconciliationStatus().catch(() => null)
      ]);
      setSettings(settingsData);
      setLimits(limitsData);
      setEditedLimits(limitsData);
      setKalshiStatus(kalshiData);
      if (guardrailsData) {
        setGuardrails(guardrailsData);
        setEditedGuardrails(guardrailsData);
      }
      setSandboxStatus(sandboxData);
      setCapitalDeploymentState(capitalData);
      setReconStatus(reconData);
    } catch (error) {
      console.error('Failed to load settings:', error);
      toast.error('Failed to load settings');
    }
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSaveLimits = async () => {
    setSaving(true);
    try {
      await updateRiskLimits(editedLimits);
      setLimits(editedLimits);
      toast.success('Risk limits saved');
    } catch (error) {
      console.error('Failed to save limits:', error);
      toast.error('Failed to save limits');
    }
    setSaving(false);
  };

  const handleLimitChange = (key, value) => {
    setEditedLimits(prev => ({
      ...prev,
      [key]: parseFloat(value) || 0
    }));
  };

  // Kalshi credential handlers
  const handleSaveCredentials = async () => {
    if (!apiKey.trim() || !privateKey.trim()) {
      toast.error('Both API Key and Private Key are required');
      return;
    }
    
    setSavingCredentials(true);
    try {
      const result = await saveKalshiKeys(apiKey, privateKey);
      if (result.success) {
        toast.success('Credentials saved securely');
        setApiKey('');
        setPrivateKey('');
        await loadData();
      } else {
        toast.error(result.message || 'Failed to save credentials');
      }
    } catch (error) {
      console.error('Failed to save credentials:', error);
      toast.error('Failed to save credentials');
    }
    setSavingCredentials(false);
  };

  const handleValidateCredentials = async () => {
    setValidating(true);
    try {
      const result = await validateKalshiKeys();
      if (result.valid) {
        toast.success(`Credentials validated! Balance: ${formatCurrency(result.balance)}`);
      } else {
        toast.error(result.message || 'Validation failed');
      }
      await loadData();
    } catch (error) {
      console.error('Validation failed:', error);
      toast.error('Validation failed');
    }
    setValidating(false);
  };

  const handleDeleteCredentials = async () => {
    setDeleting(true);
    try {
      await deleteKalshiKeys();
      toast.success('Credentials deleted');
      await loadData();
    } catch (error) {
      console.error('Failed to delete credentials:', error);
      toast.error('Failed to delete credentials');
    }
    setDeleting(false);
  };

  const handleEnableLiveTrading = async () => {
    setTogglingLive(true);
    try {
      const result = await enableLiveTrading(true);
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
      await loadData();
    } catch (error) {
      console.error('Failed to enable live trading:', error);
      toast.error('Failed to enable live trading');
    }
    setTogglingLive(false);
    setShowLiveConfirm(false);
  };

  const handleDisableLiveTrading = async () => {
    setTogglingLive(true);
    try {
      const result = await disableLiveTrading();
      toast.success(result.message);
      await loadData();
    } catch (error) {
      console.error('Failed to disable live trading:', error);
      toast.error('Failed to disable live trading');
    }
    setTogglingLive(false);
  };

  const handleKillSwitch = async () => {
    try {
      const result = await activateKillSwitch();
      toast.warning(result.message);
      await loadData();
    } catch (error) {
      console.error('Kill switch failed:', error);
      toast.error('Kill switch failed');
    }
    setShowKillConfirm(false);
  };

  const handleCapitalModeChange = async (newMode) => {
    if (newMode === 'aggressive') {
      setShowAggressiveConfirm(true);
      return;
    }
    
    setChangingMode(true);
    try {
      const result = await setCapitalDeployment(newMode);
      if (result.success) {
        toast.success(`Capital deployment mode set to ${newMode.toUpperCase()}`);
        await loadData();
      } else {
        toast.error(result.message);
      }
    } catch (error) {
      console.error('Failed to change capital mode:', error);
      toast.error('Failed to change capital mode');
    }
    setChangingMode(false);
  };

  const confirmAggressiveMode = async () => {
    setChangingMode(true);
    try {
      const result = await setCapitalDeployment('aggressive', true, true);
      if (result.success) {
        toast.warning('AGGRESSIVE mode enabled - higher risk limits active');
        await loadData();
      } else {
        toast.error(result.message);
      }
    } catch (error) {
      console.error('Failed to set aggressive mode:', error);
      toast.error('Failed to set aggressive mode');
    }
    setChangingMode(false);
    setShowAggressiveConfirm(false);
  };

  const handleForceReconciliation = async () => {
    try {
      await forceReconciliation();
      toast.success('Reconciliation triggered');
      await loadData();
    } catch (error) {
      toast.error('Reconciliation failed');
    }
  };

  const handleSaveGuardrails = async () => {
    setSavingGuardrails(true);
    try {
      await updateGuardrails(editedGuardrails);
      setGuardrails(editedGuardrails);
      toast.success('Guardrails saved');
    } catch (error) {
      console.error('Failed to save guardrails:', error);
      toast.error('Failed to save guardrails');
    }
    setSavingGuardrails(false);
  };

  const handleGuardrailChange = (key, value) => {
    setEditedGuardrails(prev => ({
      ...prev,
      [key]: parseFloat(value) || 0
    }));
  };

  const isLiveActive = kalshiStatus?.is_live_trading_active;
  const hasValidCredentials = kalshiStatus?.credentials_info?.validation_status === 'valid';

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Page Header */}
      <header className="border-b border-gray-800 bg-gray-900/50">
        <div className="max-w-[1400px] mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SettingsIcon className="w-6 h-6 text-blue-500" />
              <h1 className="text-xl font-bold">Settings</h1>
            </div>
            <Button variant="ghost" size="sm" onClick={loadData} data-testid="refresh-settings-btn">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-[1400px] mx-auto px-4 py-6">
        {loading && !settings ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Sandbox Status */}
            {sandboxStatus && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <TestTube className="w-5 h-5 text-cyan-500" />
                  Sandbox Status
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-3 bg-gray-800/50 rounded-lg">
                    <div className="text-sm text-gray-400">Mode</div>
                    <div className="font-semibold text-cyan-400 uppercase">{sandboxStatus.mode}</div>
                  </div>
                  <div className="p-3 bg-gray-800/50 rounded-lg">
                    <div className="text-sm text-gray-400">Balance</div>
                    <div className="font-semibold">{formatCurrency(sandboxStatus.balance)}</div>
                  </div>
                  <div className="p-3 bg-gray-800/50 rounded-lg">
                    <div className="text-sm text-gray-400">Positions</div>
                    <div className="font-semibold">{sandboxStatus.positions_count}</div>
                  </div>
                  <div className="p-3 bg-gray-800/50 rounded-lg">
                    <div className="text-sm text-gray-400">Working Orders</div>
                    <div className="font-semibold">{sandboxStatus.working_orders_count}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Capital Deployment Mode */}
            {capitalDeployment && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-orange-500" />
                  Capital Deployment Mode
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <Select 
                      value={capitalDeployment.mode} 
                      onValueChange={handleCapitalModeChange}
                      disabled={changingMode}
                    >
                      <SelectTrigger className="w-48 bg-gray-800 border-gray-700" data-testid="capital-mode-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-gray-800 border-gray-700">
                        <SelectItem value="conservative">
                          <span className="text-green-400">CONSERVATIVE</span>
                        </SelectItem>
                        <SelectItem value="normal">
                          <span className="text-yellow-400">NORMAL</span>
                        </SelectItem>
                        <SelectItem value="aggressive">
                          <span className="text-red-400">AGGRESSIVE</span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    {changingMode && <Loader2 className="w-5 h-5 animate-spin" />}
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-800/50 rounded-lg">
                    <div>
                      <div className="text-sm text-gray-400">Max Trade</div>
                      <div className="font-semibold">{formatCurrency(capitalDeployment.max_trade_size_dollars)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-400">Daily Loss Cap</div>
                      <div className="font-semibold">{formatCurrency(capitalDeployment.max_daily_loss_dollars)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-400">Max Exposure</div>
                      <div className="font-semibold">{formatCurrency(capitalDeployment.max_total_exposure_dollars)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-400">Rate Limit</div>
                      <div className="font-semibold">{capitalDeployment.max_orders_per_hour}/hr</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Reconciliation Status */}
            {reconStatus && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-green-500" />
                    Position Reconciliation
                  </h3>
                  <Button size="sm" variant="outline" onClick={handleForceReconciliation} data-testid="force-recon-btn">
                    Force Check
                  </Button>
                </div>
                <div className="flex items-center gap-4">
                  {reconStatus.total_unreconciled === 0 ? (
                    <Badge className="bg-green-900/50 text-green-400 border border-green-700">
                      All Reconciled
                    </Badge>
                  ) : (
                    <>
                      <Badge className="bg-red-900/50 text-red-400 border border-red-700">
                        {reconStatus.total_unreconciled} Unreconciled
                      </Badge>
                      {reconStatus.critical_mismatches > 0 && (
                        <Badge className="bg-red-900 text-red-300">
                          {reconStatus.critical_mismatches} Critical
                        </Badge>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Trading Mode Status */}
            <div className={`rounded-xl border p-6 ${
              isLiveActive 
                ? 'bg-red-950/50 border-red-700' 
                : 'bg-gray-900 border-gray-800'
            }`}>
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Shield className="w-5 h-5 text-blue-500" />
                Trading Mode
              </h3>
              
              <div className="space-y-4">
                {/* Current Mode Display */}
                <div className="flex items-center justify-between p-4 bg-gray-800/50 rounded-lg">
                  <div>
                    <div className="font-semibold text-lg">
                      {isLiveActive ? 'LIVE TRADING' : 'Paper Trading'}
                    </div>
                    <div className="text-sm text-gray-400">
                      {isLiveActive 
                        ? 'Trading with real money on Kalshi' 
                        : 'Simulated trading with mock money'}
                    </div>
                  </div>
                  <Badge 
                    className={isLiveActive 
                      ? 'bg-red-900/50 text-red-400 border border-red-700' 
                      : 'bg-green-900/50 text-green-400 border border-green-700'
                    }
                    data-testid="trading-mode-badge"
                  >
                    {isLiveActive ? 'LIVE' : 'PAPER'}
                  </Badge>
                </div>

                {/* Live Trading Toggle */}
                {hasValidCredentials && (
                  <div className="flex items-center justify-between p-4 border border-gray-700 rounded-lg">
                    <div>
                      <div className="font-medium">Enable Live Trading</div>
                      <div className="text-sm text-gray-400">
                        Switch between paper and live trading modes
                      </div>
                    </div>
                    <Switch
                      checked={isLiveActive}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setShowLiveConfirm(true);
                        } else {
                          handleDisableLiveTrading();
                        }
                      }}
                      disabled={togglingLive}
                      data-testid="live-trading-toggle"
                    />
                  </div>
                )}

                {/* Kill Switch */}
                {isLiveActive && (
                  <div className="p-4 bg-red-900/20 rounded-lg border border-red-900/50">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-red-400 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4" />
                          Emergency Kill Switch
                        </div>
                        <div className="text-sm text-gray-400">
                          Immediately stops all live trading
                        </div>
                      </div>
                      <Button 
                        variant="destructive" 
                        size="sm"
                        onClick={() => setShowKillConfirm(true)}
                        data-testid="kill-switch-btn"
                      >
                        <Power className="w-4 h-4 mr-2" />
                        KILL SWITCH
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* API Configuration */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Key className="w-5 h-5 text-purple-500" />
                Kalshi API Configuration
              </h3>
              
              <div className="space-y-4">
                {/* Current credential status */}
                {kalshiStatus?.has_credentials && (
                  <div className="p-4 bg-gray-800/50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-gray-400">Stored Key:</span>
                        <code className="bg-gray-700 px-2 py-1 rounded text-sm">
                          {kalshiStatus.credentials_info?.masked_key_last4 || '****'}
                        </code>
                      </div>
                      <div className="flex items-center gap-2">
                        {kalshiStatus.credentials_info?.validation_status === 'valid' && (
                          <Badge className="bg-green-900/50 text-green-400 border border-green-700">
                            <CheckCircle2 className="w-3 h-3 mr-1" />
                            Validated
                          </Badge>
                        )}
                        {kalshiStatus.credentials_info?.validation_status === 'invalid' && (
                          <Badge className="bg-red-900/50 text-red-400 border border-red-700">
                            <XCircle className="w-3 h-3 mr-1" />
                            Invalid
                          </Badge>
                        )}
                        {kalshiStatus.credentials_info?.validation_status === 'not_validated' && (
                          <Badge className="bg-yellow-900/50 text-yellow-400 border border-yellow-700">
                            Not Validated
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Button 
                        size="sm" 
                        variant="outline" 
                        onClick={handleValidateCredentials}
                        disabled={validating}
                        data-testid="validate-credentials-btn"
                      >
                        {validating ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                        )}
                        Validate
                      </Button>
                      <Button 
                        size="sm" 
                        variant="outline"
                        className="text-red-400 hover:text-red-300"
                        onClick={handleDeleteCredentials}
                        disabled={deleting}
                        data-testid="delete-credentials-btn"
                      >
                        {deleting ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <Trash2 className="w-4 h-4 mr-2" />
                        )}
                        Delete
                      </Button>
                    </div>
                  </div>
                )}

                {/* Add/Update credentials form */}
                <div className="space-y-4 p-4 border border-gray-700 rounded-lg">
                  <div className="text-sm text-gray-400 mb-2">
                    {kalshiStatus?.has_credentials 
                      ? 'Update your Kalshi API credentials:' 
                      : 'Enter your Kalshi API credentials to enable live trading:'}
                  </div>
                  <div>
                    <Label className="text-gray-400">API Key ID</Label>
                    <Input
                      type="text"
                      placeholder="Enter your Kalshi API Key ID"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="bg-gray-800 border-gray-700 mt-1"
                      data-testid="api-key-input"
                    />
                  </div>
                  <div>
                    <Label className="text-gray-400">Private Key (PEM format)</Label>
                    <Textarea
                      placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;..."
                      value={privateKey}
                      onChange={(e) => setPrivateKey(e.target.value)}
                      className="bg-gray-800 border-gray-700 mt-1 font-mono text-sm h-32"
                      data-testid="private-key-input"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Your private key is encrypted before storage and never exposed.
                    </p>
                  </div>
                  <Button 
                    onClick={handleSaveCredentials}
                    disabled={savingCredentials || !apiKey.trim() || !privateKey.trim()}
                    data-testid="save-credentials-btn"
                  >
                    {savingCredentials ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Save className="w-4 h-4 mr-2" />
                    )}
                    Save Credentials
                  </Button>
                </div>

                <div className="p-3 bg-blue-900/20 rounded-lg border border-blue-900/50 text-sm text-blue-400">
                  <strong>How to get API credentials:</strong>
                  <ol className="list-decimal ml-4 mt-1 space-y-1">
                    <li>Log in to your Kalshi account</li>
                    <li>Go to Profile Settings → API Keys</li>
                    <li>Click "Create New API Key"</li>
                    <li>Download and save your private key securely</li>
                  </ol>
                </div>
              </div>
            </div>

            {/* Trading Guardrails */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Zap className="w-5 h-5 text-yellow-500" />
                  Live Trading Guardrails
                </h3>
                <Button
                  size="sm"
                  onClick={handleSaveGuardrails}
                  disabled={savingGuardrails}
                  data-testid="save-guardrails-btn"
                >
                  {savingGuardrails ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  Save
                </Button>
              </div>
              <p className="text-sm text-gray-400 mb-4">
                Safety limits enforced before ANY live trade is placed.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label className="text-gray-400">Max $ per Trade</Label>
                  <Input
                    type="number"
                    value={editedGuardrails.max_dollars_per_trade || ''}
                    onChange={(e) => handleGuardrailChange('max_dollars_per_trade', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                    data-testid="max-per-trade-input"
                  />
                </div>
                <div>
                  <Label className="text-gray-400">Max Open Exposure ($)</Label>
                  <Input
                    type="number"
                    value={editedGuardrails.max_open_exposure || ''}
                    onChange={(e) => handleGuardrailChange('max_open_exposure', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                    data-testid="max-exposure-input"
                  />
                </div>
                <div>
                  <Label className="text-gray-400">Max Daily Loss ($)</Label>
                  <Input
                    type="number"
                    value={editedGuardrails.max_daily_loss || ''}
                    onChange={(e) => handleGuardrailChange('max_daily_loss', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                    data-testid="max-daily-loss-input"
                  />
                </div>
                <div>
                  <Label className="text-gray-400">Max Trades per Hour</Label>
                  <Input
                    type="number"
                    value={editedGuardrails.max_trades_per_hour || ''}
                    onChange={(e) => handleGuardrailChange('max_trades_per_hour', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                    data-testid="max-trades-hour-input"
                  />
                </div>
                <div>
                  <Label className="text-gray-400">Max Trades per Day</Label>
                  <Input
                    type="number"
                    value={editedGuardrails.max_trades_per_day || ''}
                    onChange={(e) => handleGuardrailChange('max_trades_per_day', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                    data-testid="max-trades-day-input"
                  />
                </div>
              </div>
            </div>

            {/* Risk Limits */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Shield className="w-5 h-5 text-red-500" />
                  Paper Trading Risk Limits
                </h3>
                <Button
                  size="sm"
                  onClick={handleSaveLimits}
                  disabled={saving}
                  data-testid="save-limits-btn"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  Save Changes
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label className="text-gray-400">Max Position Size ($)</Label>
                  <Input
                    type="number"
                    value={editedLimits.max_position_size || ''}
                    onChange={(e) => handleLimitChange('max_position_size', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">Maximum $ per single position</p>
                </div>
                <div>
                  <Label className="text-gray-400">Max Trade Size ($)</Label>
                  <Input
                    type="number"
                    value={editedLimits.max_trade_size || ''}
                    onChange={(e) => handleLimitChange('max_trade_size', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">Maximum $ per single trade</p>
                </div>
                <div>
                  <Label className="text-gray-400">Max Open Exposure ($)</Label>
                  <Input
                    type="number"
                    value={editedLimits.max_open_exposure || ''}
                    onChange={(e) => handleLimitChange('max_open_exposure', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">Maximum total exposure across all positions</p>
                </div>
                <div>
                  <Label className="text-gray-400">Max Daily Loss ($)</Label>
                  <Input
                    type="number"
                    value={editedLimits.max_daily_loss || ''}
                    onChange={(e) => handleLimitChange('max_daily_loss', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">Maximum loss before trading lockout</p>
                </div>
                <div>
                  <Label className="text-gray-400">Max Trades Per Day</Label>
                  <Input
                    type="number"
                    value={editedLimits.max_trades_per_day || ''}
                    onChange={(e) => handleLimitChange('max_trades_per_day', e.target.value)}
                    className="bg-gray-800 border-gray-700 mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">Maximum number of trades per day</p>
                </div>
              </div>
            </div>

            {/* Model Info */}
            {settings?.model_info && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h3 className="text-lg font-semibold mb-4">Probability Model</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-400">Version:</span>
                    <span className="ml-2">{settings.model_info.version}</span>
                  </div>
                  <div>
                    <span className="text-gray-400">Type:</span>
                    <span className="ml-2">{settings.model_info.type}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-400">Features:</span>
                    <span className="ml-2">{settings.model_info.features?.join(', ')}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-400">Notes:</span>
                    <span className="ml-2 text-gray-500">{settings.model_info.notes}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Live Trading Confirmation Dialog */}
      <AlertDialog open={showLiveConfirm} onOpenChange={setShowLiveConfirm}>
        <AlertDialogContent className="bg-gray-900 border-gray-700">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-400 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" />
              Enable Live Trading?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-gray-300">
              <div className="space-y-3">
                <p>
                  <strong className="text-white">Warning:</strong> You are about to enable live trading 
                  with real money on Kalshi.
                </p>
                <div className="bg-red-900/20 p-3 rounded border border-red-900/50 text-sm">
                  <ul className="list-disc ml-4 space-y-1">
                    <li>Real money will be used for all trades</li>
                    <li>Losses are permanent and cannot be reversed</li>
                    <li>Trading carries significant financial risk</li>
                    <li>Past performance does not guarantee future results</li>
                  </ul>
                </div>
                <p className="text-sm">
                  By enabling live trading, you acknowledge that you understand 
                  and accept these risks.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-gray-800 border-gray-700">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleEnableLiveTrading}
              className="bg-red-600 hover:bg-red-700"
              disabled={togglingLive}
              data-testid="confirm-live-trading-btn"
            >
              {togglingLive ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <DollarSign className="w-4 h-4 mr-2" />
              )}
              I Understand, Enable Live Trading
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Kill Switch Confirmation Dialog */}
      <AlertDialog open={showKillConfirm} onOpenChange={setShowKillConfirm}>
        <AlertDialogContent className="bg-gray-900 border-gray-700">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-400 flex items-center gap-2">
              <Power className="w-5 h-5" />
              Activate Kill Switch?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-gray-300">
              <div className="space-y-3">
                <p>
                  This will <strong className="text-white">immediately stop all live trading</strong>.
                </p>
                <div className="bg-yellow-900/20 p-3 rounded border border-yellow-900/50 text-sm">
                  <ul className="list-disc ml-4 space-y-1">
                    <li>New orders will NOT be placed</li>
                    <li>Existing open positions will NOT be closed automatically</li>
                    <li>You will need to manually re-enable live trading</li>
                  </ul>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-gray-800 border-gray-700">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleKillSwitch}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-kill-switch-btn"
            >
              <Power className="w-4 h-4 mr-2" />
              Activate Kill Switch
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Aggressive Mode Confirmation Dialog */}
      <AlertDialog open={showAggressiveConfirm} onOpenChange={setShowAggressiveConfirm}>
        <AlertDialogContent className="bg-gray-900 border-gray-700">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-400 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" />
              Enable AGGRESSIVE Mode?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-gray-300">
              <div className="space-y-3">
                <p>
                  <strong className="text-white">Warning:</strong> AGGRESSIVE mode significantly increases risk limits.
                </p>
                <div className="bg-red-900/20 p-3 rounded border border-red-900/50 text-sm">
                  <ul className="list-disc ml-4 space-y-1">
                    <li>Max trade size: $100 (vs $5 in conservative)</li>
                    <li>Max daily loss: $500 (vs $25 in conservative)</li>
                    <li>Max exposure: $1,000 (vs $50 in conservative)</li>
                    <li>Higher rate limits and looser liquidity checks</li>
                  </ul>
                </div>
                <p className="text-sm text-yellow-400">
                  Only use this mode if you fully understand and accept the increased risk.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-gray-800 border-gray-700">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmAggressiveMode}
              className="bg-red-600 hover:bg-red-700"
              disabled={changingMode}
              data-testid="confirm-aggressive-btn"
            >
              {changingMode ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Zap className="w-4 h-4 mr-2" />
              )}
              I Understand, Enable AGGRESSIVE
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Settings;
