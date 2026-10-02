import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import type { CandidateDetail } from '../../types';
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Calendar,
  FileText,
  AlertTriangle,
  Briefcase,
  GraduationCap,
  Sparkles,
  Mail,
  Phone,
  Link2,
  Globe,
  Loader2,
  Lock,
} from 'lucide-react';

export const ApprovalDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  // Decision Modal State
  const [decisionModal, setDecisionModal] = useState<'approve' | 'reject' | null>(null);
  const [decisionNote, setDecisionNote] = useState('');
  const [decisionLoading, setDecisionLoading] = useState(false);

  // Schedule Modal State
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [scheduleData, setScheduleData] = useState({
    start_time: '',
    duration_minutes: 45,
    interviewer_email: '',
    subject: 'Technical Referral Interview',
  });
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleSuccessMsg, setScheduleSuccessMsg] = useState<string | null>(null);

  const fetchCandidate = async () => {
    if (!id) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const response = await apiClient.get<CandidateDetail>(`/api/v1/approvals/${id}`);
      setCandidate(response.data);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to load candidate details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidate();
  }, [id]);

  const handleDownloadResume = async () => {
    if (!candidate) return;
    setDownloading(true);
    try {
      const response = await apiClient.get(`/api/v1/referral/${candidate.candidate_id}/resume`, {
        responseType: 'blob',
      });
      const contentType = String(response.headers['content-type'] || 'application/pdf');
      const blob = new Blob([response.data], {
        type: contentType,
      });
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      alert('Unable to open resume. Attachment might be missing in Zoho.');
    } finally {
      setDownloading(false);
    }
  };

  const handleDecisionSubmit = async () => {
    if (!candidate || !decisionModal) return;
    if (decisionModal === 'reject' && !decisionNote.trim()) {
      alert('A rejection reason note is required.');
      return;
    }

    setDecisionLoading(true);
    try {
      const endpoint =
        decisionModal === 'approve'
          ? `/api/v1/approvals/${candidate.candidate_id}/approve`
          : `/api/v1/approvals/${candidate.candidate_id}/reject`;

      await apiClient.post(endpoint, { note: decisionNote.trim() });
      setDecisionModal(null);
      setDecisionNote('');
      await fetchCandidate();
    } catch (err: any) {
      alert(err.response?.data?.detail || `Failed to ${decisionModal} candidate.`);
    } finally {
      setDecisionLoading(false);
    }
  };

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!candidate) return;
    if (!scheduleData.start_time) {
      alert('Please pick a date and start time.');
      return;
    }
    if (!scheduleData.interviewer_email) {
      alert('Please specify the corporate interviewer email.');
      return;
    }

    setScheduleLoading(true);
    try {
      // Format start_time to ISO format
      const isoStartTime = new Date(scheduleData.start_time).toISOString();

      const response = await apiClient.post('/api/v1/interview/schedule', {
        candidate_id: candidate.candidate_id,
        start_time: isoStartTime,
        duration_minutes: Number(scheduleData.duration_minutes),
        interviewer_email: scheduleData.interviewer_email.trim(),
        subject: scheduleData.subject.trim(),
      });

      setScheduleSuccessMsg(
        `Teams meeting scheduled successfully! Meeting link: ${response.data.meeting_url}`
      );
      await fetchCandidate();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to schedule interview.');
    } finally {
      setScheduleLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-700" />
      </div>
    );
  }

  if (errorMsg || !candidate) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center">
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-stone-800">Candidate Not Found</h2>
        <p className="text-sm text-stone-500 mt-1">{errorMsg || 'Could not locate candidate in Zoho.'}</p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center space-x-2 text-sm font-semibold text-brand-700 hover:text-brand-800"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>
    );
  }

  const isApproved = candidate.approval_status === 'Approved';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Breadcrumb & Action Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-stone-200/90 pb-4">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 text-stone-500 hover:text-stone-900 rounded-xl hover:bg-stone-100 transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-stone-900">{candidate.full_name}</h1>
            <p className="text-xs text-stone-500">
              Referred by <span className="font-semibold text-stone-700">{candidate.referred_by}</span> on {candidate.referred_date || 'Recent'}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-3">
          <button
            onClick={handleDownloadResume}
            disabled={downloading}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 border border-stone-300 bg-white hover:bg-stone-50 text-stone-700 text-xs font-semibold rounded-xl shadow-xs transition"
          >
            <FileText className="w-4 h-4 text-stone-500" />
            <span>{downloading ? 'Loading Resume...' : 'View Resume'}</span>
          </button>

          {candidate.approval_status === 'Pending' && (
            <>
              <button
                onClick={() => setDecisionModal('reject')}
                className="inline-flex items-center space-x-1.5 px-4 py-2 border border-rose-300 bg-white hover:bg-rose-50 text-rose-700 text-xs font-semibold rounded-xl shadow-xs transition"
              >
                <XCircle className="w-4 h-4" />
                <span>Reject</span>
              </button>

              <button
                onClick={() => setDecisionModal('approve')}
                className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl shadow-xs transition"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Approve Referral</span>
              </button>
            </>
          )}

          {/* Schedule Interview (Gated until Approved) */}
          <div className="relative group">
            <button
              onClick={() => isApproved && setScheduleModalOpen(true)}
              disabled={!isApproved}
              className={`inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold shadow-xs transition ${
                isApproved
                  ? 'bg-brand-700 hover:bg-brand-800 text-white'
                  : 'bg-stone-100 text-stone-400 cursor-not-allowed border border-stone-200'
              }`}
            >
              {isApproved ? <Calendar className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
              <span>Schedule Interview</span>
            </button>
            {!isApproved && (
              <div className="absolute right-0 top-full mt-1 hidden group-hover:block w-48 bg-stone-900 text-white text-[11px] rounded-lg p-2 shadow-lg z-20 text-center">
                Candidate referral must be approved before scheduling an interview.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Identity Mismatch Alert Banner */}
      {candidate.identity_mismatch && (
        <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 flex items-start space-x-3 text-amber-900 shadow-xs">
          <AlertTriangle className="w-5 h-5 shrink-0 text-amber-600 mt-0.5" />
          <div className="text-xs">
            <span className="font-bold">Identity Mismatch Warning:</span> The email or name extracted from the uploaded resume differs from what the referring employee entered. The referring input was preserved as primary in Zoho.
          </div>
        </div>
      )}

      {/* Main Grid: Left Profile, Right Match Scorecard */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Candidate Bio & Parsed Resume Data */}
        <div className="lg:col-span-2 space-y-6">
          {/* Overview Card */}
          <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  {candidate.parsed_profile?.headline || candidate.full_name}
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {candidate.parsed_profile?.current_job_title || 'Professional'}
                  {candidate.parsed_profile?.current_employer
                    ? ` at ${candidate.parsed_profile.current_employer}`
                    : ''}
                </p>
              </div>

              {/* Status Badge */}
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${
                  candidate.approval_status === 'Approved'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : candidate.approval_status === 'Rejected'
                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                    : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}
              >
                {candidate.approval_status}
              </span>
            </div>

            {/* Summary */}
            {candidate.parsed_profile?.summary && (
              <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                {candidate.parsed_profile.summary}
              </p>
            )}

            {/* Contact details */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-xs text-slate-600">
              <div className="flex items-center space-x-2">
                <Mail className="w-4 h-4 text-slate-400" />
                <span className="truncate">{candidate.email}</span>
              </div>
              {candidate.phone && (
                <div className="flex items-center space-x-2">
                  <Phone className="w-4 h-4 text-slate-400" />
                  <span>{candidate.phone}</span>
                </div>
              )}
              {candidate.parsed_profile?.total_experience_years !== undefined && (
                <div className="flex items-center space-x-2">
                  <Briefcase className="w-4 h-4 text-slate-400" />
                  <span>{candidate.parsed_profile.total_experience_years} Years Experience</span>
                </div>
              )}
            </div>

            {/* Links */}
            {candidate.parsed_profile?.links && (
              <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100">
                {candidate.parsed_profile.links.linkedin && (
                  <a
                    href={candidate.parsed_profile.links.linkedin}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center space-x-1.5 px-3 py-1 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs text-slate-700 transition"
                  >
                    <Link2 className="w-3.5 h-3.5 text-blue-600" />
                    <span>LinkedIn Profile</span>
                  </a>
                )}
                {candidate.parsed_profile.links.github && (
                  <a
                    href={candidate.parsed_profile.links.github}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center space-x-1.5 px-3 py-1 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs text-slate-700 transition"
                  >
                    <Globe className="w-3.5 h-3.5 text-slate-900" />
                    <span>GitHub Profile</span>
                  </a>
                )}
              </div>
            )}
          </div>

          {/* Work Experience Timeline */}
          <div className="bg-white rounded-2xl border border-stone-200/90 p-6 shadow-xs space-y-4">
            <div className="flex items-center space-x-2">
              <Briefcase className="w-5 h-5 text-brand-700" />
              <h3 className="text-sm font-bold text-stone-900">Experience History</h3>
            </div>

            {candidate.parsed_profile?.experience && candidate.parsed_profile.experience.length > 0 ? (
              <div className="divide-y divide-stone-100 space-y-4 pt-1">
                {candidate.parsed_profile.experience.map((exp, idx) => (
                  <div key={idx} className="pt-3 first:pt-0">
                    <div className="flex justify-between items-start text-xs">
                      <div>
                        <h4 className="font-bold text-stone-900">{exp.job_title}</h4>
                        <p className="text-brand-800 font-medium">{exp.company}</p>
                      </div>
                      <span className="text-stone-400">
                        {exp.start_date || 'Start'} &mdash; {exp.end_date || (exp.is_current ? 'Present' : 'End')}
                      </span>
                    </div>
                    {exp.description && (
                      <p className="text-xs text-stone-600 mt-2 leading-relaxed">{exp.description}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-stone-400 italic">No structured work history parsed.</p>
            )}
          </div>

          {/* Education Section */}
          <div className="bg-white rounded-2xl border border-stone-200/90 p-6 shadow-xs space-y-4">
            <div className="flex items-center space-x-2">
              <GraduationCap className="w-5 h-5 text-brand-700" />
              <h3 className="text-sm font-bold text-stone-900">Education Details</h3>
            </div>

            {candidate.parsed_profile?.education && candidate.parsed_profile.education.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {candidate.parsed_profile.education.map((edu, idx) => (
                  <div key={idx} className="bg-stone-50 p-4 rounded-xl border border-stone-100 text-xs">
                    <h4 className="font-bold text-stone-900">{edu.degree || 'Degree'}</h4>
                    <p className="text-stone-600 mt-0.5">{edu.field_of_study}</p>
                    <p className="text-stone-400 mt-1">{edu.institution}</p>
                    {edu.grade && <span className="inline-block mt-2 font-semibold text-brand-800">{edu.grade}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-stone-400 italic">No structured education parsed.</p>
            )}
          </div>
        </div>

        {/* Right Col: AI Match Scorecard & Skills */}
        <div className="space-y-6">
          {/* Match Scorecard */}
          <div className="bg-white rounded-2xl border border-stone-200/90 p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-brand-700" />
                <h3 className="text-sm font-bold text-stone-900">Job Match Scorecard</h3>
              </div>
              <span className="text-xs font-bold px-2.5 py-1 bg-brand-50 text-brand-800 border border-brand-200 rounded-full">
                {candidate.referral_score}% Fit
              </span>
            </div>

            {candidate.best_match ? (
              <div className="space-y-4 pt-2">
                <div>
                  <label className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
                    Target Role
                  </label>
                  <p className="text-sm font-bold text-stone-900 mt-0.5">
                    {candidate.best_match.job_title}
                  </p>
                </div>

                <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-brand-700 h-2 rounded-full"
                    style={{ width: `${Math.min(100, candidate.best_match.match_percent)}%` }}
                  />
                </div>

                {/* Matched Skills */}
                <div>
                  <label className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider">
                    Matched Skills ({candidate.best_match.matched_skills?.length || 0})
                  </label>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {candidate.best_match.matched_skills?.map((skill, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-medium"
                      >
                        ✓ {skill}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Missing Skills */}
                {candidate.best_match.missing_skills && candidate.best_match.missing_skills.length > 0 && (
                  <div>
                    <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      Missing Skills ({candidate.best_match.missing_skills.length})
                    </label>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {candidate.best_match.missing_skills.map((skill, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-slate-100 text-slate-600 rounded-lg text-xs font-medium"
                        >
                          ✕ {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No active job matches found above threshold.</p>
            )}
          </div>

          {/* Candidate Skills List */}
          <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-3">
            <h3 className="text-sm font-bold text-slate-900">Extracted Skills</h3>
            <div className="flex flex-wrap gap-1.5">
              {candidate.parsed_profile?.skills?.map((skill, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 bg-slate-50 text-slate-700 border border-slate-200 rounded-lg text-xs font-medium"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Decision Modal (Approve / Reject) */}
      {decisionModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 capitalize">
              {decisionModal} Referral
            </h3>
            <p className="text-xs text-slate-500">
              {decisionModal === 'approve'
                ? 'Approve this candidate to progress to interview scheduling.'
                : 'Reject this candidate. Please provide a clear note explaining the reason.'}
            </p>

            <textarea
              required={decisionModal === 'reject'}
              rows={4}
              placeholder={
                decisionModal === 'approve'
                  ? 'Optional approval note (e.g. Strong profile, proceeding to screening)'
                  : 'Mandatory reason for rejection (e.g. Lacks required years of cloud experience)'
              }
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
              className="w-full p-3 border border-stone-300 rounded-xl text-xs focus:outline-hidden focus:ring-2 focus:ring-brand-700/20 focus:border-brand-700"
            />

            <div className="flex space-x-3 pt-2">
              <button
                onClick={() => {
                  setDecisionModal(null);
                  setDecisionNote('');
                }}
                disabled={decisionLoading}
                className="flex-1 px-4 py-2 border border-stone-300 rounded-xl text-xs font-semibold text-stone-700 hover:bg-stone-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDecisionSubmit}
                disabled={decisionLoading}
                className={`flex-1 px-4 py-2 rounded-xl text-xs font-semibold text-white shadow-xs ${
                  decisionModal === 'approve'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                {decisionLoading ? 'Saving...' : `Confirm ${decisionModal}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Schedule Interview Modal */}
      {scheduleModalOpen && (
        <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-xl border border-stone-100">
            <div className="flex justify-between items-center border-b border-stone-100 pb-3">
              <h3 className="text-lg font-bold text-stone-900">Schedule Microsoft Teams Interview</h3>
              <button
                onClick={() => {
                  setScheduleModalOpen(false);
                  setScheduleSuccessMsg(null);
                }}
                className="text-stone-400 hover:text-stone-600"
              >
                ✕
              </button>
            </div>

            {scheduleSuccessMsg ? (
              <div className="space-y-4 py-4 text-center">
                <CheckCircle2 className="w-12 h-12 text-emerald-600 mx-auto" />
                <h4 className="text-base font-bold text-stone-900">Meeting Scheduled!</h4>
                <p className="text-xs text-stone-600">{scheduleSuccessMsg}</p>
                <button
                  onClick={() => {
                    setScheduleModalOpen(false);
                    setScheduleSuccessMsg(null);
                  }}
                  className="px-6 py-2 bg-brand-700 hover:bg-brand-800 text-white rounded-xl text-xs font-semibold transition"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleScheduleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">
                    Meeting Subject
                  </label>
                  <input
                    type="text"
                    required
                    value={scheduleData.subject}
                    onChange={(e) => setScheduleData({ ...scheduleData, subject: e.target.value })}
                    className="w-full p-2.5 border border-stone-300 rounded-xl text-xs focus:ring-2 focus:ring-brand-700/20 focus:border-brand-700 focus:outline-hidden"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-stone-700 mb-1">
                      Date & Start Time (Local)
                    </label>
                    <input
                      type="datetime-local"
                      required
                      value={scheduleData.start_time}
                      onChange={(e) => setScheduleData({ ...scheduleData, start_time: e.target.value })}
                      className="w-full p-2.5 border border-stone-300 rounded-xl text-xs focus:ring-2 focus:ring-brand-700/20 focus:border-brand-700 focus:outline-hidden"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-stone-700 mb-1">
                      Duration (Minutes)
                    </label>
                    <select
                      value={scheduleData.duration_minutes}
                      onChange={(e) =>
                        setScheduleData({ ...scheduleData, duration_minutes: Number(e.target.value) })
                      }
                      className="w-full p-2.5 border border-stone-300 rounded-xl text-xs bg-white focus:ring-2 focus:ring-brand-700/20 focus:border-brand-700 focus:outline-hidden"
                    >
                      <option value={30}>30 Minutes</option>
                      <option value={45}>45 Minutes</option>
                      <option value={60}>60 Minutes</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">
                    Interviewer Corporate Email
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="e.g. interviewer@company.com"
                    value={scheduleData.interviewer_email}
                    onChange={(e) =>
                      setScheduleData({ ...scheduleData, interviewer_email: e.target.value })
                    }
                    className="w-full p-2.5 border border-stone-300 rounded-xl text-xs focus:ring-2 focus:ring-brand-700/20 focus:border-brand-700 focus:outline-hidden"
                  />
                </div>

                <div className="pt-3 flex space-x-3">
                  <button
                    type="button"
                    onClick={() => setScheduleModalOpen(false)}
                    className="flex-1 py-2.5 border border-stone-300 rounded-xl text-xs font-semibold text-stone-700 hover:bg-stone-50 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={scheduleLoading}
                    className="flex-1 py-2.5 bg-brand-700 hover:bg-brand-800 text-white rounded-xl text-xs font-semibold shadow-xs flex items-center justify-center space-x-2 transition"
                  >
                    {scheduleLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Schedule & Send Invites</span>}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
