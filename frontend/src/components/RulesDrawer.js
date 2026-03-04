import React, { useState, useEffect, useCallback } from "react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "../components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import {
  Settings,
  FileText,
  History,
  RotateCcw,
  ChevronRight,
  Copy,
  Check
} from "lucide-react";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Rule Chips Component (for model cards)
export const RuleChips = ({ chips, maxDisplay = 7 }) => {
  if (!chips || chips.length === 0) return null;
  
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {chips.slice(0, maxDisplay).map((chip, idx) => (
        <div
          key={idx}
          className="px-2 py-0.5 bg-muted/50 border border-border rounded text-xs"
          title={chip.param}
        >
          <span className="text-muted-foreground">{chip.label}:</span>{" "}
          <span className="font-medium">{chip.value}</span>
        </div>
      ))}
    </div>
  );
};

// Full Rules Drawer
export const RulesDrawer = ({ strategyId, displayName, league = "BASE" }) => {
  const [rulesData, setRulesData] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState("summary");
  
  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/rules/${strategyId}?league=${league}`);
      if (res.ok) {
        const data = await res.json();
        setRulesData(data);
      }
    } catch (err) {
      console.error("Failed to fetch rules:", err);
    } finally {
      setLoading(false);
    }
  }, [strategyId, league]);
  
  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rules/${strategyId}/history?league=${league}&limit=10`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data.versions || []);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    }
  }, [strategyId, league]);

  useEffect(() => {
    if (strategyId) {
      fetchRules();
      fetchHistory();
    }
  }, [strategyId, league, fetchRules, fetchHistory]);
  
  const handleRollback = async (targetVersionId) => {
    if (!window.confirm(`Rollback to ${targetVersionId}? This will create a new version.`)) {
      return;
    }
    
    try {
      const res = await fetch(
        `${API_BASE}/api/rules/${strategyId}/rollback?league=${league}&target_version_id=${targetVersionId}`,
        { method: "POST" }
      );
      
      if (res.ok) {
        fetchRules();
        fetchHistory();
      }
    } catch (err) {
      console.error("Failed to rollback:", err);
    }
  };
  
  const copyJson = () => {
    if (rulesData?.config) {
      navigator.clipboard.writeText(JSON.stringify(rulesData.config, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="text-xs">
          <Settings className="w-3 h-3 mr-1" />
          View Rules
        </Button>
      </SheetTrigger>
      <SheetContent className="w-[600px] sm:max-w-[600px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{displayName} Rules</SheetTitle>
          <SheetDescription>
            Config Version: <span className="font-mono text-foreground">{rulesData?.version_id || "N/A"}</span>
            {rulesData?.applied_at && (
              <span className="ml-2 text-xs text-muted-foreground">
                Updated: {new Date(rulesData.applied_at).toLocaleString()}
              </span>
            )}
          </SheetDescription>
        </SheetHeader>
        
        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="summary" className="text-xs">
              <FileText className="w-3 h-3 mr-1" />
              Summary
            </TabsTrigger>
            <TabsTrigger value="json" className="text-xs">
              <Settings className="w-3 h-3 mr-1" />
              JSON
            </TabsTrigger>
            <TabsTrigger value="history" className="text-xs">
              <History className="w-3 h-3 mr-1" />
              History
            </TabsTrigger>
          </TabsList>
          
          {/* Summary Tab */}
          <TabsContent value="summary" className="mt-4">
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">Loading...</div>
            ) : rulesData?.rules_summary ? (
              <div className="prose prose-sm prose-invert max-w-none">
                <div className="whitespace-pre-wrap text-sm font-mono bg-muted/30 p-4 rounded-lg overflow-x-auto">
                  {rulesData.rules_summary}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">No summary available</div>
            )}
          </TabsContent>
          
          {/* JSON Tab */}
          <TabsContent value="json" className="mt-4">
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="absolute top-2 right-2 z-10"
                onClick={copyJson}
              >
                {copied ? (
                  <Check className="w-4 h-4 text-green-400" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </Button>
              <pre className="bg-muted/30 p-4 rounded-lg overflow-x-auto text-xs font-mono max-h-[500px] overflow-y-auto">
                {rulesData?.config ? JSON.stringify(rulesData.config, null, 2) : "No config"}
              </pre>
            </div>
          </TabsContent>
          
          {/* History Tab */}
          <TabsContent value="history" className="mt-4">
            {history.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">No history available</div>
            ) : (
              <div className="space-y-3">
                {history.map((version, idx) => (
                  <div
                    key={version.version_id}
                    className={`p-3 rounded-lg border ${
                      version.is_active ? "bg-green-500/10 border-green-500/30" : "bg-muted/20 border-border"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-mono text-sm">{version.version_id}</span>
                        {version.is_active && (
                          <Badge variant="default" className="ml-2 text-xs">Active</Badge>
                        )}
                      </div>
                      {!version.is_active && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRollback(version.version_id)}
                          className="text-xs"
                        >
                          <RotateCcw className="w-3 h-3 mr-1" />
                          Rollback
                        </Button>
                      )}
                    </div>
                    
                    <div className="mt-1 text-xs text-muted-foreground">
                      <span>By: {version.applied_by}</span>
                      <span className="mx-2">•</span>
                      <span>{new Date(version.created_at).toLocaleString()}</span>
                    </div>
                    
                    {version.change_summary && (
                      <p className="mt-1 text-xs">{version.change_summary}</p>
                    )}
                    
                    {/* Diff */}
                    {version.diff && version.diff.length > 0 && (
                      <div className="mt-2 text-xs">
                        <details>
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            View changes ({version.diff.length})
                          </summary>
                          <div className="mt-2 space-y-1 pl-2 border-l-2 border-border">
                            {version.diff.map((d, i) => (
                              <div key={i} className="font-mono">
                                <span className="text-muted-foreground">{d.parameter}:</span>{" "}
                                <span className="text-red-400">{JSON.stringify(d.old)}</span>
                                <ChevronRight className="w-3 h-3 inline mx-1" />
                                <span className="text-green-400">{JSON.stringify(d.new)}</span>
                              </div>
                            ))}
                          </div>
                        </details>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
};

export default RulesDrawer;
