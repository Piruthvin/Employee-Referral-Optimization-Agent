import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { UserPlus, MessageSquare, LayoutDashboard, LogOut, Award, Shield } from 'lucide-react';

interface NavbarProps {
  onOpenReferralModal: () => void;
  points?: number;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenReferralModal, points }) => {
  const { user, logout } = useAuthStore();
  const location = useLocation();

  const isRecruiter = user?.role === 'recruiter' || user?.role === 'hiring_manager';
  const appName = import.meta.env.VITE_APP_NAME || 'Employee Referral Agent';

  return (
    <header className="bg-white border-b border-neutral-200 sticky top-0 z-30 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand & Nav */}
        <div className="flex items-center space-x-8">
          <Link to="/" className="flex items-center space-x-3 text-neutral-900 transition group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-800 via-neutral-900 to-black flex items-center justify-center text-white shadow-md shadow-brand-900/20 border border-brand-700/30 group-hover:scale-105 transition transform">
              <Shield className="w-5 h-5 text-brand-400" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-neutral-900 leading-tight text-lg tracking-tight">ReferralOS</span>
              <span className="text-xs text-neutral-500 font-medium">{appName}</span>
            </div>
          </Link>

          {user && (
            <nav className="hidden md:flex items-center space-x-1">
              <Link
                to="/"
                className={`px-3 py-2 rounded-lg text-sm font-medium transition flex items-center space-x-2 ${
                  location.pathname === '/'
                    ? 'bg-brand-50 text-brand-800 border border-brand-200/60 font-semibold'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
                }`}
              >
                <LayoutDashboard className="w-4 h-4 text-brand-700" />
                <span>{isRecruiter ? 'Recruiter Dashboard' : 'My Referrals'}</span>
              </Link>

              <Link
                to="/chat"
                className={`px-3 py-2 rounded-lg text-sm font-medium transition flex items-center space-x-2 ${
                  location.pathname === '/chat'
                    ? 'bg-brand-50 text-brand-800 border border-brand-200/60 font-semibold'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
                }`}
              >
                <MessageSquare className="w-4 h-4 text-brand-700" />
                <span>AI Chat Assistant</span>
              </Link>
            </nav>
          )}
        </div>

        {/* User Actions */}
        {user ? (
          <div className="flex items-center space-x-4">
            {/* Points pill for employee */}
            {!isRecruiter && points !== undefined && (
              <div className="hidden sm:flex items-center space-x-1.5 bg-amber-50 text-amber-900 border border-amber-200 px-3 py-1.5 rounded-full text-xs font-semibold shadow-xs">
                <Award className="w-4 h-4 text-amber-600" />
                <span>{points} Points</span>
              </div>
            )}

            {/* Refer a Candidate Button */}
            <button
              id="refer-candidate-btn"
              onClick={onOpenReferralModal}
              className="inline-flex items-center space-x-2 bg-brand-700 hover:bg-brand-800 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-sm shadow-brand-700/20 transition transform active:scale-95 cursor-pointer"
            >
              <UserPlus className="w-4 h-4" />
              <span>Refer Candidate</span>
            </button>

            {/* Role & Profile Badge */}
            <div className="hidden lg:flex flex-col text-right">
              <span className="text-xs font-semibold text-neutral-900">{user.name}</span>
              <span className="text-[11px] capitalize text-neutral-500 font-medium">
                {user.role.replace('_', ' ')}
              </span>
            </div>

            {/* Sign Out Button */}
            <button
              onClick={logout}
              title="Sign Out"
              className="p-2 text-neutral-500 hover:text-brand-700 hover:bg-brand-50 rounded-lg transition cursor-pointer"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="text-sm font-semibold text-brand-700 hover:text-brand-800 transition"
          >
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
};
