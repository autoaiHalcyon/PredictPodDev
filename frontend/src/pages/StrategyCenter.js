/**
 * StrategyCenter.js
 * Two-panel layout: Models List (left) + Model Editor (right)
 */
import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  AlertTriangle,
  Plus,
  Save,
  Copy,
  Trash2,
  Settings,
  Activity,
  Target,
  TrendingUp,
  DollarSign,
  Clock,
  BarChart3,
  Check,
  X
} from "lucide-react";
import { toast } from "sonner";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Default empty model template
const EMPTY_MODEL = {
  name: "",
  status: "active",
  capital_allocation_pct: 50,
  rules: {
    min_edge_threshold: 0.03,
    min_clv_required: 0.02,
    max_odds: 0.85,
    min_odds: 0.05,
    kelly_fraction: 0.5,
    max_position_size_pct: 0.05,
    lookback_window_hours: 24,
    min_market_volume: 1000,
    notes: ""
  }
};

export default function StrategyCenter() {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [editedModel, setEditedModel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isNewModel, setIsNewModel] = useState(false);

  // Fetch all models
  const fetchModels = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/trading-models`);
      if (res.ok) {
        const data = await res.json();
        setModels(data.models || []);
        // Select first model if none selected
        if (!selectedModel && data.models?.length > 0) {
          selectModel(data.models[0]);
        }
      }
    } catch (e) {
      console.error("Failed to fetch models:", e);
      toast.error("Failed to load models");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Select a model for editing
  const selectModel = (model) => {
    setSelectedModel(model);
    setEditedModel(JSON.parse(JSON.stringify(model)));
    setIsNewModel(false);
  };

  // Start creating a new model
  const startNewModel = () => {
    setSelectedModel(null);
    setEditedModel(JSON.parse(JSON.stringify(EMPTY_MODEL)));
    setIsNewModel(true);
  };

  // Toggle model status
  const toggleModelStatus = async (modelId, e) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/trading-models/${modelId}/toggle`, {
        method: "PATCH"
      });
      if (res.ok) {
        const data = await res.json();
        // Update local state
        setModels(prev => prev.map(m => 
          m.id === modelId ? { ...m, status: data.status } : m
        ));
        if (selectedModel?.id === modelId) {
          setSelectedModel(prev => ({ ...prev, status: data.status }));
          setEditedModel(prev => ({ ...prev, status: data.status }));
        }
        toast.success(`Model ${data.status}`);
      }
    } catch (e) {
      console.error("Failed to toggle model:", e);
      toast.error("Failed to toggle model status");
    }
  };

  // Update edited model field
  const updateField = (field, value) => {
    setEditedModel(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Update rule field
  const updateRule = (field, value) => {
    setEditedModel(prev => ({
      ...prev,
      rules: {
        ...prev.rules,
        [field]: value
      }
    }));
  };

  // Save model
  const saveModel = async () => {
    if (!editedModel.name?.trim()) {
      toast.error("Model name is required");
      return;
    }

    setSaving(true);
    try {
      const url = isNewModel 
        ? `${API_BASE}/api/trading-models`
        : `${API_BASE}/api/trading-models/${selectedModel.id}`;
      
      const method = isNewModel ? "POST" : "PUT";
      
      const params = new URLSearchParams({
        name: editedModel.name,
        status: editedModel.status,
        capital_allocation_pct: editedModel.capital_allocation_pct
      });

      const res = await fetch(`${url}?${params}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules: editedModel.rules })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to save model");
      }

      const data = await res.json();
      toast.success("Model saved successfully");
      
      // Refresh models list
      await fetchModels();
      
      // Select the saved model
      if (data.model) {
        selectModel(data.model);
      }
    } catch (e) {
      console.error("Failed to save model:", e);
      toast.error(e.message || "Failed to save model");
    } finally {
      setSaving(false);
    }
  };

  // Save as new model
  const saveAsNew = async () => {
    const newName = prompt("Enter name for new model:", `${editedModel.name} (Copy)`);
    if (!newName?.trim()) return;

    setSaving(true);
    try {
      const params = new URLSearchParams({
        name: newName,
        status: "active",
        capital_allocation_pct: editedModel.capital_allocation_pct
      });

      const res = await fetch(`${API_BASE}/api/trading-models?${params}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules: editedModel.rules })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to save model");
      }

      const data = await res.json();
      toast.success("Model saved successfully");
      
      // Refresh and select new model
      await fetchModels();
      if (data.model) {
        selectModel(data.model);
      }
    } catch (e) {
      console.error("Failed to save model:", e);
      toast.error(e.message || "Failed to save model");
    } finally {
      setSaving(false);
    }
  };

  // Delete model
  const deleteModel = async (modelId) => {
    if (!confirm("Are you sure you want to delete this model?")) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/trading-models/${modelId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        toast.success("Model deleted");
        await fetchModels();
        setSelectedModel(null);
        setEditedModel(null);
      }
    } catch (e) {
      console.error("Failed to delete model:", e);
      toast.error("Failed to delete model");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Settings className="w-6 h-6 text-primary" />
            Strategy Center
          </h1>
          <p className="text-sm text-muted-foreground">
            Configure and manage your trading models
          </p>
        </div>
      </header>

      <div className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Panel - Models List */}
          <div className="col-span-4">
            <Card className="h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Models
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {models.map((model) => (
                  <div
                    key={model.id}
                    data-testid={`model-item-${model.id}`}
                    onClick={() => selectModel(model)}
                    className={`
                      p-3 rounded-lg border cursor-pointer transition-all
                      ${selectedModel?.id === model.id 
                        ? "border-primary bg-primary/10" 
                        : "border-border hover:border-primary/50"
                      }
                      ${model.status === "disabled" ? "opacity-50" : ""}
                    `}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{model.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {model.capital_allocation_pct}% allocation
                        </p>
                      </div>
                      <div className="flex items-center gap-2 ml-2">
                        <Badge 
                          variant={model.status === "active" ? "default" : "secondary"}
                          className={model.status === "active" ? "bg-green-600" : ""}
                        >
                          {model.status === "active" ? "Active" : "Disabled"}
                        </Badge>
                        <Switch
                          checked={model.status === "active"}
                          onCheckedChange={() => {}}
                          onClick={(e) => toggleModelStatus(model.id, e)}
                          data-testid={`toggle-${model.id}`}
                        />
                      </div>
                    </div>
                  </div>
                ))}

                {/* Add New Model Button */}
                <Button
                  variant="outline"
                  className="w-full mt-4 border-dashed"
                  onClick={startNewModel}
                  data-testid="add-new-model-btn"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add New Model
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Right Panel - Model Editor */}
          <div className="col-span-8">
            <Card className="h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Target className="w-5 h-5" />
                  {isNewModel ? "New Model" : "Model Editor"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {editedModel ? (
                  <div className="space-y-6">
                    {/* Disabled Warning Banner */}
                    {editedModel.status === "disabled" && !isNewModel && (
                      <div className="p-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5 text-yellow-500" />
                        <p className="text-yellow-500 text-sm">
                          This model is currently disabled and will not execute trades
                        </p>
                      </div>
                    )}

                    {/* Model Name */}
                    <div className="space-y-2">
                      <Label htmlFor="model-name">Model Name</Label>
                      <Input
                        id="model-name"
                        value={editedModel.name}
                        onChange={(e) => updateField("name", e.target.value)}
                        placeholder="Enter model name"
                        data-testid="model-name-input"
                      />
                    </div>

                    {/* Capital Allocation */}
                    <div className="space-y-2">
                      <Label htmlFor="capital-allocation">Capital Allocation (%)</Label>
                      <Input
                        id="capital-allocation"
                        type="number"
                        min="0"
                        max="100"
                        value={editedModel.capital_allocation_pct}
                        onChange={(e) => updateField("capital_allocation_pct", parseFloat(e.target.value) || 0)}
                        data-testid="capital-allocation-input"
                      />
                    </div>

                    {/* Rule Fields Grid */}
                    <div className="border-t border-border pt-4">
                      <h3 className="font-semibold mb-4 flex items-center gap-2">
                        <Activity className="w-4 h-4" />
                        Trading Rules
                      </h3>
                      
                      <div className="grid grid-cols-2 gap-4">
                        {/* Min Edge Threshold */}
                        <div className="space-y-2">
                          <Label htmlFor="min-edge">Min Edge Threshold</Label>
                          <Input
                            id="min-edge"
                            type="number"
                            step="0.01"
                            value={editedModel.rules?.min_edge_threshold || 0}
                            onChange={(e) => updateRule("min_edge_threshold", parseFloat(e.target.value) || 0)}
                            placeholder="0.03"
                            data-testid="min-edge-input"
                          />
                        </div>

                        {/* Min CLV Required */}
                        <div className="space-y-2">
                          <Label htmlFor="min-clv">Min CLV Required</Label>
                          <Input
                            id="min-clv"
                            type="number"
                            step="0.01"
                            value={editedModel.rules?.min_clv_required || 0}
                            onChange={(e) => updateRule("min_clv_required", parseFloat(e.target.value) || 0)}
                            placeholder="0.02"
                            data-testid="min-clv-input"
                          />
                        </div>

                        {/* Max Odds */}
                        <div className="space-y-2">
                          <Label htmlFor="max-odds">Max Odds</Label>
                          <Input
                            id="max-odds"
                            type="number"
                            step="0.01"
                            value={editedModel.rules?.max_odds || 0}
                            onChange={(e) => updateRule("max_odds", parseFloat(e.target.value) || 0)}
                            placeholder="0.85"
                            data-testid="max-odds-input"
                          />
                        </div>

                        {/* Min Odds */}
                        <div className="space-y-2">
                          <Label htmlFor="min-odds">Min Odds</Label>
                          <Input
                            id="min-odds"
                            type="number"
                            step="0.01"
                            value={editedModel.rules?.min_odds || 0}
                            onChange={(e) => updateRule("min_odds", parseFloat(e.target.value) || 0)}
                            placeholder="0.05"
                            data-testid="min-odds-input"
                          />
                        </div>

                        {/* Kelly Fraction */}
                        <div className="space-y-2">
                          <Label htmlFor="kelly-fraction">Kelly Fraction</Label>
                          <Input
                            id="kelly-fraction"
                            type="number"
                            step="0.01"
                            value={editedModel.rules?.kelly_fraction || 0}
                            onChange={(e) => updateRule("kelly_fraction", parseFloat(e.target.value) || 0)}
                            placeholder="0.5"
                            data-testid="kelly-fraction-input"
                          />
                        </div>

                        {/* Max Position Size */}
                        <div className="space-y-2">
                          <Label htmlFor="max-position">Max Position Size % of Bankroll</Label>
                          <Input
                            id="max-position"
                            type="number"
                            step="0.01"
                            value={editedModel.rules?.max_position_size_pct || 0}
                            onChange={(e) => updateRule("max_position_size_pct", parseFloat(e.target.value) || 0)}
                            placeholder="0.05"
                            data-testid="max-position-input"
                          />
                        </div>

                        {/* Lookback Window */}
                        <div className="space-y-2">
                          <Label htmlFor="lookback">Lookback Window (hours)</Label>
                          <Input
                            id="lookback"
                            type="number"
                            value={editedModel.rules?.lookback_window_hours || 0}
                            onChange={(e) => updateRule("lookback_window_hours", parseInt(e.target.value) || 0)}
                            placeholder="24"
                            data-testid="lookback-input"
                          />
                        </div>

                        {/* Min Market Volume */}
                        <div className="space-y-2">
                          <Label htmlFor="min-volume">Min Market Volume ($)</Label>
                          <Input
                            id="min-volume"
                            type="number"
                            value={editedModel.rules?.min_market_volume || 0}
                            onChange={(e) => updateRule("min_market_volume", parseInt(e.target.value) || 0)}
                            placeholder="1000"
                            data-testid="min-volume-input"
                          />
                        </div>
                      </div>

                      {/* Notes */}
                      <div className="space-y-2 mt-4">
                        <Label htmlFor="notes">Notes / Description</Label>
                        <Textarea
                          id="notes"
                          value={editedModel.rules?.notes || ""}
                          onChange={(e) => updateRule("notes", e.target.value)}
                          placeholder="Enter strategy notes..."
                          rows={3}
                          data-testid="notes-input"
                        />
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center justify-between pt-4 border-t border-border">
                      <div className="flex items-center gap-2">
                        {!isNewModel && selectedModel && (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => deleteModel(selectedModel.id)}
                            data-testid="delete-model-btn"
                          >
                            <Trash2 className="w-4 h-4 mr-1" />
                            Delete
                          </Button>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {!isNewModel && (
                          <Button
                            variant="outline"
                            onClick={saveAsNew}
                            disabled={saving}
                            data-testid="save-as-new-btn"
                          >
                            <Copy className="w-4 h-4 mr-1" />
                            Save as New Model
                          </Button>
                        )}
                        <Button
                          onClick={saveModel}
                          disabled={saving}
                          data-testid="save-model-btn"
                        >
                          {saving ? (
                            <>Saving...</>
                          ) : (
                            <>
                              <Save className="w-4 h-4 mr-1" />
                              Save
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <Settings className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Select a model to edit or create a new one</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
