import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../../store/authStore';
import { apiClient } from '../../api/client';
import type { CandidateReferral, EmployeePoints } from '../../types';
import {
  Award,
  Users,
  CheckCircle,
  Clock,
  Calendar,
  FileText,
  UserPlus,
  RefreshCw,
  Search,
  ChevronRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface EmployeeDashboardProps {
  onOpenReferralModal: () => void;
  onPointsUpdate?: (points: number) => void;
}

export const EmployeeDashboard: React.FC<EmployeeDashboardProps> = ({
  onOpenReferralModal,
  onPointsUpdate,
}) => {
  const { user } = useAuthStore();
  const [pointsData, setPointsData] = useState<EmployeePoints | null>(null);
  const [referrals, setReferrals] = useState<CandidateReferral[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ptsRes, listRes] = await Promise.all([
        apiClient.get<EmployeePoints>('/api/v1/employees/points'),
        apiClient.get<CandidateReferral[]>('/api/v1/referral/list'),
      ]);

      setPointsData(ptsRes.data);
      setReferrals(listRes.data);
      if (onPointsUpdate && ptsRes.data?.points !== undefined) {
        onPointsUpdate(ptsRes.data.points);
      }
    } catch (err) {
      console.error('Failed to load employee dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleDownloadResume = async (candidateId: string, candidateName: string) => {
    setDownloadingId(candidateId);
    try {
      const response = await apiClient.get(`/api/v1/referral/${candidateId}/resume`, {
        responseType: 'blob',
      });

      const contentType = String(response.headers['content-type'] || 'application/pdf');
      const blob = new Blob([response.data], {
        type: contentType,
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${candidateName.replace(/\s+/g, '_')}_Resume.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Could not retrieve candidate resume. Please check with recruiting.');
    } finally {
      setDownloadingId(null);
    }
  };

  const filteredReferrals = referrals.filter(
    (r) =>
      r.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusBadge = (r: CandidateReferral) => {
    if (r.candidate_status?.toLowerCase().includes('interview')) {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
          <Calendar className="w-3.5 h-3.5 mr-1" />
          Interview Scheduled
        </span>
      );
    }
    if (r.approval_status === 'Approved') {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle className="w-3.5 h-3.5 mr-1" />
          Approved
        </span>
      );
    }
    if (r.approval_status === 'Rejected') {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          Rejected
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <Clock className="w-3.5 h-3.5 mr-1" />
        Pending Review
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-brand-900 via-indigo-900 to-slate-900 rounded-3xl p-8 text-white shadow-xl relative overflow-hidden">
        <div className="relative z-10 max-w-2xl">
          <h1 className="text-3xl font-extrabold tracking-tight">Welcome back, {user?.name}!</h1>
          <p className="mt-2 text-brand-100 text-sm leading-relaxed">
            Refer exceptional colleagues and friends. Help your teams grow while earning referral rewards and points for every candidate submitted.
          </p>

          <div className="mt-6 flex flex-wrap gap-4">
            <button
              onClick={onOpenReferralModal}
              className="inline-flex items-center space-x-2 bg-white text-brand-900 hover:bg-brand-50 px-5 py-2.5 rounded-xl font-semibold text-sm shadow-md transition transform active:scale-95"
            >
              <UserPlus className="w-4 h-4 text-brand-600" />
              <span>Refer a Candidate</span>
            </button>

            <Link
              to="/chat"
              className="inline-flex items-center space-x-2 bg-white/10 hover:bg-white/20 text-white border border-white/20 px-5 py-2.5 rounded-xl font-semibold text-sm backdrop-blur-xs transition"
            >
              <span>Ask Referral AI</span>
              <ChevronRight className="w-4 h-4 text-brand-200" />
            </Link>
          </div>
        </div>

        {/* Ambient gradient decoration */}
        <div className="absolute -right-10 -bottom-10 w-80 h-80 bg-brand-500/20 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Points Card */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Earned Points</p>
            <h3 className="text-3xl font-extrabold text-slate-900 mt-1">{pointsData?.points ?? 0}</h3>
            <p className="text-xs text-amber-600 font-medium mt-1">10 pts earned per referral</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <Award className="w-6 h-6" />
          </div>
        </div>

        {/* Total Referrals Card */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Referrals</p>
            <h3 className="text-3xl font-extrabold text-slate-900 mt-1">{pointsData?.total_referrals ?? 0}</h3>
            <p className="text-xs text-slate-500 font-medium mt-1">Candidates submitted</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
        </div>

        {/* Approved Referrals Card */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Approved by Recruiter</p>
            <h3 className="text-3xl font-extrabold text-slate-900 mt-1">{pointsData?.approved_referrals ?? 0}</h3>
            <p className="text-xs text-emerald-600 font-medium mt-1">Progressed to recruiting review</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <CheckCircle className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Referrals Section */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-200/80 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">My Candidate Referrals</h2>
            <p className="text-xs text-slate-500 mt-0.5">Real-time status updates from Zoho Recruit</p>
          </div>

          <div className="flex items-center space-x-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search candidates..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-3 py-1.5 border border-slate-300 rounded-xl text-xs placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>

            <button
              onClick={fetchData}
              disabled={loading}
              title="Refresh Referrals"
              className="p-2 border border-slate-200 rounded-xl hover:bg-slate-50 text-slate-600 transition"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Table or Empty State */}
        {filteredReferrals.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200/60 bg-slate-50/50 text-slate-500 text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-3 px-6">Candidate</th>
                  <th className="py-3 px-6">Referred Date</th>
                  <th className="py-3 px-6">Best Match</th>
                  <th className="py-3 px-6">Match Score</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6 text-right">Resume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredReferrals.map((candidate) => (
                  <tr key={candidate.candidate_id} className="hover:bg-slate-50/50 transition">
                    <td className="py-4 px-6">
                      <div className="font-semibold text-slate-900">{candidate.full_name}</div>
                      <div className="text-xs text-slate-500">{candidate.email}</div>
                    </td>

                    <td className="py-4 px-6 text-xs text-slate-600">
                      {candidate.referred_date || 'Recent'}
                    </td>

                    <td className="py-4 px-6 text-xs text-slate-700 font-medium">
                      {candidate.best_match?.job_title || 'General Intake'}
                    </td>

                    <td className="py-4 px-6">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-semibold text-slate-700">
                          {candidate.referral_score || 0}%
                        </span>
                        <div className="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-brand-600 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, candidate.referral_score || 0)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    <td className="py-4 px-6">{getStatusBadge(candidate)}</td>

                    <td className="py-4 px-6 text-right">
                      <button
                        onClick={() =>
                          handleDownloadResume(candidate.candidate_id, candidate.full_name)
                        }
                        disabled={downloadingId === candidate.candidate_id}
                        className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-100 transition disabled:opacity-50"
                      >
                        <FileText className="w-3.5 h-3.5 text-slate-500" />
                        <span>
                          {downloadingId === candidate.candidate_id ? 'Loading...' : 'View Resume'}
                        </span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-16 text-center">
            <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-slate-800">No candidate referrals found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              You haven't referred any candidates yet. Click below to submit your first referral and earn 10 points!
            </p>
            <button
              onClick={onOpenReferralModal}
              className="mt-4 inline-flex items-center space-x-2 px-4 py-2 bg-brand-600 text-white rounded-xl text-xs font-semibold hover:bg-brand-700 transition"
            >
              <UserPlus className="w-4 h-4" />
              <span>Refer Candidate Now</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
