import { create } from 'zustand';
import type { User } from '../types';

interface AuthState {
  token: string | null;
  user: User | null;
  challengeToken: string | null;
  challengeEmail: string | null;
  isAuthenticated: boolean;
  setChallenge: (challengeToken: string, email: string) => void;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
}

// Security: In-memory store only. JWT token is NEVER written to localStorage or sessionStorage.
export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  challengeToken: null,
  challengeEmail: null,
  isAuthenticated: false,

  setChallenge: (challengeToken: string, email: string) =>
    set({ challengeToken, challengeEmail: email }),

  setAuth: (token: string, user: User) =>
    set({
      token,
      user,
      challengeToken: null,
      challengeEmail: null,
      isAuthenticated: true,
    }),

  logout: () =>
    set({
      token: null,
      user: null,
      challengeToken: null,
      challengeEmail: null,
      isAuthenticated: false,
    }),
}));
