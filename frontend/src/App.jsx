import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare, Bot, ShieldCheck, FileText, KeyRound, Store,
  RefreshCw, Send, Sparkles, AlertTriangle, CheckCircle2, XCircle,
  ChevronRight, Lock, ArrowRight, Search, Zap, Package, TrendingDown,
  Activity, Hash, Shield
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────────
   DESIGN TOKENS  (warm earth palette)
   bg-[#FAF8F5]  : alabaster page background
   bg-[#FFFFFF]  : card surface
   bg-[#F5F1EB]  : inset / secondary surface
   text-[#2C1F14]: espresso-brown heading
   text-[#6B5744]: warm taupe body
   text-[#9C836E]: muted caption
   accent orange : #C97941  (terracotta)
   accent hover  : #A8622E
   border        : #E8E0D5  (sand-100)
   success green : #4D7C5F
   error red     : #B84040
───────────────────────────────────────────────────────────── */

// ─── Reusable primitives ──────────────────────────────────────

const Badge = ({ children, variant = 'neutral', className = '' }) => {
  const variants = {
    neutral:  'bg-[#F5F1EB] text-[#6B5744] border-[#E8E0D5]',
    success:  'bg-[#EBF4EE] text-[#4D7C5F] border-[#C3DBC9]',
    error:    'bg-[#FAEAEA] text-[#B84040] border-[#F0C4C4]',
    gold:     'bg-[#FDF4E8] text-[#A8622E] border-[#F2D9B5]',
    blue:     'bg-[#EEF3FA] text-[#3B6EA8] border-[#C5D9EF]',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-semibold rounded-full border tracking-wide ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Card = ({ children, className = '' }) => (
  <div className={`bg-white border border-[#E8E0D5] rounded-2xl shadow-[0_2px_12px_rgba(44,31,20,0.06)] ${className}`}>
    {children}
  </div>
);

const SectionLabel = ({ children, className = '' }) => (
  <p className={`text-[11px] font-semibold uppercase tracking-widest text-[#9C836E] ${className}`}>{children}</p>
);

// ─── Markdown-lite renderer ──────────────────────────────────
const RenderText = ({ text }) => {
  if (!text) return null;
  const lines = text.split('\n');
  return (
    <div className="space-y-1 text-sm leading-relaxed text-[#3D2B1A]">
      {lines.map((line, i) => {
        const bold = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        const italic = bold.replace(/\*(.*?)\*/g, '<em>$1</em>');
        const code = italic.replace(/`(.*?)`/g, '<code class="font-mono bg-[#F5F1EB] px-1 rounded text-[#A8622E] text-xs">$1</code>');
        const strike = code.replace(/~~(.*?)~~/g, '<span class="line-through text-[#9C836E]">$1</span>');
        const rupee = strike.replace(/₹/g, '<span class="font-semibold">₹</span>');
        return (
          <p key={i} className={line.trim() === '' ? 'h-2' : ''} dangerouslySetInnerHTML={{ __html: rupee }} />
        );
      })}
    </div>
  );
};

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [merchant, setMerchant] = useState('merchant_a');
  const [chatMessages, setChatMessages] = useState([{
    id: 1, role: 'assistant',
    text: "👋 Welcome to **Apex Outfitters**. I'm your AI Commerce Agent — powered by function calling and a deterministic Policy Gate.\n\nTry a natural request like *'I want to buy the Apex Torrent Jacket in size M'* or pick a demo scenario on the right.",
    product_preview: null, policy_result: null, receipt: null
  }]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const [verifyOrderId, setVerifyOrderId] = useState('');
  const [verifyResult, setVerifyResult] = useState(null);
  const [tamperSimulated, setTamperSimulated] = useState(false);
  const [productsA, setProductsA] = useState([]);
  const [productsB, setProductsB] = useState([]);
  const [agentStep, setAgentStep] = useState(0);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentResults, setAgentResults] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);
  useEffect(() => { fetchCatalogs(); fetchLogs(); }, []);

  const fetchCatalogs = async () => {
    try {
      const [rA, rB] = await Promise.all([
        fetch('/api/products/search?merchant_id=merchant_a'),
        fetch('/api/products/search?merchant_id=merchant_b')
      ]);
      setProductsA(await rA.json() || []);
      setProductsB(await rB.json() || []);
    } catch (e) { console.error(e); }
  };

  const fetchLogs = async () => {
    try {
      const r = await fetch('/api/logs?limit=50');
      setAuditLogs(await r.json() || []);
    } catch (e) { console.error(e); }
  };

  const handleSendMessage = async (msgText = inputMessage) => {
    if (!msgText.trim() || isLoading) return;
    setChatMessages(prev => [...prev, { id: Date.now(), role: 'user', text: msgText }]);
    setInputMessage('');
    setIsLoading(true);
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msgText, merchant_id: merchant, session_id: 'web_session_demo' })
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, {
        id: Date.now() + 1, role: 'assistant',
        text: data.reply, product_preview: data.product_preview,
        policy_result: data.policy_result, receipt: data.receipt,
        tool_invoked: data.tool_invoked
      }]);
      if (data.receipt) setVerifyOrderId(data.receipt.order_id);
      fetchLogs(); fetchCatalogs();
    } catch {
      setChatMessages(prev => [...prev, {
        id: Date.now() + 1, role: 'assistant',
        text: '⚠️ Could not reach the agent backend. Make sure the server is running on port 8000.'
      }]);
    } finally { setIsLoading(false); }
  };

  const handleResetDemo = async () => {
    try {
      await fetch('/api/reset-demo', { method: 'POST' });
      fetchCatalogs(); fetchLogs();
      setChatMessages([{ id: Date.now(), role: 'assistant', text: '🔄 Demo reset. Inventory and session cleared. Ready for a fresh run.' }]);
    } catch (e) { console.error(e); }
  };

  const handleVerifyReceipt = async (orderId = verifyOrderId, forceTamper = false) => {
    if (!orderId.trim()) return;
    try {
      const res = await fetch(`/api/verify/${orderId.trim()}`);
      if (!res.ok) { setVerifyResult({ proof: { verified: false }, error: 'Order not found.' }); return; }
      const data = await res.json();
      if (forceTamper) {
        setVerifyResult({ ...data, proof: { ...data.proof, verified: false, tamper_detected: true, recomputed_hash: 'malicious_e891c3f9a23b0928a47b_FORGED', signature_valid: false } });
        setTamperSimulated(true);
      } else {
        setVerifyResult(data); setTamperSimulated(false);
      }
    } catch { setVerifyResult({ proof: { verified: false }, error: 'Network error.' }); }
  };

  const runAutonomousBuyerSimulation = async () => {
    setAgentRunning(true); setAgentStep(1); setAgentResults(null);
    for (let s = 2; s <= 5; s++) { await new Promise(r => setTimeout(r, 1300 + s * 100)); setAgentStep(s); }
    try {
      const res = await fetch('/api/orders/mandate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mandate_id: `mandate_ui_${Date.now().toString().slice(-6)}`,
          buyer_id: 'cust_001', merchant_id: 'merchant_b',
          product_id: 'URB-JKT-001', product_name: 'Urban Shield Waterproof Raincoat',
          variant: 'M', quantity: 1, currency: 'INR',
          max_price_limit: 2000.0, agreed_unit_price: 1709.10, total_authorized_amount: 1709.10,
          shipping_address: { name: 'Rahul Sharma', street: '402, Green Glen Layout, Bellandur', city: 'Bengaluru', state: 'Karnataka', postal_code: '560103', country: 'India' },
          mandate_signature: 'hmac_sha256_sig_39f029bc8172ea91...',
          expiry_timestamp: new Date(Date.now() + 15 * 60000).toISOString()
        })
      });
      setAgentResults(await res.json());
      setAgentStep(6); fetchLogs(); fetchCatalogs();
    } catch (e) { console.error(e); } finally { setAgentRunning(false); }
  };

  // ─── NAV TABS ─────────────────────────────────────────────
  const tabs = [
    { id: 'chat',           icon: MessageSquare, label: 'Checkout',   shortLabel: 'Chat'   },
    { id: 'buyer_agent',    icon: Bot,           label: 'AI Agent',   shortLabel: 'Agent'  },
    { id: 'catalogs',       icon: Store,         label: 'Catalog',    shortLabel: 'Catalog'},
    { id: 'audit',          icon: FileText,      label: 'Audit Trail',shortLabel: 'Audit'  },
    { id: 'receipt_verify', icon: KeyRound,      label: 'Verify Proof',shortLabel: 'Verify'},
  ];

  const DEMO_SCENARIOS = [
    { label: 'Standard In-Stock Order',      tag: 'APPROVED',  tagColor: 'success', prompt: 'I want to buy the Apex Torrent Waterproof Shell in size M',           desc: 'All 6 policy checks pass → Razorpay payment captured.' },
    { label: 'Out-of-Stock Failure',         tag: 'REJECTED',  tagColor: 'error',   prompt: 'Can you check stock and buy the Apex Alpine Pro Shell in size L?',    desc: 'Stock = 0 → Policy Gate rejects, agent suggests Size M.' },
    { label: 'Bounded Discount Negotiation', tag: 'COUNTER',   tagColor: 'gold',    prompt: 'Can I get a 10% discount on the Apex Torrent Shell?',                 desc: 'Agent negotiates within 15% merchant cap.' },
    { label: 'Quantity Cap Rejection',       tag: '>5 UNITS',  tagColor: 'error',   prompt: 'I want to order 20 units of the Apex Torrent Jacket',                 desc: 'Policy Gate enforces 5-unit ceiling.' },
    { label: 'High-Value Cap Rejection',     tag: '>₹10K',     tagColor: 'error',   prompt: 'Order the Apex Expedition 8000 Parka',                                desc: '₹14,999 item exceeds ₹10,000 auto-order limit.' },
  ];

  // ─── RENDER ──────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#FAF8F5] text-[#2C1F14] flex flex-col font-sans antialiased selection:bg-[#C97941]/20">

      {/* ── TOPNAV ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-[#E8E0D5] shadow-[0_1px_8px_rgba(44,31,20,0.06)]">
        <div className="max-w-[1380px] mx-auto px-5 h-[60px] flex items-center justify-between gap-4">

          {/* Logo */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#C97941] to-[#8C4E1F] flex items-center justify-center shadow-sm">
              <span className="font-bold text-white text-base leading-none">R</span>
            </div>
            <div className="hidden sm:block">
              <div className="flex items-center gap-2">
                <span className="font-bold text-[15px] text-[#2C1F14] tracking-tight">Razorpay</span>
                <span className="font-light text-[15px] text-[#C97941]">Agentic Commerce</span>
              </div>
              <p className="text-[10px] text-[#9C836E] leading-none mt-0.5">Track 1 · AP2 Protocol · Policy Gate</p>
            </div>
          </div>

          {/* Tab nav */}
          <nav className="flex items-center gap-0.5 bg-[#F5F1EB] p-1 rounded-xl border border-[#E8E0D5]">
            {tabs.map(({ id, icon: Icon, label, shortLabel }) => (
              <button
                key={id}
                onClick={() => { setActiveTab(id); if (id === 'audit') fetchLogs(); }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 whitespace-nowrap
                  ${activeTab === id
                    ? 'bg-white text-[#C97941] shadow-[0_1px_4px_rgba(44,31,20,0.1)] border border-[#E8E0D5]'
                    : 'text-[#6B5744] hover:text-[#2C1F14] hover:bg-white/60'
                  }`}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                <span className="hidden md:inline">{label}</span>
                <span className="md:hidden">{shortLabel}</span>
              </button>
            ))}
          </nav>

          {/* Actions */}
          <button
            onClick={handleResetDemo}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#6B5744] bg-[#F5F1EB] hover:bg-[#EDE6DC] border border-[#E8E0D5] rounded-lg transition-colors shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Reset Demo</span>
          </button>
        </div>
      </header>

      {/* ── PAGE CONTENT ────────────────────────────────────── */}
      <main className="flex-1 max-w-[1380px] w-full mx-auto px-5 py-6">

        {/* ════════════════════════════════════════════
            TAB 1 — CONVERSATIONAL CHECKOUT
        ════════════════════════════════════════════ */}
        {activeTab === 'chat' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start min-h-[680px]">

            {/* ── Chat panel ── */}
            <div className="lg:col-span-8 flex flex-col bg-white border border-[#E8E0D5] rounded-2xl shadow-[0_2px_16px_rgba(44,31,20,0.07)] overflow-hidden" style={{ minHeight: 600 }}>

              {/* Chat header */}
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#F0E9DF] bg-[#FAF8F5]">
                <div className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full bg-[#4D7C5F] animate-pulse" />
                  <div>
                    <p className="text-sm font-semibold text-[#2C1F14]">
                      {merchant === 'merchant_a' ? 'Apex Outfitters' : 'Urban Trail Co.'}
                    </p>
                    <p className="text-[11px] text-[#9C836E]">AI Agent + Policy Gate</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[#9C836E]">Store:</span>
                  <select
                    value={merchant}
                    onChange={(e) => setMerchant(e.target.value)}
                    className="text-xs font-medium text-[#2C1F14] bg-white border border-[#E8E0D5] rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#C97941]/30 cursor-pointer"
                  >
                    <option value="merchant_a">Apex Outfitters (Gear)</option>
                    <option value="merchant_b">Urban Trail Co. (City)</option>
                  </select>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4" style={{ minHeight: 0 }}>
                {chatMessages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] sm:max-w-[76%] rounded-2xl px-4 py-3 text-sm shadow-sm
                      ${msg.role === 'user'
                        ? 'bg-[#C97941] text-white rounded-br-sm'
                        : 'bg-[#FAF8F5] text-[#2C1F14] border border-[#E8E0D5] rounded-bl-sm'
                      }`}>

                      {/* Tool badge */}
                      {msg.tool_invoked && (
                        <div className="inline-flex items-center gap-1 mb-2 px-2 py-0.5 bg-white border border-[#E8E0D5] rounded-md text-[10px] font-mono text-[#A8622E]">
                          <Zap className="w-2.5 h-2.5 text-[#C97941]" />
                          {msg.tool_invoked}()
                        </div>
                      )}

                      {msg.role === 'user'
                        ? <p className="text-sm leading-relaxed">{msg.text}</p>
                        : <RenderText text={msg.text} />
                      }

                      {/* Product card */}
                      {msg.product_preview && (
                        <div className="mt-3 p-3 bg-white rounded-xl border border-[#E8E0D5] flex gap-3 items-center">
                          <img src={msg.product_preview.image_url} alt={msg.product_preview.name}
                            className="w-14 h-14 rounded-lg object-cover bg-[#F5F1EB] shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <h4 className="text-xs font-semibold text-[#2C1F14] truncate">{msg.product_preview.name}</h4>
                              <Badge variant="neutral">{msg.product_preview.variant}</Badge>
                            </div>
                            <p className="text-[11px] text-[#9C836E] mt-0.5 line-clamp-1">{msg.product_preview.description}</p>
                            <div className="flex items-center justify-between mt-2">
                              <span className="text-sm font-bold text-[#C97941]">₹{msg.product_preview.price.toLocaleString('en-IN')}</span>
                              <Badge variant={msg.product_preview.stock_count > 0 ? 'success' : 'error'}>
                                {msg.product_preview.stock_count > 0 ? `${msg.product_preview.stock_count} in stock` : 'Out of Stock'}
                              </Badge>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Policy Gate checklist */}
                      {msg.policy_result && (
                        <div className="mt-3 p-3 bg-white rounded-xl border border-[#E8E0D5]">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-1.5">
                              <Shield className="w-3.5 h-3.5 text-[#C97941]" />
                              <SectionLabel>Policy Gate</SectionLabel>
                            </div>
                            <Badge variant={msg.policy_result.status === 'APPROVED' ? 'success' : 'error'}>
                              {msg.policy_result.status}
                            </Badge>
                          </div>
                          <div className="space-y-1.5">
                            {msg.policy_result.checks?.map((check, i) => (
                              <div key={i} className="flex items-start gap-1.5 text-[11px]">
                                {check.passed
                                  ? <CheckCircle2 className="w-3.5 h-3.5 text-[#4D7C5F] shrink-0 mt-0.5" />
                                  : <XCircle className="w-3.5 h-3.5 text-[#B84040] shrink-0 mt-0.5" />
                                }
                                <span className={check.passed ? 'text-[#6B5744]' : 'text-[#B84040] font-medium'}>
                                  <strong>{check.name}:</strong> {check.detail}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Receipt card */}
                      {msg.receipt && (
                        <div className="mt-3 p-3 bg-[#EBF4EE] rounded-xl border border-[#C3DBC9]">
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-1.5 text-[#4D7C5F]">
                              <Lock className="w-3.5 h-3.5" />
                              <span className="text-[11px] font-semibold">Verifiable Receipt</span>
                            </div>
                            <span className="text-[10px] font-mono text-[#6B5744]">{msg.receipt.order_id}</span>
                          </div>
                          <p className="text-[11px] text-[#4D7C5F]">Signed with HMAC-SHA256 · Proof stored in MongoDB.</p>
                          <div className="mt-2 pt-2 border-t border-[#C3DBC9] flex items-center justify-between text-[11px]">
                            <span className="font-mono text-[#6B5744] truncate max-w-[170px]">
                              {msg.receipt.receipt_hash.slice(0, 20)}…
                            </span>
                            <button
                              onClick={() => { setVerifyOrderId(msg.receipt.order_id); setActiveTab('receipt_verify'); handleVerifyReceipt(msg.receipt.order_id); }}
                              className="flex items-center gap-0.5 text-[#4D7C5F] font-semibold hover:underline"
                            >
                              Verify <ChevronRight className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {/* Loading */}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="flex items-center gap-2.5 bg-[#FAF8F5] border border-[#E8E0D5] rounded-2xl rounded-bl-sm px-4 py-3 text-xs text-[#9C836E]">
                      <span className="flex gap-1">
                        {[0,1,2].map(i => (
                          <span key={i} className="w-1.5 h-1.5 rounded-full bg-[#C97941] animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                        ))}
                      </span>
                      Agent analyzing intent and running catalog tools…
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input bar */}
              <div className="px-4 py-3.5 border-t border-[#F0E9DF] bg-[#FAF8F5]">
                <form
                  onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}
                  className="flex items-center gap-2"
                >
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    placeholder="e.g. 'I want to buy the Apex Torrent Jacket in size M'…"
                    className="flex-1 bg-white border border-[#E8E0D5] rounded-xl px-4 py-2.5 text-sm text-[#2C1F14] placeholder-[#BCA99A] focus:outline-none focus:ring-2 focus:ring-[#C97941]/30 focus:border-[#C97941] transition-shadow"
                  />
                  <button
                    type="submit"
                    disabled={isLoading || !inputMessage.trim()}
                    className="p-2.5 bg-[#C97941] hover:bg-[#A8622E] disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl transition-colors shadow-sm shrink-0"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            </div>

            {/* ── Right sidebar ── */}
            <div className="lg:col-span-4 space-y-4">

              {/* Demo scenarios */}
              <Card className="p-5">
                <div className="flex items-center gap-2 mb-1">
                  <Sparkles className="w-4 h-4 text-[#C97941]" />
                  <h3 className="text-sm font-semibold text-[#2C1F14]">Demo Scenarios</h3>
                </div>
                <p className="text-[11px] text-[#9C836E] mb-4">Click any scenario to send it directly to the agent.</p>

                <div className="space-y-2">
                  {DEMO_SCENARIOS.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => handleSendMessage(s.prompt)}
                      className="w-full text-left p-3.5 rounded-xl border border-[#E8E0D5] hover:border-[#C97941]/40 hover:bg-[#FDF8F3] bg-[#FAF8F5] transition-all group"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold text-[#2C1F14] group-hover:text-[#C97941] transition-colors">{s.label}</span>
                        <div className="flex items-center gap-1.5">
                          <Badge variant={s.tagColor}>{s.tag}</Badge>
                          <ChevronRight className="w-3 h-3 text-[#BCA99A] group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </div>
                      <p className="text-[11px] text-[#9C836E]">{s.desc}</p>
                    </button>
                  ))}
                </div>
              </Card>

              {/* Policy guardrails */}
              <Card className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <ShieldCheck className="w-4 h-4 text-[#4D7C5F]" />
                  <h3 className="text-sm font-semibold text-[#2C1F14]">Policy Guardrails</h3>
                </div>
                <div className="space-y-0 divide-y divide-[#F0E9DF]">
                  {[
                    { label: 'Price Integrity', value: 'Catalog Override' },
                    { label: 'Max Quantity', value: '5 units / order' },
                    { label: 'Max Order Value', value: '₹10,000' },
                    { label: 'Discount Range', value: '5% – 15%' },
                    { label: 'Address Check', value: 'Saved Profile Only' },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex items-center justify-between py-2 text-xs">
                      <span className="text-[#9C836E]">{label}</span>
                      <span className="font-semibold text-[#2C1F14]">{value}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════
            TAB 2 — AUTONOMOUS AI BUYER AGENT
        ════════════════════════════════════════════ */}
        {activeTab === 'buyer_agent' && (
          <div className="space-y-6 max-w-5xl mx-auto">

            {/* Hero */}
            <Card className="p-6 bg-gradient-to-br from-[#FDF4E8] to-[#FAF8F5] border-[#F2D9B5]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5">
                <div>
                  <Badge variant="gold" className="mb-3">
                    <Bot className="w-3 h-3" /> Autonomous · Zero Human Input
                  </Badge>
                  <h2 className="text-xl font-bold text-[#2C1F14] mb-1">AI Buyer Agent (AP2 Protocol)</h2>
                  <p className="text-sm text-[#6B5744] max-w-xl">
                    An external agent autonomously fulfils the goal:{' '}
                    <em className="font-medium text-[#2C1F14]">"Find a waterproof jacket under ₹2,000, negotiate the best discount, sign an AP2 mandate and execute payment."</em>
                  </p>
                </div>
                <button
                  onClick={runAutonomousBuyerSimulation}
                  disabled={agentRunning}
                  className="flex items-center gap-2 px-5 py-3 bg-[#C97941] hover:bg-[#A8622E] disabled:opacity-50 text-white text-sm font-semibold rounded-xl shadow-sm transition-colors shrink-0"
                >
                  <Bot className={`w-4 h-4 ${agentRunning ? 'animate-spin' : ''}`} />
                  {agentRunning ? 'Running…' : 'Run Agent Demo'}
                </button>
              </div>
            </Card>

            {/* Pipeline steps */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              {[
                { step: 1, title: 'Multi-Merchant Query',   desc: 'Searches Merchant A & B catalogs' },
                { step: 2, title: 'Goal Comparison',         desc: 'Filters price ≤ ₹2k & in-stock' },
                { step: 3, title: 'Negotiation',             desc: 'Requests 10% discount' },
                { step: 4, title: 'AP2 Mandate',             desc: 'Constructs & signs mandate' },
                { step: 5, title: 'Policy Gate & Razorpay',  desc: 'Guardrails + payment' },
                { step: 6, title: 'Receipt Proof',            desc: 'Verifies HMAC authenticity' },
              ].map((s) => (
                <div
                  key={s.step}
                  className={`p-4 rounded-xl border transition-all duration-300 ${
                    agentStep === s.step
                      ? 'bg-[#FDF4E8] border-[#C97941] shadow-[0_2px_12px_rgba(201,121,65,0.15)]'
                      : agentStep > s.step
                      ? 'bg-[#EBF4EE] border-[#C3DBC9]'
                      : 'bg-white border-[#E8E0D5] opacity-50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-[#9C836E] uppercase tracking-wider">Step {s.step}</span>
                    {agentStep > s.step
                      ? <CheckCircle2 className="w-4 h-4 text-[#4D7C5F]" />
                      : agentStep === s.step
                      ? <span className="w-2.5 h-2.5 rounded-full bg-[#C97941] animate-ping block" />
                      : <span className="w-2 h-2 rounded-full bg-[#E8E0D5] block" />
                    }
                  </div>
                  <p className="text-xs font-semibold text-[#2C1F14] mb-1">{s.title}</p>
                  <p className="text-[11px] text-[#9C836E]">{s.desc}</p>
                </div>
              ))}
            </div>

            {/* Results */}
            {agentResults && (
              <Card className="p-6 border-[#C3DBC9] bg-[#F5FBF7]">
                <div className="flex items-center justify-between pb-4 border-b border-[#E0EDE4] mb-5">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-[#4D7C5F]" />
                    <h3 className="font-bold text-[#2C1F14]">Autonomous Purchase Completed — Zero Human Input</h3>
                  </div>
                  <Badge variant="success">AP2 Verified</Badge>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
                  {[
                    { label: 'Winning Merchant', value: 'Urban Trail Co. (B)', sub: '₹1,899 vs ₹2,499 at Merchant A', color: 'text-[#2C1F14]' },
                    { label: 'Negotiated Discount', value: '10% OFF Approved', sub: 'Final: ₹1,709.10 (was ₹1,899)', color: 'text-[#4D7C5F]' },
                    { label: 'Razorpay Order', value: agentResults.razorpay_order?.order_id || 'N/A', sub: 'Test mode · Status: Captured', color: 'text-[#C97941] font-mono text-xs' },
                  ].map(({ label, value, sub, color }) => (
                    <div key={label} className="p-4 bg-white rounded-xl border border-[#E8E0D5]">
                      <SectionLabel className="mb-2">{label}</SectionLabel>
                      <p className={`text-sm font-bold ${color}`}>{value}</p>
                      <p className="text-[11px] text-[#9C836E] mt-1">{sub}</p>
                    </div>
                  ))}
                </div>

                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-white rounded-xl border border-[#E8E0D5]">
                  <div>
                    <SectionLabel className="mb-1">SHA-256 Receipt Hash</SectionLabel>
                    <code className="text-xs text-[#4D7C5F] font-mono break-all">{agentResults.verifiable_receipt?.receipt_hash}</code>
                  </div>
                  <button
                    onClick={() => { setVerifyOrderId(agentResults.order_id); setActiveTab('receipt_verify'); handleVerifyReceipt(agentResults.order_id); }}
                    className="flex items-center gap-1.5 px-4 py-2 bg-[#C97941] hover:bg-[#A8622E] text-white text-xs font-semibold rounded-lg transition-colors shrink-0"
                  >
                    Inspect Proof <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* ════════════════════════════════════════════
            TAB 3 — MULTI-MERCHANT CATALOG
        ════════════════════════════════════════════ */}
        {activeTab === 'catalogs' && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-bold text-[#2C1F14]">Multi-Merchant Agent-Readable Catalogs</h2>
              <p className="text-sm text-[#9C836E] mt-0.5">Two independent catalogs with identical schema — enabling autonomous cross-merchant comparison by AI agents.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {[
                { id: 'A', name: 'Apex Outfitters', sub: 'products_merchant_a · Premium Outdoor Gear', products: productsA, accent: 'text-[#C97941]', border: 'border-[#F2D9B5]', bg: 'bg-[#FDF4E8]' },
                { id: 'B', name: 'Urban Trail Co.',  sub: 'products_merchant_b · City Commute Apparel', products: productsB, accent: 'text-[#3B6EA8]', border: 'border-[#C5D9EF]', bg: 'bg-[#EEF3FA]' },
              ].map(({ id, name, sub, products, accent, border, bg }) => (
                <Card key={id} className="flex flex-col overflow-hidden">
                  <div className={`flex items-center justify-between px-5 py-4 ${bg} border-b ${border}`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg ${bg} border ${border} flex items-center justify-center font-bold ${accent} text-sm`}>{id}</div>
                      <div>
                        <h3 className="text-sm font-bold text-[#2C1F14]">{name}</h3>
                        <p className="text-[11px] text-[#9C836E]">{sub}</p>
                      </div>
                    </div>
                    <Badge variant="neutral">{products.length} Products</Badge>
                  </div>

                  <div className="p-4 space-y-2.5 overflow-y-auto" style={{ maxHeight: 560 }}>
                    {products.map((p) => (
                      <div key={p.product_id} className="flex items-center gap-3 p-3 bg-[#FAF8F5] rounded-xl border border-[#F0E9DF] hover:border-[#E0D0C0] transition-colors">
                        <img src={p.image_url} alt={p.name} className="w-12 h-12 rounded-lg object-cover bg-[#EEE8E0] shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <h4 className="text-xs font-semibold text-[#2C1F14] truncate">{p.name}</h4>
                            <Badge variant="neutral">{p.variant}</Badge>
                          </div>
                          <p className="text-[11px] text-[#9C836E] truncate mt-0.5">{p.description}</p>
                          <p className="text-sm font-bold text-[#C97941] mt-1">₹{p.price.toLocaleString('en-IN')}</p>
                        </div>
                        <Badge variant={p.stock_count > 0 ? 'success' : 'error'} className="shrink-0">
                          {p.stock_count > 0 ? `${p.stock_count} units` : 'Out of Stock'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════
            TAB 4 — AUDIT TRAIL
        ════════════════════════════════════════════ */}
        {activeTab === 'audit' && (
          <div className="space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-[#2C1F14]">Audit Trail & Security Telemetry</h2>
                <p className="text-sm text-[#9C836E] mt-0.5">Every intent, catalog lookup, policy evaluation, and Razorpay action committed to MongoDB <code className="text-xs bg-[#F5F1EB] px-1 rounded">audit_logs</code>.</p>
              </div>
              <button
                onClick={fetchLogs}
                className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-[#6B5744] bg-white border border-[#E8E0D5] hover:bg-[#F5F1EB] rounded-lg transition-colors w-fit"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Refresh
              </button>
            </div>

            <Card className="divide-y divide-[#F0E9DF] overflow-hidden">
              {auditLogs.length === 0 ? (
                <div className="py-16 text-center">
                  <Activity className="w-8 h-8 text-[#E8E0D5] mx-auto mb-3" />
                  <p className="text-sm text-[#BCA99A]">No logs yet. Run a chat or AI agent transaction.</p>
                </div>
              ) : auditLogs.map((log, i) => (
                <div key={log.id || i} className="px-5 py-4 hover:bg-[#FAF8F5] transition-colors">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={log.actor === 'outside_ai_buyer_agent' ? 'gold' : 'blue'}>
                        {log.actor === 'outside_ai_buyer_agent' ? <Bot className="w-3 h-3" /> : <MessageSquare className="w-3 h-3" />}
                        {log.actor === 'outside_ai_buyer_agent' ? 'AI Buyer Agent' : 'Human Chat'}
                      </Badge>
                      <span className="text-[11px] text-[#9C836E]">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <Badge variant={['SUCCESS','COMPLETED'].includes(log.final_status) ? 'success' : 'error'}>
                      {log.final_status}
                    </Badge>
                  </div>

                  <p className="text-xs font-medium text-[#2C1F14] mb-2">"{log.raw_input}"</p>

                  {log.policy_gate && (
                    <div className="flex flex-wrap gap-4 text-[11px] text-[#9C836E]">
                      <span>Policy: <span className={log.policy_gate.status === 'APPROVED' ? 'text-[#4D7C5F] font-semibold' : 'text-[#B84040] font-semibold'}>{log.policy_gate.status}{log.policy_gate.reason ? ` · ${log.policy_gate.reason}` : ''}</span></span>
                      {log.policy_gate.total_amount && <span>Amount: <span className="text-[#C97941] font-semibold">₹{log.policy_gate.total_amount.toLocaleString('en-IN')}</span></span>}
                    </div>
                  )}

                  {log.verifiable_receipt && (
                    <p className="mt-1 text-[10px] font-mono text-[#BCA99A] truncate">
                      <Hash className="w-2.5 h-2.5 inline mr-0.5" />{log.verifiable_receipt.receipt_hash}
                    </p>
                  )}
                </div>
              ))}
            </Card>
          </div>
        )}

        {/* ════════════════════════════════════════════
            TAB 5 — VERIFIABLE RECEIPT PROOF
        ════════════════════════════════════════════ */}
        {activeTab === 'receipt_verify' && (
          <div className="max-w-2xl mx-auto space-y-5">

            <div>
              <h2 className="text-lg font-bold text-[#2C1F14]">Cryptographic Receipt Proof</h2>
              <p className="text-sm text-[#9C836E] mt-0.5">
                An HMAC-SHA256 signature is generated over canonical order fields at checkout. This endpoint recomputes the hash in real-time to detect tampering.
              </p>
            </div>

            <Card className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <input
                  type="text"
                  value={verifyOrderId}
                  onChange={(e) => setVerifyOrderId(e.target.value)}
                  placeholder="Enter Order ID e.g. ord_20260902213237"
                  className="flex-1 bg-[#FAF8F5] border border-[#E8E0D5] rounded-xl px-4 py-2.5 text-sm font-mono text-[#2C1F14] placeholder-[#BCA99A] focus:outline-none focus:ring-2 focus:ring-[#C97941]/30 focus:border-[#C97941]"
                />
                <button
                  onClick={() => handleVerifyReceipt(verifyOrderId, false)}
                  className="px-4 py-2.5 bg-[#C97941] hover:bg-[#A8622E] text-white text-sm font-semibold rounded-xl transition-colors shadow-sm shrink-0"
                >
                  Verify
                </button>
              </div>

              {/* Tamper toggle */}
              {verifyResult && (
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#FAF8F5] border border-[#E8E0D5]">
                  <span className="text-xs font-medium text-[#6B5744]">Anti-Tamper Demonstration:</span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleVerifyReceipt(verifyOrderId, false)}
                      className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${!tamperSimulated ? 'bg-[#4D7C5F] text-white' : 'bg-[#F5F1EB] text-[#6B5744]'}`}
                    >Authentic</button>
                    <button
                      onClick={() => handleVerifyReceipt(verifyOrderId, true)}
                      className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${tamperSimulated ? 'bg-[#B84040] text-white' : 'bg-[#F5F1EB] text-[#6B5744]'}`}
                    >Simulate Tamper</button>
                  </div>
                </div>
              )}
            </Card>

            {verifyResult && (
              <div className={`p-6 rounded-2xl border shadow-[0_2px_16px_rgba(44,31,20,0.07)] transition-all ${
                verifyResult.proof?.verified
                  ? 'bg-[#F5FBF7] border-[#C3DBC9]'
                  : 'bg-[#FDF2F2] border-[#F0C4C4]'
              }`}>
                <div className="flex items-center justify-between pb-4 border-b border-current/10 mb-5">
                  <div className="flex items-center gap-2">
                    {verifyResult.proof?.verified
                      ? <CheckCircle2 className="w-5 h-5 text-[#4D7C5F]" />
                      : <XCircle className="w-5 h-5 text-[#B84040]" />
                    }
                    <h3 className={`font-bold text-sm ${verifyResult.proof?.verified ? 'text-[#2C3B2C]' : 'text-[#3B1010]'}`}>
                      {verifyResult.proof?.verified
                        ? 'Receipt Authenticated — Cryptographically Valid'
                        : 'SECURITY ALERT: Tamper Detected — Hash Mismatch!'
                      }
                    </h3>
                  </div>
                  <Badge variant={verifyResult.proof?.verified ? 'success' : 'error'}>
                    {verifyResult.proof?.verified ? 'PASSED' : 'TAMPERED'}
                  </Badge>
                </div>

                <div className="space-y-3">
                  {[
                    { label: 'Stored Receipt Hash', value: verifyResult.proof?.stored_hash, mono: true, color: '' },
                    { label: 'Recomputed Hash (Live)', value: verifyResult.proof?.recomputed_hash, mono: true,
                      color: verifyResult.proof?.verified ? 'text-[#4D7C5F]' : 'text-[#B84040] font-bold' },
                  ].map(({ label, value, mono, color }) => (
                    <div key={label} className="p-3.5 bg-white/80 rounded-xl border border-[#E8E0D5]">
                      <SectionLabel className="mb-1.5">{label}</SectionLabel>
                      <code className={`text-xs break-all ${color} ${mono ? 'font-mono' : ''}`}>{value}</code>
                    </div>
                  ))}

                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: 'Algorithm', value: 'HMAC-SHA256' },
                      { label: 'Merchant Signature', value: verifyResult.proof?.signature_valid ? 'Valid & Authorized' : 'Invalid Signature', ok: verifyResult.proof?.signature_valid },
                    ].map(({ label, value, ok }) => (
                      <div key={label} className="p-3.5 bg-white/80 rounded-xl border border-[#E8E0D5]">
                        <SectionLabel className="mb-1.5">{label}</SectionLabel>
                        <p className={`text-sm font-semibold ${ok === false ? 'text-[#B84040]' : ok === true ? 'text-[#4D7C5F]' : 'text-[#2C1F14]'}`}>{value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── FOOTER ───────────────────────────────────────────── */}
      <footer className="border-t border-[#E8E0D5] bg-white py-4 mt-8">
        <p className="text-center text-[11px] text-[#BCA99A]">
          Razorpay Hackathon · Track 1: AI Growth & Agentic Commerce · FastAPI · MongoDB Atlas · NVIDIA NIM · AP2 Protocol
        </p>
      </footer>
    </div>
  );
}
