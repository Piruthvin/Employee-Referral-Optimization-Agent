import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { Navbar } from './components/Navbar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ReferralModal } from './components/ReferralModal';
import { LoginPage } from './pages/LoginPage';
import { EmployeeDashboard } from './pages/employee/EmployeeDashboard';
import { RecruiterDashboard } from './pages/recruiter/RecruiterDashboard';
import { ApprovalDetailPage } from './pages/recruiter/ApprovalDetailPage';
import { ChatPage } from './pages/chat/ChatPage';

export const App: React.FC = () => {
  const { user } = useAuthStore();
  const [isReferralModalOpen, setIsReferralModalOpen] = useState(false);
  const [employeePoints, setEmployeePoints] = useState<number | undefined>(undefined);

  const isRecruiter = user?.role === 'recruiter' || user?.role === 'hiring_manager';

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 flex flex-col">
        <Navbar
          onOpenReferralModal={() => setIsReferralModalOpen(true)}
          points={employeePoints}
        />

        <main className="flex-1">
          <Routes>
            {/* Public Auth Route */}
            <Route
              path="/login"
              element={user ? <Navigate to="/" replace /> : <LoginPage />}
            />

            {/* Protected Routes */}
            <Route element={<ProtectedRoute />}>
              <Route
                path="/"
                element={
                  isRecruiter ? (
                    <RecruiterDashboard />
                  ) : (
                    <EmployeeDashboard
                      onOpenReferralModal={() => setIsReferralModalOpen(true)}
                      onPointsUpdate={(pts) => setEmployeePoints(pts)}
                    />
                  )
                }
              />

              <Route path="/chat" element={<ChatPage />} />

              {/* Recruiter / Hiring Manager only route */}
              <Route
                element={<ProtectedRoute allowedRoles={['recruiter', 'hiring_manager']} />}
              >
                <Route path="/approvals/:id" element={<ApprovalDetailPage />} />
              </Route>
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {/* Global Referral Submission Modal */}
        <ReferralModal
          isOpen={isReferralModalOpen}
          onClose={() => setIsReferralModalOpen(false)}
        />
      </div>
    </BrowserRouter>
  );
};

export default App;
