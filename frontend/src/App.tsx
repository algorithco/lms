import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import ParentRoute from './components/ParentRoute';
import TeacherRoute from './components/TeacherRoute';
import type { ComponentType } from 'react';

// Keep the public/auth shell small. Feature pages load only when visited,
// avoiding a full LMS bundle on the landing page.
const lazyPage = (load: () => Promise<{ default: ComponentType }>) => lazy(load);
const Analytics = lazyPage(() => import('./pages/Analytics'));
const Arena = lazyPage(() => import('./pages/Arena'));
const Dashboard = lazyPage(() => import('./pages/Dashboard'));
const DuelRoom = lazyPage(() => import('./pages/DuelRoom'));
const EssayLeaderboard = lazyPage(() => import('./pages/EssayLeaderboard'));
const EssayResult = lazyPage(() => import('./pages/EssayResult'));
const EssayTeacherQueue = lazyPage(() => import('./pages/EssayTeacherQueue'));
const EssayTeacherReview = lazyPage(() => import('./pages/EssayTeacherReview'));
const EssayTopics = lazyPage(() => import('./pages/EssayTopics'));
const EssayWrite = lazyPage(() => import('./pages/EssayWrite'));
const Games = lazyPage(() => import('./pages/Games'));
const PlayGame = lazyPage(() => import('./pages/PlayGame'));
const Groups = lazyPage(() => import('./pages/Groups'));
const Imports = lazyPage(() => import('./pages/Imports'));
const Landing = lazyPage(() => import('./pages/Landing'));
const Login = lazyPage(() => import('./pages/Login'));
const MySubscription = lazyPage(() => import('./pages/MySubscription'));
const PanelDashboard = lazyPage(() => import('./pages/PanelDashboard'));
const PanelQuestions = lazyPage(() => import('./pages/PanelQuestions'));
const PanelTestForm = lazyPage(() => import('./pages/PanelTestForm'));
const PanelTests = lazyPage(() => import('./pages/PanelTests'));
const PanelTopics = lazyPage(() => import('./pages/PanelTopics'));
const PanelTuition = lazyPage(() => import('./pages/PanelTuition'));
const PanelUsers = lazyPage(() => import('./pages/PanelUsers'));
const ParentPortal = lazyPage(() => import('./pages/ParentPortal'));
const PasswordReset = lazyPage(() => import('./pages/PasswordReset'));
const PasswordResetConfirm = lazyPage(() => import('./pages/PasswordResetConfirm'));
const MyCertificates = lazyPage(() => import('./pages/MyCertificates'));
const Plans = lazyPage(() => import('./pages/Plans'));
const Pricing = lazyPage(() => import('./pages/Pricing'));
const Profile = lazyPage(() => import('./pages/Profile'));
const Register = lazyPage(() => import('./pages/Register'));
const Results = lazyPage(() => import('./pages/Results'));
const Subscribe = lazyPage(() => import('./pages/Subscribe'));
const TakeTest = lazyPage(() => import('./pages/TakeTest'));
const TeacherDashboard = lazyPage(() => import('./pages/TeacherDashboard'));
const TestDetail = lazyPage(() => import('./pages/TestDetail'));
const TeacherGradebook = lazyPage(() => import('./pages/TeacherGradebook'));
const Tests = lazyPage(() => import('./pages/Tests'));
const SmartTestCreate = lazyPage(() => import('./pages/SmartTestCreate'));
const Tma = lazyPage(() => import('./pages/Tma'));
const Tournaments = lazyPage(() => import('./pages/Tournaments'));
const TournamentLive = lazyPage(() => import('./pages/TournamentLive'));
const EnterpriseDashboard = lazyPage(() => import('./pages/EnterpriseDashboard'));
const VerifyCertificate = lazyPage(() => import('./pages/VerifyCertificate'));
const ScanOMR = lazyPage(() => import('./pages/ScanOMR'));
const TitulScanner = lazyPage(() => import('./pages/TitulScanner'));
const SpeakingTopics = lazyPage(() => import('./pages/SpeakingTopics'));
const SpeakingPractice = lazyPage(() => import('./pages/SpeakingPractice'));
const SpeakingResult = lazyPage(() => import('./pages/SpeakingResult'));
const TeacherAiConverter = lazyPage(() => import('./pages/TeacherAiConverter'));
const TeacherFinanceDashboard = lazyPage(() => import('./pages/TeacherFinanceDashboard'));
const TeacherVocabGenerator = lazyPage(() => import('./pages/TeacherVocabGenerator'));
const EnglishExamInterface = lazyPage(() => import('./pages/tests/EnglishExamInterface'));

import AuthModal from './components/AuthModal';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <ScrollTop />
        <AnimatedRoutes />
        <AuthModal />
      </BrowserRouter>
    </AuthProvider>
  );
}

/** Remounts the route tree on every navigation so .page-enter replays. */
function AnimatedRoutes() {
  const { pathname } = useLocation();
  return (
    <div key={pathname} className="page-enter">
      <Suspense fallback={<p className="route-loading" role="status">Yuklanmoqda…</p>}>
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
        <Route path="/tma/" element={<Tma />} />
          <Route path="/verify" element={<VerifyCertificate />} />
          <Route path="/verify/:number" element={<VerifyCertificate />} />
          {/* Legacy Django URL parity: /certificates/verify/<number>/ */}
          <Route path="/certificates/verify/:number" element={<VerifyCertificate />} />

        <Route element={<ProtectedRoute />}>
          {/* Authentic Cambridge CD-IELTS / BMB CBT Kiosk Mode (distraction-free 100vw x 100vh) */}
          <Route path="/english-exam/:attemptId" element={<EnglishExamInterface />} />
          <Route element={<Layout />}>
            {/* Ratings live inside the app shell so the sidebar/topbar
                (and the way back) never disappear. The API already
                requires auth, so a shell-less public route only 401'd. */}
            <Route path="/essay-leaderboard" element={<EssayLeaderboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/tests" element={<Tests />} />
            <Route path="/tests/create" element={<SmartTestCreate />} />
            <Route path="/tests/run/:id" element={<Navigate to="/tests/:id" replace />} />
            <Route path="/tests/:id" element={<TestDetail />} />
            <Route path="/tests/:id/gradebook" element={<TeacherGradebook />} />
            {/* Legacy /tests/<id>/take/ → detail (starts attempt there) */}
            <Route path="/tests/:id/take" element={<Navigate to="/tests/:id" replace />} />
            <Route path="/tests/take/:id" element={<Navigate to="/tests/:id" replace />} />
            <Route path="/take/:attemptId" element={<TakeTest />} />
            <Route path="/tests/scan-omr" element={<ScanOMR />} />
            <Route path="/scan-omr" element={<Navigate to="/tests/scan-omr" replace />} />
            <Route path="/titul-scanner" element={<TitulScanner />} />
            <Route path="/results" element={<Results />} />
            {/* Legacy /results/<id>/ deep link */}
            <Route path="/results/:id" element={<Results />} />
            <Route path="/certificates" element={<MyCertificates />} />
            {/* AI Speaking Simulator (IELTS & Multi-level) */}
            <Route path="/speaking" element={<SpeakingTopics />} />
            <Route path="/speaking/practice/:topicId" element={<SpeakingPractice />} />
            <Route path="/speaking/result/:id" element={<SpeakingResult />} />
            {/* Essays */}
            <Route path="/essays" element={<EssayTopics />} />
            {/* Legacy password-gate page → topics (gate is inline in write flow) */}
            <Route path="/essays/:topicId/start" element={<Navigate to="/essays" replace />} />
            <Route path="/essays/write/:id" element={<EssayWrite />} />
            <Route path="/essays/result/:id" element={<EssayResult />} />
            {/* Arena */}
            <Route path="/arena" element={<Arena />} />
            <Route path="/arena/:code" element={<DuelRoom />} />
            {/* Tournaments (Sunday Live League) */}
            <Route path="/tournaments" element={<Tournaments />} />
            <Route path="/tournaments/:id/live" element={<TournamentLive />} />
            <Route path="/tournaments/:id" element={<TournamentLive />} />
            {/* Enterprise (B2B SaaS Learning Centers Hub) */}
            <Route path="/enterprise" element={<EnterpriseDashboard />} />
            <Route path="/enterprise/dashboard" element={<EnterpriseDashboard />} />
            {/* Games (kebab-case = legacy Django slugs) */}
            <Route path="/games" element={<Games />} />
            <Route path="/games/leaderboard" element={<Navigate to="/games" replace />} />
            <Route path="/games/imlo-mina" element={<Navigate to="/games/imlo_mina" replace />} />
            <Route path="/games/gazal-puzzle" element={<Navigate to="/games/gazal_puzzle" replace />} />
            <Route path="/games/lugat-match" element={<Navigate to="/games/lugat_match" replace />} />
            <Route path="/games/:slug" element={<PlayGame />} />
            {/* Billing (legacy /subscribe/* shapes) */}
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/plans" element={<Plans />} />
            <Route path="/premium" element={<Plans />} />
            <Route path="/subscribe" element={<Plans />} />
            <Route path="/subscribe/my" element={<Navigate to="/my-subscription" replace />} />
            <Route path="/subscribe/success" element={<Navigate to="/my-subscription" replace />} />
            <Route path="/subscribe/cancel" element={<Navigate to="/subscribe" replace />} />
            <Route path="/subscribe/:planId/subscribe" element={<SubscribeRedirect />} />
            <Route path="/subscribe/:planId" element={<Subscribe />} />
            <Route path="/subscribe/pay" element={<Subscribe />} />
            <Route path="/checkout" element={<Subscribe />} />
            <Route path="/my-subscription" element={<MySubscription />} />
            {/* School */}
            <Route element={<TeacherRoute />}>
              <Route path="/teacher" element={<TeacherDashboard />} />
              <Route path="/teacher/ai-converter" element={<TeacherAiConverter />} />
              <Route path="/teacher/finance" element={<TeacherFinanceDashboard />} />
              <Route path="/teacher/vocab-generator" element={<TeacherVocabGenerator />} />
              <Route path="/panel/ai-converter" element={<Navigate to="/teacher/ai-converter" replace />} />
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
              <Route path="/tests/import" element={<Navigate to="/import" replace />} />
              <Route path="/attendance" element={<Navigate to="/panel" replace />} />
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
              <Route path="/control-panel/tuition" element={<Navigate to="/panel/tuition" replace />} />
              <Route path="/panel/tests" element={<PanelTests />} />
              <Route path="/panel/tests/new" element={<PanelTestForm />} />
              <Route path="/panel/tests/smart-create" element={<SmartTestCreate />} />
              <Route path="/panel/tests/:id/edit" element={<PanelTestForm />} />
              <Route path="/panel/tests/:id/questions" element={<PanelQuestions />} />
              <Route path="/panel/topics" element={<PanelTopics />} />
              <Route path="/panel/tuition" element={<PanelTuition />} />
              <Route path="/panel/users" element={<PanelUsers />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
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
