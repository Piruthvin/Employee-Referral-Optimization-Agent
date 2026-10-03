export type UserRole = 'employee' | 'recruiter' | 'hiring_manager';

export interface User {
  email: string;
  role: UserRole;
  name: string;
  zoho_user_id: string;
}

export interface CandidateReferral {
  candidate_id: string;
  full_name: string;
  email: string;
  candidate_status: string;
  approval_status: 'Pending' | 'Approved' | 'Rejected';
  referred_by: string;
  referred_date: string;
  referral_score: number;
  approval_note?: string;
  current_employer?: string;
  current_job_title?: string;
  experience_in_years?: number;
  skill_set?: string;
  best_match?: {
    job_id?: string;
    job_title: string;
    match_percent: number;
    job_description?: string;
    notes?: string;
    matched_skills?: string[];
    missing_skills?: string[];
    experience_fit?: boolean;
  };
}

export interface CandidateDetail {
  candidate_id: string;
  full_name: string;
  email: string;
  alternate_email?: string;
  phone?: string;
  candidate_status: string;
  approval_status: 'Pending' | 'Approved' | 'Rejected';
  approval_note?: string;
  referred_by: string;
  referred_date: string;
  referral_score: number;
  identity_mismatch?: boolean;
  parsed_profile?: {
    headline?: string;
    summary?: string;
    total_experience_years?: number;
    current_employer?: string;
    current_job_title?: string;
    notice_period?: string;
    skills?: string[];
    education?: Array<{
      degree?: string;
      field_of_study?: string;
      institution?: string;
      start_year?: string;
      end_year?: string;
      grade?: string;
    }>;
    experience?: Array<{
      job_title: string;
      company: string;
      start_date?: string;
      end_date?: string;
      is_current?: boolean;
      description?: string;
    }>;
    links?: {
      linkedin?: string;
      github?: string;
      portfolio?: string;
    };
  };
  best_match?: {
    job_id?: string;
    job_title: string;
    match_percent: number;
    job_description?: string;
    notes?: string;
    matched_skills?: string[];
    missing_skills?: string[];
    experience_fit?: boolean;
  };
}

export interface EmployeePoints {
  employee_email: string;
  total_referrals: number;
  approved_referrals: number;
  points: number;
}

export interface DashboardMetrics {
  total_referrals: number;
  pending_approval: number;
  approved_referrals: number;
  rejected_referrals: number;
  interviews_scheduled: number;
  overall_conversion_rate: number;
  avg_approval_time_days: number;
}

export interface FunnelStage {
  stage: string;
  count: number;
  conversion_from_previous: number;
}

export interface OverdueReferral {
  candidate_id: string;
  candidate_name: string;
  referred_by: string;
  referred_date: string;
  days_pending: number;
  referral_score: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: Date;
  isStreaming?: boolean;
  error?: boolean;
}
