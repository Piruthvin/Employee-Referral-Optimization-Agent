import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { apiClient } from '../api/client';
import type { User, UserRole } from '../types';

export function decodeJwtPayload(token: string): any {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

export const useAuth = () => {
  const navigate = useNavigate();
  const { setAuth, setChallenge, logout } = useAuthStore();

  const [step, setStep] = useState<'email' | 'otp'>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [challengeToken, setChallengeToken] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleRequestOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setErrorMsg('Please enter a valid corporate email address.');
      return false;
    }

    setLoading(true);
    try {
      const response = await apiClient.post('/api/v1/auth/login/request', {
        email: cleanEmail,
      });

      const data = response.data;

      // Handle email_only development direct login contract (auto-login without OTP screen)
      if (data.auth_mode === 'email_only' || (data.message && data.message.includes('direct login'))) {
        const token = data.access_token || data.challenge_token;
        let user: User | null = data.user;
        if (!user && token) {
          const claims = decodeJwtPayload(token);
          if (claims) {
            user = {
              email: claims.email || cleanEmail,
              role: (claims.role || 'employee') as UserRole,
              name: claims.name || cleanEmail,
              zoho_user_id: claims.zoho_user_id || '',
            };
          }
        }

        if (token && user) {
          setAuth(token, user);
          navigate('/');
          return true;
        }
      }

      // Standard OTP mode flow: transition to OTP verification step
      const tok = data.challenge_token;
      setChallengeToken(tok);
      setChallenge(tok, cleanEmail);
      setStep('otp');
      setSuccessMsg(
        data.message ||
          'Verification code dispatched. Please check your corporate email inbox.'
      );
      return true;
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setErrorMsg(detail || 'Failed to request login code. Please try again.');
      return false;
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMsg(null);

    const cleanOtp = otp.trim();
    if (!cleanOtp || cleanOtp.length !== 6) {
      setErrorMsg('Please enter the 6-digit verification code.');
      return false;
    }

    if (!challengeToken) {
      setErrorMsg('Challenge session expired. Please request a new code.');
      setStep('email');
      return false;
    }

    setLoading(true);
    try {
      const response = await apiClient.post('/api/v1/auth/login/verify', {
        challenge_token: challengeToken,
        otp: cleanOtp,
      });

      const data = response.data;
      const accessToken = data.access_token;
      let user: User = data.user;
      if (!user) {
        user = {
          email: data.email || email,
          role: (data.role || 'employee') as UserRole,
          name: data.name || email,
          zoho_user_id: data.zoho_user_id || '',
        };
      }

      setAuth(accessToken, user);
      navigate('/');
      return true;
    } catch (err: any) {
      // Update challenge token if new token was returned with decremented attempts
      const newTok = err.response?.headers?.['x-new-challenge-token'];
      if (newTok) {
        setChallengeToken(newTok);
      }
      const detail = err.response?.data?.detail;
      setErrorMsg(detail || 'Invalid or expired verification code. Please check and retry.');
      return false;
    } finally {
      setLoading(false);
    }
  };

  const resetToEmail = () => {
    setStep('email');
    setOtp('');
    setErrorMsg(null);
    setSuccessMsg(null);
  };

  return {
    step,
    email,
    setEmail,
    otp,
    setOtp,
    loading,
    errorMsg,
    setErrorMsg,
    successMsg,
    handleRequestOtp,
    handleVerifyOtp,
    resetToEmail,
    logout,
  };
};
