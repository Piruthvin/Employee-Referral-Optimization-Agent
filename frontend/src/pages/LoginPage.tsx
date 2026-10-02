import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { Mail, KeyRound, ArrowRight, ShieldCheck, AlertCircle, Loader2 } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const {
    step,
    email,
    setEmail,
    otp,
    setOtp,
    loading,
    errorMsg,
    successMsg,
    handleRequestOtp,
    handleVerifyOtp,
    resetToEmail,
  } = useAuth();

  return (
    <div className="min-h-screen bg-neutral-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Red & Black Emblem Logo */}
        <div className="w-14 h-14 bg-gradient-to-tr from-brand-800 via-neutral-900 to-black rounded-2xl flex items-center justify-center text-white mx-auto shadow-lg shadow-brand-900/30 mb-4 border border-brand-700/30">
          <ShieldCheck className="w-8 h-8 text-brand-400" />
        </div>
        <h2 className="text-3xl font-extrabold text-neutral-900 tracking-tight">ReferralOS</h2>
        <p className="mt-2 text-sm text-neutral-600 font-medium">
          Enterprise Employee Referral & Recruitment AI Platform
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-xl shadow-neutral-300/40 rounded-2xl border border-neutral-200 sm:px-10">
          {errorMsg && (
            <div
              id="login-error-banner"
              className="mb-4 p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-3 text-rose-800 text-sm"
            >
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div
              id="login-success-banner"
              className="mb-4 p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm"
            >
              {successMsg}
            </div>
          )}

          {step === 'email' ? (
            <form onSubmit={handleRequestOtp} className="space-y-5">
              <div>
                <label className="block text-xs font-semibold text-neutral-700 uppercase tracking-wider mb-2">
                  Zoho Corporate Email
                </label>
                <div className="relative rounded-xl shadow-xs">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-neutral-400">
                    <Mail className="h-5 w-5" />
                  </div>
                  <input
                    id="email-input"
                    type="email"
                    required
                    placeholder="e.g. employee@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={loading}
                    className="block w-full pl-10 pr-3 py-2.5 border border-neutral-300 rounded-xl text-sm placeholder-neutral-400 focus:outline-hidden focus:ring-2 focus:ring-brand-500/25 focus:border-brand-700 transition disabled:bg-neutral-50 text-neutral-900"
                  />
                </div>
                <p className="mt-2 text-xs text-neutral-500">
                  Your role (Employee or Recruiter) is securely determined from Zoho Recruit Users.
                </p>
              </div>

              <button
                id="send-code-btn"
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center space-x-2 py-2.5 px-4 border border-transparent rounded-xl shadow-sm text-sm font-semibold text-white bg-brand-700 hover:bg-brand-800 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-brand-700 transition active:scale-98 disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Sending code...</span>
                  </>
                ) : (
                  <>
                    <span>Send Verification Code</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOtp} className="space-y-5">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-xs font-semibold text-neutral-700 uppercase tracking-wider">
                    6-Digit Verification Code
                  </label>
                  <button
                    id="change-email-btn"
                    type="button"
                    onClick={resetToEmail}
                    className="text-xs text-brand-700 hover:text-brand-800 font-semibold cursor-pointer transition"
                  >
                    Change Email
                  </button>
                </div>

                <div className="relative rounded-xl shadow-xs">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-neutral-400">
                    <KeyRound className="h-5 w-5" />
                  </div>
                  <input
                    id="otp-input"
                    type="text"
                    required
                    maxLength={6}
                    placeholder="123456"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                    disabled={loading}
                    className="block w-full pl-10 pr-3 py-2.5 border border-neutral-300 rounded-xl text-lg tracking-widest text-center font-mono placeholder-neutral-300 focus:outline-hidden focus:ring-2 focus:ring-brand-500/25 focus:border-brand-700 transition disabled:bg-neutral-50 text-neutral-900"
                  />
                </div>
                <p className="mt-2 text-xs text-neutral-600">
                  Enter the one-time code sent to <span className="font-semibold text-neutral-900">{email}</span>.
                </p>
              </div>

              <button
                id="verify-signin-btn"
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center space-x-2 py-2.5 px-4 border border-transparent rounded-xl shadow-sm text-sm font-semibold text-white bg-brand-700 hover:bg-brand-800 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-brand-700 transition active:scale-98 disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Verifying...</span>
                  </>
                ) : (
                  <span>Verify & Sign In</span>
                )}
              </button>
            </form>
          )}

          <div className="mt-6 pt-6 border-t border-neutral-200 text-center">
            <span className="text-xs text-neutral-500">
              Stateless OTP authentication &bull; Protected by enterprise security
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
