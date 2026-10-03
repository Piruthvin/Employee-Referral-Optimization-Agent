import React, { useState } from 'react';
import { X, UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { apiClient } from '../api/client';

interface ReferralModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface ReferralResult {
  success: boolean;
  candidate_id: string;
  best_match?: {
    job_id?: string;
    job_title: string;
    job_description?: string;
    match_percent: number;
    notes?: string;
    matched_skills?: string[];
    missing_skills?: string[];
  };
  status: string;
  message?: string;
}

export const ReferralModal: React.FC<ReferralModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [candidateName, setCandidateName] = useState('');
  const [candidateEmail, setCandidateEmail] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const [uploadProgress, setUploadProgress] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<ReferralResult | null>(null);
  const [descExpanded, setDescExpanded] = useState(false);

  if (!isOpen) return null;

  const handleFileChange = (selectedFile: File | null) => {
    setErrorMsg(null);
    if (!selectedFile) {
      setFile(null);
      return;
    }

    const validExtensions = ['.pdf', '.docx'];
    const fileName = selectedFile.name.toLowerCase();
    const hasValidExt = validExtensions.some((ext) => fileName.endsWith(ext));

    if (!hasValidExt) {
      setErrorMsg('Please upload a valid PDF or DOCX file.');
      return;
    }

    const maxSize = 5 * 1024 * 1024; // 5 MB
    if (selectedFile.size > maxSize) {
      setErrorMsg('Resume file size must be less than 5 MB.');
      return;
    }

    setFile(selectedFile);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!candidateName.trim()) {
      setErrorMsg('Candidate name is required.');
      return;
    }
    if (!candidateEmail.trim() || !candidateEmail.includes('@')) {
      setErrorMsg('A valid candidate email is required.');
      return;
    }
    if (!file) {
      setErrorMsg('Please select a resume file (PDF or DOCX).');
      return;
    }

    const formData = new FormData();
    formData.append('candidate_name', candidateName.trim());
    formData.append('candidate_email', candidateEmail.trim().toLowerCase());
    formData.append('resume_file', file);

    setIsSubmitting(true);
    setUploadProgress(15);

    try {
      const response = await apiClient.post<ReferralResult>('/api/v1/referral/submit', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percent = Math.round((progressEvent.loaded * 80) / progressEvent.total);
            setUploadProgress(percent);
          }
        },
      });

      setUploadProgress(100);
      setResult(response.data);
      if (onSuccess) {
        onSuccess();
      }
    } catch (err: any) {
      setIsSubmitting(false);
      const status = err.response?.status;
      const detail = err.response?.data?.detail;

      if (status === 409) {
        setErrorMsg(detail || 'This candidate has already been referred or already exists in the system.');
      } else if (status === 422) {
        setErrorMsg(detail || 'The uploaded file appears to be a scanned image. A text-based PDF or DOCX resume is required.');
      } else {
        setErrorMsg(detail || 'Failed to submit candidate referral. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setCandidateName('');
    setCandidateEmail('');
    setFile(null);
    setResult(null);
    setErrorMsg(null);
    setUploadProgress(0);
  };

  const handleClose = () => {
    handleReset();
    onClose();
  };

  return (
    <div
      id="referral-modal-backdrop"
      className="fixed inset-0 z-50 overflow-y-auto bg-neutral-950/60 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-neutral-200 overflow-hidden transform transition-all">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200 bg-neutral-50/80">
          <div>
            <h3 className="text-lg font-bold text-neutral-900">Refer a Candidate</h3>
            <p className="text-xs text-neutral-500">Fast, streamlined candidate referral intake</p>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 text-neutral-400 hover:text-neutral-600 rounded-lg hover:bg-neutral-100 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6">
          {result ? (
            /* Success Card */
            <div id="referral-success-card" className="space-y-6 text-center">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto shadow-inner">
                <CheckCircle2 className="w-10 h-10" />
              </div>

              <div>
                <h4 className="text-xl font-bold text-neutral-900">Referral Submitted!</h4>
                <p className="text-sm text-neutral-600 mt-1">
                  Candidate profile has been created and securely synced to Zoho Recruit.
                </p>
              </div>

              <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-4 text-left space-y-3">
                <div className="flex justify-between items-center text-sm border-b border-neutral-200 pb-2">
                  <span className="text-neutral-500 font-medium">Status</span>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900">
                    {result.status || 'Pending recruiter approval'}
                  </span>
                </div>

                {result.best_match ? (
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between items-center text-sm mb-1">
                        <span className="text-neutral-500 font-medium">Best Matching Role</span>
                        <span className="font-semibold text-brand-700">
                          {result.best_match.match_percent}% Match
                        </span>
                      </div>
                      <div className="text-sm font-bold text-neutral-900">
                        {result.best_match.job_title}
                      </div>
                      {result.best_match.job_id && (
                        <div className="text-[11px] font-mono text-neutral-500 mt-0.5">
                          Job ID: {result.best_match.job_id}
                        </div>
                      )}
                      <div className="w-full bg-neutral-200 rounded-full h-2 mt-2 overflow-hidden">
                        <div
                          className="bg-brand-700 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(100, result.best_match.match_percent)}%` }}
                        />
                      </div>
                    </div>

                    {/* Why this match notes */}
                    {result.best_match.notes && (
                      <div className="p-3 bg-brand-50/70 border border-brand-200/80 rounded-xl text-left">
                        <span className="text-[11px] font-bold text-brand-900 uppercase tracking-wider block">
                          ✨ Why this match:
                        </span>
                        <p className="text-xs text-brand-950 mt-1 leading-relaxed font-medium">
                          {result.best_match.notes}
                        </p>
                      </div>
                    )}

                    {/* Job Description with expand/collapse */}
                    {result.best_match.job_description && (
                      <div className="p-3 bg-white border border-neutral-200 rounded-xl text-left">
                        <span className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider block mb-1">
                          Role Description
                        </span>
                        <p className="text-xs text-neutral-700 leading-relaxed whitespace-pre-line">
                          {descExpanded
                            ? result.best_match.job_description
                            : `${result.best_match.job_description.slice(0, 160)}${result.best_match.job_description.length > 160 ? '...' : ''}`}
                        </p>
                        {result.best_match.job_description.length > 160 && (
                          <button
                            type="button"
                            onClick={() => setDescExpanded(!descExpanded)}
                            className="mt-1 text-xs font-semibold text-brand-700 hover:text-brand-800 transition cursor-pointer"
                          >
                            {descExpanded ? 'Show less' : 'Read full description'}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-neutral-500 italic">
                    Candidate profile saved. No open jobs currently match the required criteria.
                  </div>
                )}
              </div>

              <div className="flex space-x-3">
                <button
                  id="refer-another-btn"
                  onClick={handleReset}
                  className="flex-1 px-4 py-2.5 border border-neutral-300 hover:bg-neutral-50 text-neutral-700 text-sm font-semibold rounded-xl transition cursor-pointer"
                >
                  Refer Another
                </button>
                <button
                  id="referral-done-btn"
                  onClick={handleClose}
                  className="flex-1 px-4 py-2.5 bg-brand-700 hover:bg-brand-800 text-white text-sm font-semibold rounded-xl shadow-sm shadow-brand-700/20 transition cursor-pointer"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            /* Referral Form - Exactly 3 Fields */
            <form id="referral-form" onSubmit={handleSubmit} className="space-y-4">
              {errorMsg && (
                <div
                  id="referral-error-banner"
                  className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-3 text-rose-800 text-sm"
                >
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-600" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Field 1: Candidate Name */}
              <div>
                <label className="block text-xs font-semibold text-neutral-700 uppercase tracking-wider mb-1.5">
                  Candidate Full Name <span className="text-brand-700">*</span>
                </label>
                <input
                  id="candidate-name-input"
                  type="text"
                  required
                  placeholder="e.g. Jane Doe"
                  value={candidateName}
                  onChange={(e) => setCandidateName(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 border border-neutral-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/25 focus:border-brand-700 transition disabled:bg-neutral-50 text-neutral-900"
                />
              </div>

              {/* Field 2: Candidate Email */}
              <div>
                <label className="block text-xs font-semibold text-neutral-700 uppercase tracking-wider mb-1.5">
                  Candidate Email Address <span className="text-brand-700">*</span>
                </label>
                <input
                  id="candidate-email-input"
                  type="email"
                  required
                  placeholder="e.g. jane.doe@example.com"
                  value={candidateEmail}
                  onChange={(e) => setCandidateEmail(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 border border-neutral-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/25 focus:border-brand-700 transition disabled:bg-neutral-50 text-neutral-900"
                />
              </div>

              {/* Field 3: Resume File (PDF or DOCX, max 5 MB) */}
              <div>
                <label className="block text-xs font-semibold text-neutral-700 uppercase tracking-wider mb-1.5">
                  Resume File (PDF / DOCX, max 5 MB) <span className="text-brand-700">*</span>
                </label>
                <div className="relative border-2 border-dashed border-neutral-300 hover:border-brand-600 rounded-xl p-4 text-center cursor-pointer transition bg-neutral-50/60">
                  <input
                    id="candidate-resume-file"
                    type="file"
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    disabled={isSubmitting}
                    onChange={(e) => handleFileChange(e.target.files ? e.target.files[0] : null)}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  {file ? (
                    <div className="flex items-center justify-center space-x-2 text-brand-700 font-medium text-sm">
                      <FileText className="w-5 h-5 text-brand-700" />
                      <span className="truncate max-w-xs">{file.name}</span>
                      <span className="text-xs text-neutral-500">({(file.size / (1024 * 1024)).toFixed(2)} MB)</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center space-y-1 text-neutral-500">
                      <UploadCloud className="w-8 h-8 text-neutral-400" />
                      <span className="text-sm font-medium text-neutral-800">Click or drag resume here</span>
                      <span className="text-xs text-neutral-500">Supported formats: PDF, DOCX (Max 5MB)</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Upload Progress Bar */}
              {isSubmitting && (
                <div className="space-y-1.5 pt-2">
                  <div className="flex justify-between text-xs text-neutral-600 font-medium">
                    <span>Analyzing & parsing resume...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full bg-neutral-200 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-brand-700 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Submit Buttons */}
              <div className="pt-3 flex space-x-3">
                <button
                  id="referral-cancel-btn"
                  type="button"
                  onClick={handleClose}
                  disabled={isSubmitting}
                  className="flex-1 px-4 py-2.5 border border-neutral-300 hover:bg-neutral-50 text-neutral-700 text-sm font-semibold rounded-xl transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  id="referral-submit-btn"
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 px-4 py-2.5 bg-brand-700 hover:bg-brand-800 text-white text-sm font-semibold rounded-xl shadow-sm shadow-brand-700/20 transition flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <span>Submit Referral</span>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
