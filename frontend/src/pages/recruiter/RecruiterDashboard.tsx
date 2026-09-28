import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import type { DashboardMetrics, FunnelStage, CandidateReferral, OverdueReferral } from '../../types';
import {
  Users,
  Clock,
  CheckCircle,
  XCircle,
  Calendar,
  TrendingUp,
  AlertTriangle,
  Search,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

export const RecruiterDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [funnel, setFunnel] = useState<FunnelStage[]>([]);
  const [referrals, setReferrals] = useState<CandidateReferral[]>([]);
  const [overdue, setOverdue] = useState<OverdueReferral[]>([]);
  const [loading, setLoading] = useState(true);

  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'overdue'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [metricsRes, funnelRes, listRes, pendingRes] = await Promise.all([
        apiClient.get<DashboardMetrics>('/api/v1/analytics/dashboard'),
        apiClient.get<{ funnel_stages: FunnelStage[] }>('/api/v1/analytics/conversion'),
        apiClient.get<CandidateReferral[]>('/api/v1/referral/list'),
        apiClient.get<{ overdue_referrals: OverdueReferral[] }>('/api/v1/analytics/pending?days_threshold=5'),
      ]);

      setMetrics(metricsRes.data);
      setFunnel(funnelRes.data?.funnel_stages || []);
      setReferrals(listRes.data || []);
      setOverdue(pendingRes.data?.overdue_referrals || []);
    } catch (err) {
      console.error('Failed to load recruiter analytics dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredReferrals = referrals.filter((r) => {
    const matchesSearch =
      r.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.referred_by.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (activeTab === 'pending') {
      return r.approval_status === 'Pending';
    }
    if (activeTab === 'overdue') {
      return overdue.some((o) => o.candidate_id === r.candidate_id);
    }
    if (statusFilter !== 'all') {
      return r.approval_status === statusFilter;
    }
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Recruitment Referral Operations</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time pipeline monitoring, SLA tracking, and Zoho Recruit candidate synchronization
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-xl shadow-xs transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Sync Data</span>
          </button>
        </div>
      </div>

      {/* Overdue Review Alert Banner */}
      {overdue.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-amber-900">
                {overdue.length} Referral{overdue.length > 1 ? 's' : ''} Pending Review &gt; 5 Days
              </h4>
              <p className="text-xs text-amber-700 mt-0.5">
                Review turnaround SLA is at risk. Please prioritize evaluating these candidates.
              </p>
            </div>
          </div>
          <button
            onClick={() => setActiveTab('overdue')}
            className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow-xs transition"
          >
            Filter Overdue
          </button>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Total</span>
            <Users className="w-4 h-4 text-brand-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{metrics?.total_referrals ?? 0}</div>
          <p className="text-[10px] text-slate-400 mt-1">Candidates in Zoho</p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-amber-600 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Pending</span>
            <Clock className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-amber-600">{metrics?.pending_approval ?? 0}</div>
          <p className="text-[10px] text-slate-400 mt-1">Awaiting decision</p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-emerald-600 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Approved</span>
            <CheckCircle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-emerald-600">{metrics?.approved_referrals ?? 0}</div>
          <p className="text-[10px] text-slate-400 mt-1">Moved to pipeline</p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-rose-600 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Rejected</span>
            <XCircle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-rose-600">{metrics?.rejected_referrals ?? 0}</div>
          <p className="text-[10px] text-slate-400 mt-1">Declined</p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-indigo-600 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Interviews</span>
            <Calendar className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-indigo-600">{metrics?.interviews_scheduled ?? 0}</div>
          <p className="text-[10px] text-slate-400 mt-1">Teams meetings</p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-brand-600 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Conversion</span>
            <TrendingUp className="w-4 h-4" />
          </div>
          <div className="text-2xl font-bold text-brand-600">{metrics?.overall_conversion_rate ?? 0}%</div>
          <p className="text-[10px] text-slate-400 mt-1">Avg review {metrics?.avg_approval_time_days ?? 0}d</p>
        </div>
      </div>

      {/* Visual Analytics Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recruitment Funnel Chart */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Recruitment Funnel Conversion</h3>
              <p className="text-xs text-slate-500">Volume and step-by-step conversion across milestones</p>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 bg-slate-100 rounded-full text-slate-600">
              Zoho Lifecycle
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnel} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="stage" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload as FunnelStage;
                      return (
                        <div className="bg-slate-900 text-white text-xs rounded-xl p-3 shadow-lg">
                          <p className="font-bold">{data.stage}</p>
                          <p className="text-slate-300 mt-1">Candidates: {data.count}</p>
                          <p className="text-brand-300">Conversion: {data.conversion_from_previous}%</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="count" fill="#4f46e5" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Efficiency & Speed Card */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Turnaround Velocity</h3>
            <p className="text-xs text-slate-500 mt-0.5">Speed from submission to initial review decision</p>

            <div className="mt-8 text-center">
              <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-brand-50 border-4 border-brand-100 text-brand-700 shadow-inner">
                <span className="text-3xl font-extrabold">{metrics?.avg_approval_time_days ?? 0}</span>
                <span className="text-xs font-semibold ml-0.5">d</span>
              </div>
              <p className="text-xs font-semibold text-slate-700 mt-3">Average Review Time</p>
              <p className="text-[11px] text-slate-400">Target SLA is &lt; 3.0 days</p>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4 mt-6">
            <div className="flex justify-between text-xs text-slate-600 mb-1">
              <span>SLA Compliance</span>
              <span className="font-semibold text-emerald-600">
                {metrics && metrics.total_referrals > 0
                  ? Math.round(((metrics.total_referrals - overdue.length) / metrics.total_referrals) * 100)
                  : 100}
                %
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div
                className="bg-emerald-500 h-2 rounded-full"
                style={{
                  width: `${
                    metrics && metrics.total_referrals > 0
                      ? Math.round(((metrics.total_referrals - overdue.length) / metrics.total_referrals) * 100)
                      : 100
                  }%`,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Referrals Operations Management Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        {/* Table Controls */}
        <div className="px-6 py-4 border-b border-slate-200/80 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Tabs */}
          <div className="flex space-x-1 bg-slate-100 p-1 rounded-xl">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'all'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All Referrals ({referrals.length})
            </button>
            <button
              onClick={() => setActiveTab('pending')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'pending'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Pending Review ({metrics?.pending_approval ?? 0})
            </button>
            <button
              onClick={() => setActiveTab('overdue')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'overdue'
                  ? 'bg-white text-amber-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Overdue SLA ({overdue.length})
            </button>
          </div>

          {/* Search & Filter */}
          <div className="flex items-center space-x-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search candidate / referrer..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-3 py-1.5 border border-slate-300 rounded-xl text-xs placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="py-1.5 px-3 border border-slate-300 rounded-xl text-xs text-slate-700 bg-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="all">All Statuses</option>
              <option value="Pending">Pending</option>
              <option value="Approved">Approved</option>
              <option value="Rejected">Rejected</option>
            </select>
          </div>
        </div>

        {/* Table Body */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200/60 bg-slate-50/50 text-slate-500 text-[11px] font-semibold uppercase tracking-wider">
                <th className="py-3 px-6">Candidate</th>
                <th className="py-3 px-6">Referrer (Employee)</th>
                <th className="py-3 px-6">Referred Date</th>
                <th className="py-3 px-6">Best Job Match</th>
                <th className="py-3 px-6">Score</th>
                <th className="py-3 px-6">Approval Status</th>
                <th className="py-3 px-6 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filteredReferrals.map((c) => (
                <tr key={c.candidate_id} className="hover:bg-slate-50/50 transition">
                  <td className="py-4 px-6">
                    <div className="font-semibold text-slate-900">{c.full_name}</div>
                    <div className="text-xs text-slate-500">{c.email}</div>
                  </td>

                  <td className="py-4 px-6 text-xs text-slate-600 font-medium">
                    {c.referred_by}
                  </td>

                  <td className="py-4 px-6 text-xs text-slate-500">
                    {c.referred_date || 'Recent'}
                  </td>

                  <td className="py-4 px-6 text-xs text-slate-800 font-medium">
                    {c.best_match?.job_title || 'General Intake'}
                  </td>

                  <td className="py-4 px-6">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-brand-50 text-brand-700">
                      {c.referral_score || 0}%
                    </span>
                  </td>

                  <td className="py-4 px-6">
                    {c.approval_status === 'Approved' ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Approved
                      </span>
                    ) : c.approval_status === 'Rejected' ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                        Rejected
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                        Pending
                      </span>
                    )}
                  </td>

                  <td className="py-4 px-6 text-right">
                    <Link
                      to={`/approvals/${c.candidate_id}`}
                      className="inline-flex items-center space-x-1 px-3 py-1.5 bg-brand-50 hover:bg-brand-100 text-brand-700 rounded-lg text-xs font-semibold transition"
                    >
                      <span>Review</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
