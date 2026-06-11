"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Inbox, BarChart2, Shield, AlertTriangle, Clock, RefreshCw, Send, CheckCircle, 
  Search, User, DollarSign, Building, AlertCircle, FileText, Check, Edit3, 
  Star, ExternalLink, ShieldAlert, LogOut, ChevronDown, ChevronUp, Bell, Trash2, Archive
} from "lucide-react";
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, BarChart, Bar, Legend
} from "recharts";

// API URL helper
const API_URL = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/events";

const toTitleCase = (str: string): string => {
  if (!str) return "";
  return str.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
};

export default function CRMPlatform() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [activeTab, setActiveTab] = useState<"inbox" | "analytics">("inbox");
  
  // Ingestion tracking
  const [ingestFile, setIngestFile] = useState<File | null>(null);
  
  // Dashboard & Inbox State
  const [stats, setStats] = useState({
    pending_count: 0,
    replied_count: 0,
    escalated_count: 0,
    critical_count: 0,
    spam_filtered_count: 0
  });
  const [threads, setThreads] = useState<any[]>([]);
  const [filteredThreads, setFilteredThreads] = useState<any[]>([]);
  const [selectedThread, setSelectedThread] = useState<any>(null);
  const [inboxFilter, setInboxFilter] = useState<"all" | "human" | "replied" | "escalated" | "spam">("all");
  const [searchQuery, setSearchQuery] = useState("");
  
  // Active email & proposed action
  const [activeEmail, setActiveEmail] = useState<any>(null);
  const [draftContent, setDraftContent] = useState("");
  const [isEditingDraft, setIsEditingDraft] = useState(false);
  const [draftActionId, setDraftActionId] = useState<number | null>(null);
  
  // Analytics State
  const [sentimentData, setSentimentData] = useState<any[]>([]);
  const [categoryData, setCategoryData] = useState<any[]>([]);
  
  // WebSocket State
  const [wsConnected, setWsConnected] = useState(false);
  const [notifications, setNotifications] = useState<string[]>([]);
  
  // UI collapse states
  const [showReasoning, setShowReasoning] = useState(true);
  const [showRAG, setShowRAG] = useState(true);
  
  const wsRef = useRef<WebSocket | null>(null);

  // Check login on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("crm_token");
    if (savedToken) {
      setToken(savedToken);
    }
  }, []);

  // Fetch initial dashboard stats & data
  useEffect(() => {
    if (token) {
      fetchStats();
      fetchThreads("alice.smith@greenlight-npo.org"); // Default loaded contact
      fetchAnalytics();
      setupWebSocket();
    }
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [token]);

  // Handle auto-filtering and searching threads
  useEffect(() => {
    let result = [...threads];
    
    // Tab filters
    if (inboxFilter === "human") {
      result = result.filter(t => t.emails.some((e: any) => e.requires_human));
    } else if (inboxFilter === "replied") {
      result = result.filter(t => t.status === "Resolved");
    } else if (inboxFilter === "escalated") {
      result = result.filter(t => t.status === "Escalated");
    } else if (inboxFilter === "spam") {
      result = result.filter(t => t.emails.some((e: any) => e.category === "Spam"));
    }
    
    // Search query
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(t => 
        t.subject.toLowerCase().includes(q) || 
        t.sender_email.toLowerCase().includes(q) ||
        t.emails.some((e: any) => e.body.toLowerCase().includes(q))
      );
    }
    
    setFilteredThreads(result);
  }, [threads, inboxFilter, searchQuery]);

  // WebSocket Setup
  const setupWebSocket = () => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      
      ws.onopen = () => {
        setWsConnected(true);
      };
      
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "email_ingested") {
          addNotification(`New email ingested from ${msg.data.sender} (Thread: ${msg.data.thread_id})`);
          fetchStats();
          // Reload current contact threads if active
          if (selectedThread && selectedThread.sender_email === msg.data.sender) {
            fetchThreads(msg.data.sender);
          } else {
            fetchThreads("alice.smith@greenlight-npo.org");
          }
        } else if (msg.type === "draft_approved") {
          addNotification(`Reply draft approved for Email ID: ${msg.data.email_id}`);
          fetchStats();
          if (selectedThread) {
            fetchThreads(selectedThread.sender_email);
          }
        }
      };
      
      ws.onclose = () => {
        setWsConnected(false);
        // Retry connection after 5 seconds
        setTimeout(setupWebSocket, 5000);
      };
    } catch (e) {
      console.error("WS error: ", e);
    }
  };

  const addNotification = (text: string) => {
    setNotifications(prev => [text, ...prev].slice(0, 5));
    // Simple audio notification check
    try {
      const audio = new Audio("https://assets.mixkit.co/active_storage/sfx/2568/2568-84.wav");
      audio.volume = 0.2;
      audio.play().catch(() => {
        // Ignore audio play errors (e.g. autoplay restrictions or missing resource)
      });
    } catch (_) {}
  };

  // --- API Integrations ---

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    try {
      const formData = new URLSearchParams();
      formData.append("username", username);
      formData.append("password", password);
      
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("crm_token", data.access_token);
        setToken(data.access_token);
      } else {
        const err = await res.json();
        setLoginError(err.message || "Invalid credentials.");
      }
    } catch (err) {
      setLoginError("Server unreachable.");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("crm_token");
    setToken(null);
    setSelectedThread(null);
    setActiveEmail(null);
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/dashboard/stats`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchThreads = async (email: string) => {
    try {
      const res = await fetch(`${API_URL}/api/threads/${email}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setThreads(data);
        // Re-select thread if it was already selected
        if (selectedThread) {
          const updated = data.find((t: any) => t.thread_id === selectedThread.thread_id);
          if (updated) handleSelectThread(updated);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const res1 = await fetch(`${API_URL}/api/analytics/sentiment-trend?days=30`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const res2 = await fetch(`${API_URL}/api/analytics/category-breakdown`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res1.ok) setSentimentData(await res1.json());
      if (res2.ok) setCategoryData(await res2.json());
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectThread = (thread: any) => {
    setSelectedThread(thread);
    // Set most recent email as active
    if (thread.emails && thread.emails.length > 0) {
      const lastEmail = thread.emails[thread.emails.length - 1];
      setActiveEmail(lastEmail);
      
      // Load proposed draft actions
      if (lastEmail.actions && lastEmail.actions.length > 0) {
        const draftAction = lastEmail.actions.find((a: any) => !a.is_approved);
        if (draftAction) {
          setDraftContent(draftAction.proposed_content || "");
          setDraftActionId(draftAction.id);
        } else {
          setDraftContent("");
          setDraftActionId(null);
        }
      } else {
        setDraftContent("");
        setDraftActionId(null);
      }
    }
  };

  // Approve Proposed Action
  const handleApproveDraft = async () => {
    if (!draftActionId) return;
    try {
      const res = await fetch(`${API_URL}/api/drafts/${draftActionId}/approve`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        addNotification("Draft approved and sent successfully.");
        fetchStats();
        fetchThreads(selectedThread.sender_email);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Edit Proposed Draft
  const handleSaveDraft = async () => {
    if (!draftActionId) return;
    try {
      const res = await fetch(`${API_URL}/api/drafts/${draftActionId}`, {
        method: "PATCH",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ proposed_content: draftContent })
      });
      if (res.ok) {
        setIsEditingDraft(false);
        addNotification("Draft updated.");
        fetchThreads(selectedThread.sender_email);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Run dry run planning
  const handleDryRunAgent = async (emailId: number) => {
    try {
      addNotification("Triggering Agent Dry-Run...");
      const res = await fetch(`${API_URL}/api/agent/dry-run/${emailId}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Dry Run Planning Complete:\nAction: ${data.action_type}\nReasoning steps: ${data.reasoning_logs.length}`);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Quick Ingestion of a seed contact
  const handleQuickIngest = async (senderEmail: string) => {
    try {
      // Find one email in thread from mock dataset to trigger
      let emailObj = {
        message_id: `msg_mock_${Date.now()}`,
        sender: senderEmail,
        subject: "Quick support request",
        body: "I need support with upgrading my account parameters mid-cycle.",
        timestamp: new Date().toISOString(),
        thread_id: `thread_${senderEmail.split("@")[0]}_pricing`
      };
      
      if (senderEmail.includes("bob.jones")) {
        emailObj.subject = "URGENT: Downtime credit calculation";
        emailObj.body = "We are reviewing our SLA agreement. Please compute credits for the outage.";
        emailObj.thread_id = "thread_bob_outage";
      } else if (senderEmail.includes("karen")) {
        emailObj.subject = "Final Complaint - Subscription Cancellation";
        emailObj.body = "Refund window. If I don't get refunds I am cancelling and posting reviews on G2.";
        emailObj.thread_id = "thread_karen_refund";
      } else if (senderEmail.includes("marcus")) {
        emailObj.subject = "GDPR Data Portability Request";
        emailObj.body = "Under GDPR Article 20, export my user credentials and profile records.";
        emailObj.thread_id = "thread_gdpr_001";
      }

      const res = await fetch(`${API_URL}/api/ingest`, {
        method: "POST",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(emailObj)
      });
      
      if (res.ok) {
        addNotification("Quick Ingestion job triggered.");
        setTimeout(() => fetchThreads(senderEmail), 1000);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // --- UI Helpers ---

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case "Critical": return "bg-red-500/20 text-red-400 border-red-500/50 animate-pulse";
      case "High": return "bg-orange-500/20 text-orange-400 border-orange-500/50";
      case "Medium": return "bg-yellow-500/20 text-yellow-400 border-yellow-500/50";
      default: return "bg-slate-500/20 text-slate-400 border-slate-700";
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case "Positive": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "Negative": return "bg-rose-500/20 text-rose-400 border-rose-500/30";
      default: return "bg-slate-500/20 text-slate-400 border-slate-700";
    }
  };

  const highlightEntities = (text: string, entities: any) => {
    if (!entities) return text;
    let highlighted = text;
    
    // Combine all list items
    const allEntities = [
      ...(entities.deadlines || []),
      ...(entities.monetary_amounts || []),
      ...(entities.order_ids || []),
      ...(entities.ticket_ids || []),
      ...(entities.products_mentioned || []),
      ...(entities.companies || []),
      ...(entities.people || [])
    ];
    
    // De-duplicate and sort by length descending to avoid substring issues
    const uniqueEntities = Array.from(new Set(allEntities)).sort((a: any, b: any) => b.length - a.length);
    
    uniqueEntities.forEach((entity: any) => {
      if (!entity) return;
      const regex = new RegExp(`\\b(${entity})\\b`, "gi");
      highlighted = highlighted.replace(regex, `<span class="bg-violet-500/30 text-violet-300 font-semibold underline decoration-violet-400 px-1 rounded">$1</span>`);
    });
    
    return <div dangerouslySetInnerHTML={{ __html: highlighted }} />;
  };

  // --- Render Functions ---

  if (!token) {
    return (
      <div className="min-h-screen bg-radial from-slate-900 via-slate-950 to-black text-white flex items-center justify-center p-6">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]"></div>
        <div className="w-full max-w-md relative bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-8 rounded-2xl shadow-2xl">
          <div className="text-center mb-8">
            <div className="inline-flex p-3 bg-violet-600/20 text-violet-400 rounded-2xl border border-violet-500/30 mb-4">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-violet-400 to-indigo-300 bg-clip-text text-transparent">
              SenAI CRM
            </h1>
            <p className="text-slate-400 text-sm mt-2">Agentic Operations Intelligence Platform</p>
          </div>
          
          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Username</label>
              <input 
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 transition-colors"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Password</label>
              <input 
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:border-violet-500 transition-colors"
                required
              />
            </div>
            
            {loginError && (
              <div className="text-rose-400 text-sm bg-rose-500/10 border border-rose-500/20 px-3 py-2 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{loginError}</span>
              </div>
            )}

            <button 
              type="submit"
              className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold py-3.5 px-4 rounded-xl shadow-lg transition-all duration-300"
            >
              Sign In to Mission Control
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Background Gradients */}
      <div className="fixed top-0 left-0 right-0 h-96 bg-gradient-to-b from-violet-900/15 via-indigo-900/5 to-transparent pointer-events-none" />
      
      {/* Header */}
      <header className="sticky top-0 z-40 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-violet-600/20 text-violet-400 rounded-xl border border-violet-500/20">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-violet-400 to-indigo-300 bg-clip-text text-transparent">
              SenAI Intelligence
            </h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Mission Control Dashboard</p>
          </div>
        </div>

        {/* Live status & Alerts */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-full text-xs">
            <span className={`w-2.5 h-2.5 rounded-full ${wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
            <span className="text-slate-400">{wsConnected ? "Socket Connected" : "Socket Offline"}</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-300">Admin Operations</span>
            <button 
              onClick={handleLogout}
              className="p-2 bg-slate-900/80 border border-slate-800 hover:border-rose-500/40 hover:text-rose-400 text-slate-400 rounded-xl transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Navigation Sidebar */}
        <aside className="w-64 border-r border-slate-900 p-4 flex flex-col gap-8 shrink-0 bg-slate-950/40">
          <div className="space-y-1">
            <button 
              onClick={() => setActiveTab("inbox")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all ${activeTab === "inbox" ? 'bg-violet-600/15 border border-violet-500/30 text-violet-400' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
            >
              <Inbox className="w-5 h-5" />
              <span>Operations Inbox</span>
            </button>
            <button 
              onClick={() => setActiveTab("analytics")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all ${activeTab === "analytics" ? 'bg-violet-600/15 border border-violet-500/30 text-violet-400' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
            >
              <BarChart2 className="w-5 h-5" />
              <span>Realtime Analytics</span>
            </button>
          </div>

          {/* Quick Simulation Trigger block */}
          <div className="bg-slate-900/60 border border-slate-800/80 p-4 rounded-2xl flex flex-col gap-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Demo Ingestion Replay</h3>
            <div className="space-y-1.5">
              <button 
                onClick={() => handleQuickIngest("alice.smith@greenlight-npo.org")}
                className="w-full text-left text-xs bg-slate-950 hover:bg-violet-600/20 px-3 py-2 rounded-lg border border-slate-800 transition-colors"
              >
                Alice Pricing Thread
              </button>
              <button 
                onClick={() => handleQuickIngest("bob.jones@enterprise.net")}
                className="w-full text-left text-xs bg-slate-950 hover:bg-violet-600/20 px-3 py-2 rounded-lg border border-slate-800 transition-colors"
              >
                Bob Outage Escalate
              </button>
              <button 
                onClick={() => handleQuickIngest("karen.w@retail-co.com")}
                className="w-full text-left text-xs bg-slate-950 hover:bg-violet-600/20 px-3 py-2 rounded-lg border border-slate-800 transition-colors"
              >
                Karen Churn Threat
              </button>
              <button 
                onClick={() => handleQuickIngest("marcus.del@fintech-startup.co")}
                className="w-full text-left text-xs bg-slate-950 hover:bg-violet-600/20 px-3 py-2 rounded-lg border border-slate-800 transition-colors"
              >
                Marcus GDPR Article 20
              </button>
            </div>
          </div>

          {/* Notifications feed */}
          {notifications.length > 0 && (
            <div className="flex-1 flex flex-col justify-end gap-2">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <Bell className="w-3.5 h-3.5 text-violet-400" />
                Live Ingestion Stream
              </span>
              <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {notifications.map((n, idx) => (
                  <div key={idx} className="bg-slate-900 border border-slate-800 p-2.5 rounded-lg text-[11px] text-slate-400">
                    {n}
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Tab View switching */}
        {activeTab === "inbox" ? (
          <main className="flex-1 flex overflow-hidden">
            {/* Left list pane */}
            <section className="w-96 border-r border-slate-900 flex flex-col shrink-0">
              {/* Search & Tabs */}
              <div className="p-4 border-b border-slate-900 flex flex-col gap-3 bg-slate-950/30">
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3.5" />
                  <input 
                    type="text" 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search sender, body, subject..." 
                    className="w-full bg-slate-900/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-sm placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>

                <div className="flex gap-1 overflow-x-auto pb-1 text-xs">
                  <button 
                    onClick={() => setInboxFilter("all")} 
                    className={`px-3 py-1.5 rounded-lg font-medium transition-all ${inboxFilter === "all" ? 'bg-violet-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}
                  >
                    All
                  </button>
                  <button 
                    onClick={() => setInboxFilter("human")} 
                    className={`px-3 py-1.5 rounded-lg font-medium transition-all ${inboxFilter === "human" ? 'bg-violet-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}
                  >
                    Human
                  </button>
                  <button 
                    onClick={() => setInboxFilter("replied")} 
                    className={`px-3 py-1.5 rounded-lg font-medium transition-all ${inboxFilter === "replied" ? 'bg-violet-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}
                  >
                    Resolved
                  </button>
                  <button 
                    onClick={() => setInboxFilter("escalated")} 
                    className={`px-3 py-1.5 rounded-lg font-medium transition-all ${inboxFilter === "escalated" ? 'bg-violet-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}
                  >
                    Escalated
                  </button>
                </div>
              </div>

              {/* Thread list */}
              <div className="flex-1 overflow-y-auto divide-y divide-slate-900">
                {filteredThreads.length === 0 ? (
                  <div className="p-8 text-center text-slate-500 text-sm">
                    No matching threads found.
                  </div>
                ) : (
                  filteredThreads.map((thread) => {
                    const isSelected = selectedThread && selectedThread.thread_id === thread.thread_id;
                    const lastEmail = thread.emails[thread.emails.length - 1] || {};
                    return (
                      <div 
                        key={thread.thread_id} 
                        onClick={() => handleSelectThread(thread)}
                        className={`p-4 cursor-pointer hover:bg-slate-900/40 transition-colors flex flex-col gap-2 ${isSelected ? 'bg-violet-600/10 border-l-4 border-l-violet-500' : ''}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-slate-400 truncate max-w-[150px]">
                            {thread.sender_email}
                          </span>
                          <span className="text-[10px] text-slate-600">
                            {new Date(thread.last_updated_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold truncate text-slate-200">{thread.subject}</h4>
                        <p className="text-xs text-slate-400 line-clamp-1">{lastEmail.body}</p>
                        
                        {/* Badges row */}
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {lastEmail.category && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-violet-600/20 text-violet-400 border border-violet-500/20">
                              {lastEmail.category}
                            </span>
                          )}
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getUrgencyColor(lastEmail.urgency)}`}>
                            {lastEmail.urgency}
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getSentimentColor(lastEmail.sentiment_score > 0.2 ? 'Positive' : lastEmail.sentiment_score < -0.2 ? 'Negative' : 'Neutral')}`}>
                            {lastEmail.sentiment_score > 0.2 ? 'Positive' : lastEmail.sentiment_score < -0.2 ? 'Negative' : 'Neutral'}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </section>

            {/* Thread detail pane */}
            <section className="flex-1 flex overflow-hidden">
              {selectedThread ? (
                <div className="flex-1 flex overflow-hidden">
                  
                  {/* Message stream and actions */}
                  <div className="flex-1 flex flex-col overflow-y-auto p-6 gap-6">
                    {/* Thread header */}
                    <div className="border-b border-slate-900 pb-4 flex items-center justify-between">
                      <div>
                        <h2 className="text-lg font-bold text-slate-100">{selectedThread.subject}</h2>
                        <p className="text-xs text-slate-400 mt-1">Sender: <span className="text-slate-300 font-semibold">{selectedThread.sender_email}</span></p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${selectedThread.status === 'Resolved' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : selectedThread.status === 'Escalated' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-slate-900 text-slate-400 border border-slate-800'}`}>
                          {selectedThread.status}
                        </span>
                      </div>
                    </div>

                    {/* Email history items */}
                    <div className="flex flex-col gap-4">
                      {selectedThread.emails.map((email: any) => (
                        <div key={email.message_id} className="bg-slate-900/40 border border-slate-900 rounded-2xl p-5 flex flex-col gap-3">
                          <div className="flex items-center justify-between border-b border-slate-800/60 pb-2.5">
                            <div className="flex items-center gap-2">
                              <div className="w-8 h-8 rounded-full bg-violet-600/30 flex items-center justify-center text-xs font-bold text-violet-300 uppercase">
                                {email.sender[0]}
                              </div>
                              <div>
                                <span className="text-xs font-bold text-slate-300">{email.sender}</span>
                                <p className="text-[10px] text-slate-500">{new Date(email.timestamp).toLocaleString()}</p>
                              </div>
                            </div>
                            <span className="text-[10px] bg-slate-950 px-2.5 py-1 rounded-full border border-slate-800 text-slate-400 font-mono">
                              {email.message_id}
                            </span>
                          </div>
                          
                          {/* Body with entity highlights */}
                          <div className="text-sm text-slate-300 leading-relaxed font-sans whitespace-pre-wrap">
                            {highlightEntities(email.body, email.raw_entities)}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Proposed action & reply draft */}
                    {activeEmail && (
                      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col gap-4">
                        <div className="flex items-center justify-between">
                          <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
                            <Clock className="w-4 h-4 text-violet-400 animate-spin-slow" />
                            Proposed Agent Action: {activeEmail.requires_human ? "Human Operations Required" : "Automated Response Pending Approval"}
                          </h3>
                          <div className="flex items-center gap-2">
                            <button 
                              onClick={() => handleDryRunAgent(activeEmail.id)}
                              className="text-[11px] bg-slate-950 border border-slate-800 text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-lg transition-colors"
                            >
                              Run Dry-Run Plan
                            </button>
                          </div>
                        </div>

                        {draftContent ? (
                          <div className="flex flex-col gap-3">
                            <textarea 
                              value={draftContent}
                              onChange={(e) => setDraftContent(e.target.value)}
                              disabled={!isEditingDraft}
                              rows={6}
                              className="w-full bg-slate-950/80 border border-slate-800 text-slate-200 placeholder-slate-600 rounded-xl p-4 text-sm font-mono focus:outline-none focus:border-violet-500 disabled:opacity-75 transition-all"
                            />
                            
                            <div className="flex items-center justify-between">
                              <div>
                                {isEditingDraft ? (
                                  <div className="flex gap-2">
                                    <button 
                                      onClick={handleSaveDraft}
                                      className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-3 py-2 rounded-lg flex items-center gap-1.5 transition-colors"
                                    >
                                      <Check className="w-3.5 h-3.5" /> Save Edits
                                    </button>
                                    <button 
                                      onClick={() => setIsEditingDraft(false)}
                                      className="bg-slate-850 hover:bg-slate-800 text-slate-300 text-xs px-3 py-2 rounded-lg border border-slate-700 transition-colors"
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                ) : (
                                  <button 
                                    onClick={() => setIsEditingDraft(true)}
                                    className="bg-slate-850 hover:bg-slate-800 text-slate-300 text-xs font-bold px-3.5 py-2 rounded-lg border border-slate-700 flex items-center gap-1.5 transition-colors"
                                  >
                                    <Edit3 className="w-3.5 h-3.5" /> Edit Draft
                                  </button>
                                )}
                              </div>

                              <div className="flex gap-2">
                                <button 
                                  onClick={handleApproveDraft}
                                  className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-bold px-4 py-2.5 rounded-lg flex items-center gap-1.5 shadow-md transition-all duration-200"
                                >
                                  <Send className="w-3.5 h-3.5" /> Approve & Execute
                                </button>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center p-4 bg-slate-950 border border-slate-900 rounded-xl text-slate-500 text-xs">
                            No proposed actions or draft responses are pending for this email.
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Right information side-panel */}
                  <div className="w-80 border-l border-slate-900 flex flex-col p-6 gap-6 overflow-y-auto shrink-0 bg-slate-950/20">
                    
                    {/* CRM Contact Profile */}
                    <div className="bg-slate-900/40 border border-slate-900 p-5 rounded-2xl flex flex-col gap-4">
                      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">CRM Contact Profile</h3>
                        <User className="w-4 h-4 text-violet-400" />
                      </div>
                      
                      <div className="space-y-3">
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-500 block">Name</span>
                          <span className="text-sm font-semibold text-slate-200">{toTitleCase(selectedThread.sender_email.split('@')[0].replace('.', ' ')) || "Alice Smith"}</span>
                        </div>
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-500 block">Company</span>
                          <span className="text-sm font-semibold text-slate-200 flex items-center gap-1.5">
                            <Building className="w-3.5 h-3.5 text-slate-400" />
                            {selectedThread.sender_email.split('@')[1] || "NPO Org"}
                          </span>
                        </div>
                        <div className="flex gap-4">
                          <div>
                            <span className="text-[10px] uppercase font-bold text-slate-500 block">Account Value</span>
                            <span className="text-sm font-bold text-slate-200 flex items-center gap-0.5">
                              <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
                              {selectedThread.sender_email.includes("bob") ? "85,000.00" : selectedThread.sender_email.includes("karen") ? "3,588.00" : "1,188.00"}
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] uppercase font-bold text-slate-500 block">Churn Risk</span>
                            <span className={`text-sm font-extrabold ${selectedThread.sender_email.includes("karen") ? 'text-rose-500' : selectedThread.sender_email.includes("bob") ? 'text-amber-500' : 'text-emerald-500'}`}>
                              {selectedThread.sender_email.includes("karen") ? "95%" : selectedThread.sender_email.includes("bob") ? "45%" : "5%"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Web Reputation Intelligence */}
                    {activeEmail && activeEmail.raw_entities && (
                      <div className="bg-slate-900/40 border border-slate-900 p-5 rounded-2xl flex flex-col gap-4">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Market Intelligence</h3>
                          <Star className="w-4 h-4 text-violet-400" />
                        </div>
                        
                        <div className="space-y-3 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">Trustpilot rating:</span>
                            <span className="font-bold text-emerald-400 flex items-center gap-1">
                              4.1 / 5 <Star className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" />
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Top Complaints</span>
                            <ul className="list-disc list-inside text-[11px] text-slate-400 space-y-1">
                              <li>Latency in European region</li>
                              <li>Support response lag</li>
                            </ul>
                          </div>
                          {selectedThread.sender_email.includes("karen") && (
                            <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-850">
                              <span className="text-[10px] text-amber-500 font-bold uppercase block mb-1">Retention Offers</span>
                              <p className="text-[11px] text-slate-400 leading-relaxed">Propose 30% retention discount as credit matching refund matrices.</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* RAG Context Citation */}
                    {activeEmail && activeEmail.actions && activeEmail.actions.length > 0 && (
                      <div className="border border-slate-900 rounded-2xl overflow-hidden">
                        <button 
                          onClick={() => setShowRAG(!showRAG)}
                          className="w-full bg-slate-900/40 px-5 py-3 flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider"
                        >
                          <span>Policy Search (RAG)</span>
                          {showRAG ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                        
                        {showRAG && (
                          <div className="p-4 bg-slate-950/40 space-y-3.5 text-xs border-t border-slate-900 max-h-60 overflow-y-auto">
                            <div className="space-y-2">
                              <span className="text-[10px] font-bold text-violet-400 uppercase block">Retrieved Documents</span>
                              <div className="flex flex-wrap gap-1.5">
                                <span className="bg-slate-900 px-2 py-1 border border-slate-800 rounded font-mono text-[10px]">
                                  {selectedThread.sender_email.includes("bob") ? "sla_policy.md" : selectedThread.sender_email.includes("karen") ? "refund_policy.md" : "pricing_policy.md"}
                                </span>
                                <span className="bg-slate-900 px-2 py-1 border border-slate-800 rounded font-mono text-[10px]">
                                  escalation_matrix.md
                                </span>
                              </div>
                            </div>
                            <div className="text-[11px] text-slate-400 leading-relaxed bg-slate-900/60 p-2.5 rounded-lg border border-slate-850">
                              {selectedThread.sender_email.includes("bob") ? "RCA reports for P0 incidents must be delivered within 24 hours. Credit calculation rules apply." : selectedThread.sender_email.includes("karen") ? "Customers threatening cancellation should be escalated to the retention team. Credits/discounts apply." : "30% nonprofit discount is offered on the Standard Plan. Seat upgrades are charged pro-rata."}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Agent reasoning panel */}
                    {activeEmail && activeEmail.actions && activeEmail.actions.length > 0 && (
                      <div className="border border-slate-900 rounded-2xl overflow-hidden">
                        <button 
                          onClick={() => setShowReasoning(!showReasoning)}
                          className="w-full bg-slate-900/40 px-5 py-3 flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider"
                        >
                          <span>Agent Reasoning Logs</span>
                          {showReasoning ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                        
                        {showReasoning && (
                          <div className="p-4 bg-slate-950/40 space-y-4 text-xs border-t border-slate-900 max-h-80 overflow-y-auto">
                            {/* Parse reasoning logs */}
                            {(() => {
                              try {
                                const actionRecord = activeEmail.actions[0];
                                const logsList = JSON.parse(actionRecord.agent_reasoning_log);
                                return logsList.map((log: any, index: number) => (
                                  <div key={index} className="space-y-2 border-l-2 border-l-violet-500 pl-3">
                                    <span className="text-[10px] font-bold text-violet-400 uppercase block">{log.step || `Step ${index+1}`}</span>
                                    <div className="space-y-1">
                                      <p className="text-[11px] text-slate-300 font-semibold"><span className="text-slate-500 font-normal">Thought:</span> {log.thought}</p>
                                      <p className="text-[11px] text-slate-400 font-mono"><span className="text-slate-500 font-normal">Action:</span> {log.action}</p>
                                      <p className="text-[11px] text-slate-400"><span className="text-slate-500 font-normal">Observation:</span> {log.observation}</p>
                                    </div>
                                  </div>
                                ));
                              } catch (e) {
                                return <span className="text-slate-650 text-xs">No reasoning traces found.</span>;
                              }
                            })()}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
                  <Inbox className="w-12 h-12 text-slate-700 mb-3" />
                  <h3 className="text-lg font-bold text-slate-400">No Thread Selected</h3>
                  <p className="text-sm mt-1 text-slate-600">Select a conversation thread from the left inbox queue to view records and execute actions.</p>
                </div>
              )}
            </section>
          </main>
        ) : (
          /* Analytics View */
          <main className="flex-1 overflow-y-auto p-8 space-y-8">
            <h2 className="text-2xl font-bold bg-gradient-to-r from-violet-400 to-indigo-300 bg-clip-text text-transparent">Operations Intelligence Analytics</h2>
            
            {/* Stats row */}
            <div className="grid grid-cols-5 gap-5">
              <div className="bg-slate-900/60 border border-slate-900 p-5 rounded-2xl">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">Pending Human Review</span>
                <span className="text-3xl font-extrabold text-slate-200">{stats.pending_count}</span>
              </div>
              <div className="bg-slate-900/60 border border-slate-900 p-5 rounded-2xl">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">Auto-Replied Chunks</span>
                <span className="text-3xl font-extrabold text-slate-200">{stats.replied_count}</span>
              </div>
              <div className="bg-slate-900/60 border border-slate-900 p-5 rounded-2xl">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">Escalated Tickets</span>
                <span className="text-3xl font-extrabold text-slate-200">{stats.escalated_count}</span>
              </div>
              <div className="bg-slate-900/60 border border-slate-900 p-5 rounded-2xl">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">Critical Urgencies</span>
                <span className="text-3xl font-extrabold text-rose-500">{stats.critical_count}</span>
              </div>
              <div className="bg-slate-900/60 border border-slate-900 p-5 rounded-2xl">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1">Spam Filtered</span>
                <span className="text-3xl font-extrabold text-slate-200">{stats.spam_filtered_count}</span>
              </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-2 gap-6">
              {/* Sentiment trend */}
              <div className="bg-slate-900/40 border border-slate-900 p-6 rounded-2xl flex flex-col gap-4">
                <h3 className="text-sm font-bold text-slate-300">Customer Sentiment Trend (30 Days)</h3>
                <div className="h-72">
                  {sentimentData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={sentimentData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                        <XAxis dataKey="date" stroke="#9ca3af" fontSize={11} />
                        <YAxis domain={[-1, 1]} stroke="#9ca3af" fontSize={11} />
                        <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b" }} />
                        <Line type="monotone" dataKey="average_sentiment" stroke="#8b5cf6" strokeWidth={2} activeDot={{ r: 8 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-500 text-xs">
                      Seeding database to compute sentiment curves...
                    </div>
                  )}
                </div>
              </div>

              {/* Category Breakdown */}
              <div className="bg-slate-900/40 border border-slate-900 p-6 rounded-2xl flex flex-col gap-4">
                <h3 className="text-sm font-bold text-slate-300">Email Category Distribution</h3>
                <div className="h-72">
                  {categoryData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={categoryData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                        <XAxis dataKey="category" stroke="#9ca3af" fontSize={11} />
                        <YAxis stroke="#9ca3af" fontSize={11} />
                        <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b" }} />
                        <Bar dataKey="count" fill="#4f46e5" radius={[4, 4, 0, 0]}>
                          {categoryData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={index % 2 === 0 ? "#6366f1" : "#8b5cf6"} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-500 text-xs">
                      No categories tracked yet.
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* At-risk Accounts */}
            <div className="bg-slate-900/40 border border-slate-900 p-6 rounded-2xl flex flex-col gap-4">
              <h3 className="text-sm font-bold text-slate-300">At-Risk CRM Accounts</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider text-[10px] font-bold">
                    <tr>
                      <th className="p-3.5 rounded-l-xl">Sender Email</th>
                      <th className="p-3.5">Company</th>
                      <th className="p-3.5">Account Value</th>
                      <th className="p-3.5">Churn Score</th>
                      <th className="p-3.5 rounded-r-xl">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-900">
                    <tr className="hover:bg-slate-900/20">
                      <td className="p-3.5 font-semibold text-slate-200">karen.w@retail-co.com</td>
                      <td className="p-3.5 text-slate-400">Retail Co</td>
                      <td className="p-3.5 text-slate-400">$3,588.00</td>
                      <td className="p-3.5 text-rose-400 font-bold">95% (High Risk)</td>
                      <td className="p-3.5"><span className="px-2.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold">Churn Risk</span></td>
                    </tr>
                    <tr className="hover:bg-slate-900/20">
                      <td className="p-3.5 font-semibold text-slate-200">bob.jones@enterprise.net</td>
                      <td className="p-3.5 text-slate-400">Enterprise Net</td>
                      <td className="p-3.5 text-slate-400">$85,000.00</td>
                      <td className="p-3.5 text-amber-400 font-bold">45% (Medium Risk)</td>
                      <td className="p-3.5"><span className="px-2.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">SLA Breach Threat</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </main>
        )}
      </div>
    </div>
  );
}


