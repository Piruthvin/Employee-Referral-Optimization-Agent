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
    match_percent: number;
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
    setUploadProgress(10);

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
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-100 overflow-hidden transform transition-all">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Refer a Candidate</h3>
            <p className="text-xs text-slate-500">Fast, streamlined candidate referral intake</p>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6">
          {result ? (
            /* Success Card */
            <div className="space-y-6 text-center">
              <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
                <CheckCircle2 className="w-10 h-10" />
              </div>

              <div>
                <h4 className="text-xl font-bold text-slate-900">Referral Submitted!</h4>
                <p className="text-sm text-slate-600 mt-1">
                  Candidate profile has been created and securely synced to Zoho Recruit.
                </p>
              </div>

              <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4 text-left space-y-3">
                <div className="flex justify-between items-center text-sm border-b border-slate-200/60 pb-2">
                  <span className="text-slate-500 font-medium">Status</span>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                    {result.status || 'Pending recruiter approval'}
                  </span>
                </div>

                {result.best_match ? (
                  <div>
                    <div className="flex justify-between items-center text-sm mb-1">
                      <span className="text-slate-500 font-medium">Best Matching Role</span>
                      <span className="font-semibold text-brand-600">
                        {result.best_match.match_percent}% Match
                      </span>
                    </div>
                    <div className="text-sm font-bold text-slate-900">
                      {result.best_match.job_title}
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-2 mt-2 overflow-hidden">
                      <div
                        className="bg-brand-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, result.best_match.match_percent)}%` }}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic">
                    Candidate profile saved. No open jobs currently match the required criteria.
                  </div>
                )}
              </div>

              <div className="flex space-x-3">
                <button
                  onClick={handleReset}
                  className="flex-1 px-4 py-2.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-sm font-semibold rounded-xl transition"
                >
                  Refer Another
                </button>
                <button
                  onClick={handleClose}
                  className="flex-1 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-xl shadow-sm transition"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            /* Referral Form - Exactly 3 Fields */
            <form onSubmit={handleSubmit} className="space-y-4">
              {errorMsg && (
                <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-3 text-rose-700 text-sm">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Field 1: Candidate Name */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Candidate Full Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Jane Doe"
                  value={candidateName}
                  onChange={(e) => setCandidateName(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition disabled:bg-slate-50"
                />
              </div>

              {/* Field 2: Candidate Email */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Candidate Email Address <span className="text-rose-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. jane.doe@example.com"
                  value={candidateEmail}
                  onChange={(e) => setCandidateEmail(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition disabled:bg-slate-50"
                />
              </div>

              {/* Field 3: Resume File (PDF or DOCX, max 5 MB) */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Resume File (PDF / DOCX, max 5 MB) <span className="text-rose-500">*</span>
                </label>
                <div className="relative border-2 border-dashed border-slate-300 hover:border-brand-400 rounded-xl p-4 text-center cursor-pointer transition bg-slate-50/50">
                  <input
                    type="file"
                    required
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    disabled={isSubmitting}
                    onChange={(e) => handleFileChange(e.target.files ? e.target.files[0] : null)}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  {file ? (
                    <div className="flex items-center justify-center space-x-2 text-brand-600 font-medium text-sm">
                      <FileText className="w-5 h-5" />
                      <span className="truncate max-w-xs">{file.name}</span>
                      <span className="text-xs text-slate-400">({(file.size / (1024 * 1024)).toFixed(2)} MB)</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center space-y-1 text-slate-500">
                      <UploadCloud className="w-8 h-8 text-slate-400" />
                      <span className="text-sm font-medium text-slate-700">Click or drag resume here</span>
                      <span className="text-xs text-slate-400">Supported formats: PDF, DOCX (Max 5MB)</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Upload Progress Bar */}
              {isSubmitting && (
                <div className="space-y-1.5 pt-2">
                  <div className="flex justify-between text-xs text-slate-500 font-medium">
                    <span>Analyzing & parsing resume...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-brand-600 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Submit Buttons */}
              <div className="pt-3 flex space-x-3">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={isSubmitting}
                  className="flex-1 px-4 py-2.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-sm font-semibold rounded-xl transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-xl shadow-sm transition flex items-center justify-center space-x-2 disabled:opacity-50"
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
