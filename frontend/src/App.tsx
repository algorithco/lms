import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import ParentRoute from './components/ParentRoute';
import TeacherRoute from './components/TeacherRoute';
import Analytics from './pages/Analytics';
import Arena from './pages/Arena';
import Dashboard from './pages/Dashboard';
import DuelRoom from './pages/DuelRoom';
import EssayLeaderboard from './pages/EssayLeaderboard';
import EssayResult from './pages/EssayResult';
import EssayTeacherQueue from './pages/EssayTeacherQueue';
import EssayTeacherReview from './pages/EssayTeacherReview';
import EssayTopics from './pages/EssayTopics';
import EssayWrite from './pages/EssayWrite';
import Games from './pages/Games';
import PlayGame from './pages/PlayGame';
import Groups from './pages/Groups';
import Imports from './pages/Imports';
import Landing from './pages/Landing';
import Login from './pages/Login';
import MySubscription from './pages/MySubscription';
import PanelDashboard from './pages/PanelDashboard';
import PanelQuestions from './pages/PanelQuestions';
import PanelTestForm from './pages/PanelTestForm';
import PanelTests from './pages/PanelTests';
import PanelTopics from './pages/PanelTopics';
import PanelUsers from './pages/PanelUsers';
import ParentPortal from './pages/ParentPortal';
import PasswordReset from './pages/PasswordReset';
import PasswordResetConfirm from './pages/PasswordResetConfirm';
import MyCertificates from './pages/MyCertificates';
import Plans from './pages/Plans';
import Register from './pages/Register';
import Results from './pages/Results';
import Subscribe from './pages/Subscribe';
import TakeTest from './pages/TakeTest';
import TeacherDashboard from './pages/TeacherDashboard';
import TestDetail from './pages/TestDetail';
import Tests from './pages/Tests';
import Tma from './pages/Tma';
import VerifyCertificate from './pages/VerifyCertificate';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <ScrollTop />
        <AnimatedRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}

/** Remounts the route tree on every navigation so .page-enter replays. */
function AnimatedRoutes() {
  const { pathname } = useLocation();
  return (
    <div key={pathname} className="page-enter">
      <Routes>
        {/* Public */}
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/password-reset" element={<PasswordReset />} />
        <Route path="/password-reset/confirm/:uid/:token" element={<PasswordResetConfirm />} />
        {/* Old Django emailed link shape → SPA confirm */}
        <Route path="/password-reset/:uid/:token" element={<PasswordResetConfirm />} />
        <Route path="/password-reset/done" element={<Navigate to="/password-reset" replace />} />
        <Route path="/password-reset/complete" element={<Navigate to="/login" replace />} />
        {/* Telegram Mini App shell (bot web_app button points at /tma/) */}
        <Route path="/tma" element={<Tma />} />
        <Route path="/password-reset/confirm/:uid/:token" element={<PasswordResetConfirm />} />
          <Route path="/verify" element={<VerifyCertificate />} />
          <Route path="/verify/:number" element={<VerifyCertificate />} />
          {/* Legacy Django URL parity: /certificates/verify/<number>/ */}
          <Route path="/certificates/verify/:number" element={<VerifyCertificate />} />
          <Route path="/essay-leaderboard" element={<EssayLeaderboard />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/tests" element={<Tests />} />
            <Route path="/tests/:id" element={<TestDetail />} />
            {/* Legacy /tests/<id>/take/ → detail (starts attempt there) */}
            <Route path="/tests/:id/take" element={<Navigate to="/tests/:id" replace />} />
            <Route path="/take/:attemptId" element={<TakeTest />} />
            <Route path="/results" element={<Results />} />
            {/* Legacy /results/<id>/ deep link */}
            <Route path="/results/:id" element={<Results />} />
            <Route path="/certificates" element={<MyCertificates />} />
            {/* Essays */}
            <Route path="/essays" element={<EssayTopics />} />
            {/* Legacy password-gate page → topics (gate is inline in write flow) */}
            <Route path="/essays/:topicId/start" element={<Navigate to="/essays" replace />} />
            <Route path="/essays/write/:id" element={<EssayWrite />} />
            <Route path="/essays/result/:id" element={<EssayResult />} />
            {/* Arena */}
            <Route path="/arena" element={<Arena />} />
            <Route path="/arena/:code" element={<DuelRoom />} />
            {/* Games (kebab-case = legacy Django slugs) */}
            <Route path="/games" element={<Games />} />
            <Route path="/games/leaderboard" element={<Navigate to="/games" replace />} />
            <Route path="/games/imlo-mina" element={<Navigate to="/games/imlo_mina" replace />} />
            <Route path="/games/gazal-puzzle" element={<Navigate to="/games/gazal_puzzle" replace />} />
            <Route path="/games/lugat-match" element={<Navigate to="/games/lugat_match" replace />} />
            <Route path="/games/:slug" element={<PlayGame />} />
            {/* Billing (legacy /subscribe/* shapes) */}
            <Route path="/subscribe" element={<Plans />} />
            <Route path="/subscribe/my" element={<Navigate to="/my-subscription" replace />} />
            <Route path="/subscribe/success" element={<Navigate to="/my-subscription" replace />} />
            <Route path="/subscribe/cancel" element={<Navigate to="/subscribe" replace />} />
            <Route path="/subscribe/:planId/subscribe" element={<SubscribeRedirect />} />
            <Route path="/subscribe/:planId" element={<Subscribe />} />
            <Route path="/my-subscription" element={<MySubscription />} />
            {/* School */}
            <Route element={<TeacherRoute />}>
              <Route path="/teacher" element={<TeacherDashboard />} />
              {/* Legacy /teacher/dashboard/ */}
              <Route path="/teacher/dashboard" element={<Navigate to="/teacher" replace />} />
              <Route path="/analytics" element={<Analytics />} />
              {/* Legacy /teacher/analytics/ */}
              <Route path="/teacher/analytics" element={<Navigate to="/analytics" replace />} />
              <Route path="/groups" element={<Groups />} />
              {/* Legacy group CRUD pages → Groups hub (modal states) */}
              <Route path="/groups/create" element={<Navigate to="/groups" replace />} />
              <Route path="/groups/:groupId" element={<Navigate to="/groups" replace />} />
              <Route path="/groups/:groupId/edit" element={<Navigate to="/groups" replace />} />
              <Route path="/groups/:groupId/delete" element={<Navigate to="/groups" replace />} />
              {/* Teacher essay review (parity with /essays/teacher/*) */}
              <Route path="/teacher/essays" element={<EssayTeacherQueue />} />
              <Route path="/teacher/essays/:id/review" element={<EssayTeacherReview />} />
              <Route path="/essays/teacher/queue" element={<Navigate to="/teacher/essays" replace />} />
              <Route path="/essays/teacher/:sid/review" element={<TeacherReviewRedirect />} />
              <Route path="/import" element={<Imports />} />
              {/* Legacy import pages → Imports hub */}
              <Route path="/import/students" element={<Navigate to="/import" replace />} />
              <Route path="/import/tests" element={<Navigate to="/import" replace />} />
            </Route>
            <Route element={<ParentRoute />}>
              <Route path="/parent" element={<ParentPortal />} />
            </Route>
            {/* Legacy standalone pages → SPA equivalents */}
            <Route path="/essays/submit" element={<Navigate to="/essays" replace />} />
            <Route path="/manage-teachers" element={<Navigate to="/panel/users" replace />} />
            {/* Panel */}
            <Route element={<AdminRoute />}>
              <Route path="/panel" element={<PanelDashboard />} />
              {/* Legacy /control-panel/* mount → /panel/* */}
              <Route path="/control-panel" element={<Navigate to="/panel" replace />} />
              <Route path="/control-panel/tests" element={<Navigate to="/panel/tests" replace />} />
              <Route path="/control-panel/tests/create" element={<Navigate to="/panel/tests/new" replace />} />
              <Route path="/control-panel/tests/:id/edit" element={<PanelTestEditRedirect />} />
              <Route path="/control-panel/tests/:id/questions" element={<PanelQuestionsRedirect />} />
              <Route path="/control-panel/essay-topics" element={<Navigate to="/panel/topics" replace />} />
              <Route path="/control-panel/essay-topics/create" element={<Navigate to="/panel/topics" replace />} />
              <Route path="/control-panel/essay-topics/:id/edit" element={<Navigate to="/panel/topics" replace />} />
              <Route path="/control-panel/users" element={<Navigate to="/panel/users" replace />} />
              <Route path="/panel/tests" element={<PanelTests />} />
              <Route path="/panel/tests/new" element={<PanelTestForm />} />
              <Route path="/panel/tests/:id/edit" element={<PanelTestForm />} />
              <Route path="/panel/tests/:id/questions" element={<PanelQuestions />} />
              <Route path="/panel/topics" element={<PanelTopics />} />
              <Route path="/panel/users" element={<PanelUsers />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

/** Legacy /subscribe/<id>/subscribe/ → /subscribe/<id> (param passthrough). */
function SubscribeRedirect() {
  const { planId } = useParams();
  return <Navigate to={`/subscribe/${planId}`} replace />;
}

/** Legacy /essays/teacher/<id>/review/ → /teacher/essays/<id>/review/. */
function TeacherReviewRedirect() {
  const { sid } = useParams();
  return <Navigate to={`/teacher/essays/${sid}/review`} replace />;
}

/** Legacy /control-panel/tests/<id>/* → /panel/tests/<id>/*. */
function PanelTestEditRedirect() {
  const { id } = useParams();
  return <Navigate to={`/panel/tests/${id}/edit`} replace />;
}
function PanelQuestionsRedirect() {
  const { id } = useParams();
  return <Navigate to={`/panel/tests/${id}/questions`} replace />;
}

/** New page starts at the top (except same-page anchor jumps). */
function ScrollTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, [pathname, hash]);
  return null;
}
