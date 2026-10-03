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
  Info,
  X,
  Loader2,
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
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateReferral | null>(null);
  const [activeDetail, setActiveDetail] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailDescExpanded, setDetailDescExpanded] = useState(false);

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
    } catch {
      alert('Could not retrieve candidate resume. Please check with recruiting.');
    } finally {
      setDownloadingId(null);
    }
  };

  const handleOpenMatchDetail = async (c: CandidateReferral) => {
    setSelectedCandidate(c);
    setDetailDescExpanded(false);
    setActiveDetail(null);
    setDetailLoading(true);
    try {
      const res = await apiClient.get(`/api/v1/referral/${c.candidate_id}`);
      setActiveDetail(res.data);
    } catch {
      setActiveDetail(null);
    } finally {
      setDetailLoading(false);
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
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-neutral-900 text-neutral-100 border border-neutral-700 shadow-xs">
          <Calendar className="w-3.5 h-3.5 mr-1 text-brand-400" />
          Interview Scheduled
        </span>
      );
    }
    if (r.approval_status === 'Approved') {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
          <CheckCircle className="w-3.5 h-3.5 mr-1 text-emerald-600" />
          Approved
        </span>
      );
    }
    if (r.approval_status === 'Rejected') {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200">
          Rejected
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-900 border border-amber-200">
        <Clock className="w-3.5 h-3.5 mr-1 text-amber-600" />
        Pending Review
      </span>
    );
  };

  return (
    <div id="employee-dashboard" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Enterprise Dark & Red Welcome Banner */}
      <div className="bg-gradient-to-r from-black via-neutral-900 to-neutral-950 rounded-3xl p-8 text-white shadow-xl relative overflow-hidden border border-neutral-800">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-brand-950/80 border border-brand-700/40 text-brand-300 text-xs font-semibold mb-4">
            <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
            <span>Referral Acceleration Engine</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">Welcome back, {user?.name}!</h1>
          <p className="mt-2 text-neutral-300 text-sm leading-relaxed">
            Refer exceptional talent to active roles. Help your organization scale while earning recognition and points for every candidate submitted.
          </p>

          <div className="mt-6 flex flex-wrap gap-4">
            <button
              id="banner-refer-candidate-btn"
              onClick={onOpenReferralModal}
              className="inline-flex items-center space-x-2 bg-brand-700 hover:bg-brand-800 text-white px-5 py-2.5 rounded-xl font-semibold text-sm shadow-lg shadow-brand-900/30 transition transform active:scale-95 cursor-pointer"
            >
              <UserPlus className="w-4 h-4" />
              <span>Refer a Candidate</span>
            </button>

            <Link
              to="/chat"
              className="inline-flex items-center space-x-2 bg-white/10 hover:bg-white/20 text-white border border-white/20 px-5 py-2.5 rounded-xl font-semibold text-sm backdrop-blur-xs transition"
            >
              <span>Ask Referral AI</span>
              <ChevronRight className="w-4 h-4 text-brand-300" />
            </Link>
          </div>
        </div>

        {/* Ambient deep red gradient decoration */}
        <div className="absolute -right-10 -bottom-10 w-80 h-80 bg-brand-700/15 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Points Card */}
        <div id="employee-points-card" className="bg-white rounded-2xl p-6 border border-neutral-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Earned Points</p>
            <h3 className="text-3xl font-extrabold text-neutral-900 mt-1">{pointsData?.points ?? 0}</h3>
            <p className="text-xs text-amber-700 font-semibold mt-1">10 pts earned per referral</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-100">
            <Award className="w-6 h-6" />
          </div>
        </div>

        {/* Total Referrals Card */}
        <div className="bg-white rounded-2xl p-6 border border-neutral-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Total Referrals</p>
            <h3 className="text-3xl font-extrabold text-neutral-900 mt-1">{pointsData?.total_referrals ?? 0}</h3>
            <p className="text-xs text-neutral-500 font-medium mt-1">Candidates submitted</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-700 flex items-center justify-center border border-brand-100">
            <Users className="w-6 h-6" />
          </div>
        </div>

        {/* Approved Referrals Card */}
        <div className="bg-white rounded-2xl p-6 border border-neutral-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Approved by Recruiter</p>
            <h3 className="text-3xl font-extrabold text-neutral-900 mt-1">{pointsData?.approved_referrals ?? 0}</h3>
            <p className="text-xs text-emerald-700 font-semibold mt-1">Progressed to recruiting review</p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100">
            <CheckCircle className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Referrals Section */}
      <div className="bg-white rounded-2xl border border-neutral-200 shadow-xs overflow-hidden">
        <div className="px-6 py-5 border-b border-neutral-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-neutral-900">My Candidate Referrals</h2>
            <p className="text-xs text-neutral-500 mt-0.5">Real-time status updates from Zoho Recruit</p>
          </div>

          <div className="flex items-center space-x-3">
            <div className="relative">
              <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-2.5" />
              <input
                id="referral-search-input"
                type="text"
                placeholder="Search candidates..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-3 py-1.5 border border-neutral-300 rounded-xl text-xs placeholder-neutral-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/25 focus:border-brand-700 text-neutral-900"
              />
            </div>

            <button
              onClick={fetchData}
              disabled={loading}
              title="Refresh Referrals"
              className="p-2 border border-neutral-200 rounded-xl hover:bg-neutral-50 text-neutral-600 transition cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Table or Empty State */}
        {filteredReferrals.length > 0 ? (
          <div className="overflow-x-auto">
            <table id="employee-referrals-table" className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50 text-neutral-600 text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-3 px-6">Candidate</th>
                  <th className="py-3 px-6">Referred Date</th>
                  <th className="py-3 px-6">Best Match</th>
                  <th className="py-3 px-6">Match Score</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6 text-right">Resume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 text-sm">
                {filteredReferrals.map((candidate) => (
                  <tr key={candidate.candidate_id} className="hover:bg-neutral-50/70 transition">
                    <td className="py-4 px-6">
                      <div className="font-semibold text-neutral-900">{candidate.full_name}</div>
                      <div className="text-xs text-neutral-500">{candidate.email}</div>
                    </td>

                    <td className="py-4 px-6 text-xs text-neutral-600">
                      {candidate.referred_date || 'Recent'}
                    </td>

                    <td className="py-4 px-6 text-xs text-neutral-800 font-medium">
                      <button
                        onClick={() => handleOpenMatchDetail(candidate)}
                        className="inline-flex items-center space-x-1.5 text-left group hover:text-brand-700 transition cursor-pointer"
                        title="View match analysis"
                      >
                        <span className="font-semibold underline decoration-neutral-300 group-hover:decoration-brand-500">
                          {candidate.best_match?.job_title || 'General Intake'}
                        </span>
                        <Info className="w-3.5 h-3.5 text-neutral-400 group-hover:text-brand-600 shrink-0" />
                      </button>
                    </td>

                    <td className="py-4 px-6">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-semibold text-neutral-800">
                          {candidate.referral_score || 0}%
                        </span>
                        <div className="w-16 bg-neutral-200 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-brand-700 h-1.5 rounded-full"
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
                        className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-neutral-200 text-xs font-medium text-neutral-700 hover:bg-neutral-100 transition disabled:opacity-50 cursor-pointer"
                      >
                        <FileText className="w-3.5 h-3.5 text-neutral-500" />
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
          <div id="employee-empty-state" className="py-16 text-center">
            <Users className="w-12 h-12 text-neutral-300 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-neutral-800">No candidate referrals found</h3>
            <p className="text-xs text-neutral-500 mt-1 max-w-sm mx-auto">
              You haven't referred any candidates yet. Click below to submit your first referral and earn 10 points!
            </p>
            <button
              onClick={onOpenReferralModal}
              className="mt-4 inline-flex items-center space-x-2 px-4 py-2 bg-brand-700 text-white rounded-xl text-xs font-semibold hover:bg-brand-800 transition cursor-pointer"
            >
              <UserPlus className="w-4 h-4" />
              <span>Refer Candidate Now</span>
            </button>
          </div>
        )}
      </div>

      {/* Referral Match Details Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-neutral-200 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-neutral-100 pb-3">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-base font-bold text-neutral-900">{selectedCandidate.full_name}</h3>
                  {detailLoading && <Loader2 className="w-4 h-4 animate-spin text-brand-600" />}
                </div>
                <p className="text-xs text-neutral-500">{selectedCandidate.email}</p>
              </div>
              <button
                onClick={() => setSelectedCandidate(null)}
                className="p-1 text-neutral-400 hover:text-neutral-600 rounded-lg hover:bg-neutral-100 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Target Role & Match Score */}
            <div className="space-y-3">
              <div>
                <div className="flex justify-between items-center text-sm mb-1">
                  <span className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    Target Role Match
                  </span>
                  <span className="text-sm font-bold text-brand-700">
                    {activeDetail?.best_match?.match_percent ?? selectedCandidate.best_match?.match_percent ?? selectedCandidate.referral_score}% Match
                  </span>
                </div>
                <div className="text-sm font-bold text-neutral-900">
                  {activeDetail?.best_match?.job_title || selectedCandidate.best_match?.job_title || 'General Intake'}
                </div>
                {(activeDetail?.best_match?.job_id || selectedCandidate.best_match?.job_id) && (
                  <div className="text-[11px] font-mono text-neutral-500 mt-0.5">
                    Job ID: {activeDetail?.best_match?.job_id || selectedCandidate.best_match?.job_id}
                  </div>
                )}
                <div className="w-full bg-neutral-200 rounded-full h-2 mt-2 overflow-hidden">
                  <div
                    className="bg-brand-700 h-2 rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(
                        100,
                        activeDetail?.best_match?.match_percent ?? selectedCandidate.best_match?.match_percent ?? selectedCandidate.referral_score
                      )}%`,
                    }}
                  />
                </div>
              </div>

              {/* Why this match: notes */}
              {(activeDetail?.best_match?.notes || selectedCandidate.best_match?.notes) && (
                <div className="p-3 bg-brand-50/70 border border-brand-200/80 rounded-xl">
                  <span className="text-[11px] font-bold text-brand-900 uppercase tracking-wider block mb-1">
                    ✨ Why this match:
                  </span>
                  <p className="text-xs text-brand-950 leading-relaxed font-medium">
                    {activeDetail?.best_match?.notes || selectedCandidate.best_match?.notes}
                  </p>
                </div>
              )}

              {/* Role Description with expand/collapse */}
              {(activeDetail?.best_match?.job_description || selectedCandidate.best_match?.job_description) && (
                <div className="p-3 bg-neutral-50 border border-neutral-200 rounded-xl">
                  <span className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider block mb-1">
                    Role Description
                  </span>
                  <p className="text-xs text-neutral-700 leading-relaxed whitespace-pre-line">
                    {detailDescExpanded
                      ? (activeDetail?.best_match?.job_description || selectedCandidate.best_match?.job_description)
                      : `${(activeDetail?.best_match?.job_description || selectedCandidate.best_match?.job_description).slice(0, 160)}${
                          (activeDetail?.best_match?.job_description || selectedCandidate.best_match?.job_description).length > 160 ? '...' : ''
                        }`}
                  </p>
                  {(activeDetail?.best_match?.job_description || selectedCandidate.best_match?.job_description).length > 160 && (
                    <button
                      type="button"
                      onClick={() => setDetailDescExpanded(!detailDescExpanded)}
                      className="mt-1 text-xs font-semibold text-brand-700 hover:text-brand-800 transition cursor-pointer"
                    >
                      {detailDescExpanded ? 'Show less' : 'Read full description'}
                    </button>
                  )}
                </div>
              )}

              {/* Matched & Missing Skills if available */}
              {activeDetail?.best_match?.matched_skills && activeDetail.best_match.matched_skills.length > 0 && (
                <div>
                  <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider block mb-1.5">
                    Matched Skills ({activeDetail.best_match.matched_skills.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {activeDetail.best_match.matched_skills.map((s: string, idx: number) => (
                      <span key={idx} className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-medium">
                        ✓ {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end space-x-3 pt-3 border-t border-neutral-100">
              <button
                onClick={() =>
                  handleDownloadResume(selectedCandidate.candidate_id, selectedCandidate.full_name)
                }
                disabled={downloadingId === selectedCandidate.candidate_id}
                className="px-3.5 py-2 border border-neutral-200 text-neutral-700 text-xs font-semibold rounded-xl hover:bg-neutral-50 transition cursor-pointer inline-flex items-center space-x-1.5"
              >
                <FileText className="w-3.5 h-3.5 text-neutral-500" />
                <span>Download Resume</span>
              </button>
              <button
                onClick={() => setSelectedCandidate(null)}
                className="px-4 py-2 bg-brand-700 hover:bg-brand-800 text-white text-xs font-semibold rounded-xl transition cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
