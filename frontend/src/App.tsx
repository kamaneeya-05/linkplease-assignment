import { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle, Clock, Copy, Plus, RefreshCw, LucideIcon } from 'lucide-react';
import { apiService, Delivery, Rule, Stats } from './api';
import './index.css';

interface TabType {
  id: 'overview' | 'rules' | 'deliveries';
  label: string;
}

const TABS: TabType[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'rules', label: 'Rules' },
  { id: 'deliveries', label: 'Deliveries' },
];

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-slate-500/20 text-slate-300 border-slate-500/40',
  queued: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  sent: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  delivered: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  failed: 'bg-red-500/20 text-red-300 border-red-500/40',
  cancelled: 'bg-zinc-500/20 text-zinc-300 border-zinc-500/40',
};

function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'rules' | 'deliveries'>('overview');
  const [stats, setStats] = useState<Stats | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState('');
  const [message, setMessage] = useState('');
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const loadStats = async () => {
    try {
      const data = await apiService.getStats();
      setStats(data);
    } catch (err) {
      setError('Failed to load statistics');
      console.error(err);
    }
  };

  const loadRules = async () => {
    try {
      const data = await apiService.getRules();
      setRules(data);
    } catch (err) {
      setError('Failed to load rules');
      console.error(err);
    }
  };

  const loadDeliveries = async () => {
    try {
      const data = await apiService.getDeliveries();
      setDeliveries(data);
    } catch (err) {
      setError('Failed to load delivery activity');
      console.error(err);
    }
  };

  const loadData = async () => {
    setLoading(true);
    await Promise.all([loadStats(), loadRules(), loadDeliveries()]);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() || !message.trim()) {
      setError('Keyword and message are required');
      return;
    }

    try {
      await apiService.createRule(keyword, message);
      setKeyword('');
      setMessage('');
      setShowRuleForm(false);
      await loadRules();
      setError(null);
    } catch (err) {
      setError('Failed to create rule');
      console.error(err);
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <header className="border-b border-slate-700 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">LinkPlease</h1>
            <p className="text-slate-400 text-sm">Rule-based DM Automation</p>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 hover:bg-slate-800 rounded-lg transition text-slate-300 disabled:opacity-50"
          >
            <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-lg flex items-start gap-3">
            <AlertCircle className="text-red-500 flex-shrink-0 mt-0.5" size={20} />
            <div>
              <h3 className="font-semibold text-red-500">Error</h3>
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          </div>
        )}

        <div className="flex gap-2 mb-6 border-b border-slate-700">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-white border-b-2 border-blue-500'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <StatCard label="Sent" value={stats?.sent || 0} icon={CheckCircle} color="emerald" />
              <StatCard label="Failed" value={stats?.failed || 0} icon={AlertCircle} color="red" />
              <StatCard label="Queued" value={stats?.queued || 0} icon={Clock} color="amber" />
              <StatCard label="Duplicates Blocked" value={stats?.duplicates_blocked || 0} icon={Copy} color="blue" />
            </div>
          </div>
        )}

        {activeTab === 'rules' && (
          <div className="space-y-6">
            <button
              onClick={() => setShowRuleForm(!showRuleForm)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
            >
              <Plus size={20} />
              New Rule
            </button>

            {showRuleForm && (
              <form onSubmit={handleCreateRule} className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Keyword</label>
                  <input
                    type="text"
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder="e.g., PRICE"
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">DM Message</label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Message to send when keyword matches..."
                    rows={4}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition disabled:opacity-50"
                  >
                    Create Rule
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRuleForm(false)}
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            <div className="space-y-2">
              {rules.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <p>No rules created yet. Create one to get started!</p>
                </div>
              ) : (
                rules.map((rule) => (
                  <div key={rule.rule_id} className="bg-slate-800 border border-slate-700 rounded-lg p-4 hover:border-slate-600 transition">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-white truncate">{rule.keyword}</h3>
                        <p className="text-slate-400 text-sm mt-1">{rule.dm_message}</p>
                        <p className="text-slate-500 text-xs mt-2">Created: {new Date(rule.created_at).toLocaleString()}</p>
                      </div>
                      <button onClick={() => copyToClipboard(rule.rule_id, rule.rule_id)} className="p-2 hover:bg-slate-700 rounded-lg transition">
                        {copiedId === rule.rule_id ? (
                          <CheckCircle size={20} className="text-emerald-500" />
                        ) : (
                          <Copy size={20} className="text-slate-400" />
                        )}
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {activeTab === 'deliveries' && (
          <div className="space-y-4">
            <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
              {deliveries.length === 0 ? (
                <div className="text-center py-8 text-slate-400 p-4">
                  <p>No deliveries yet. Create a rule and send a matching comment.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-900 border-b border-slate-700">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-slate-300">Status</th>
                        <th className="px-4 py-3 text-left font-semibold text-slate-300">User</th>
                        <th className="px-4 py-3 text-left font-semibold text-slate-300">Rule</th>
                        <th className="px-4 py-3 text-left font-semibold text-slate-300">Attempts</th>
                        <th className="px-4 py-3 text-left font-semibold text-slate-300">Updated</th>
                        <th className="px-4 py-3 text-left font-semibold text-slate-300">Failure</th>
                      </tr>
                    </thead>
                    <tbody>
                      {deliveries.map((delivery) => (
                        <tr key={delivery.delivery_id} className="border-b border-slate-700 hover:bg-slate-700/50">
                          <td className="px-4 py-3">
                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[delivery.status] || STATUS_STYLES.pending}`}>
                              {delivery.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-slate-200">{delivery.user_id}</td>
                          <td className="px-4 py-3 text-slate-200">{delivery.keyword}</td>
                          <td className="px-4 py-3 text-slate-200">{delivery.attempts}</td>
                          <td className="px-4 py-3 text-slate-300">{new Date(delivery.updated_at).toLocaleString()}</td>
                          <td className="px-4 py-3 text-slate-300">{delivery.last_error || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number;
  icon: LucideIcon;
  color: 'emerald' | 'red' | 'amber' | 'blue';
}

function StatCard({ label, value, icon: Icon, color }: StatCardProps) {
  const colorClasses = {
    emerald: 'from-emerald-500/20 to-emerald-500/0 text-emerald-400 border-emerald-500/20',
    red: 'from-red-500/20 to-red-500/0 text-red-400 border-red-500/20',
    amber: 'from-amber-500/20 to-amber-500/0 text-amber-400 border-amber-500/20',
    blue: 'from-blue-500/20 to-blue-500/0 text-blue-400 border-blue-500/20',
  };

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} border rounded-lg p-6 backdrop-blur-sm`}>
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-slate-300 text-sm font-medium">{label}</h3>
        <Icon size={24} className={colorClasses[color].split(' ')[1]} />
      </div>
      <div className="text-3xl font-bold text-white">{value}</div>
    </div>
  );
}

export default App;
