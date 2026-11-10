import { Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { RequireRole } from "./components/RequireRole";
import { HomePage } from "./pages/public/HomePage";
import { LoginPage } from "./pages/public/LoginPage";
import { TournamentPage } from "./pages/public/TournamentPage";
import { MatchPage } from "./pages/public/MatchPage";
import { TeamPage } from "./pages/public/TeamPage";
import { OrganizerHome } from "./pages/organizer/OrganizerHome";
import { CreateTournamentPage } from "./pages/organizer/CreateTournamentPage";
import { ManageTournamentPage } from "./pages/organizer/ManageTournamentPage";
import { CaptainHome } from "./pages/captain/CaptainHome";
import { ApplyPage } from "./pages/captain/ApplyPage";
import { RosterPage } from "./pages/captain/RosterPage";
import { LineupPage } from "./pages/captain/LineupPage";
import { JudgeHome } from "./pages/judge/JudgeHome";
import { ProtocolPage } from "./pages/judge/ProtocolPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Гость */}
        <Route index element={<HomePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="tournaments/:id" element={<TournamentPage />} />
        <Route path="tournaments/:id/teams/:teamId" element={<TeamPage />} />
        <Route path="matches/:id" element={<MatchPage />} />

        {/* Организатор */}
        <Route
          path="organizer"
          element={
            <RequireRole role="organizer" allowWithoutRole>
              <OrganizerHome />
            </RequireRole>
          }
        />
        <Route
          path="organizer/tournaments/new"
          element={
            <RequireRole role="organizer">
              <CreateTournamentPage />
            </RequireRole>
          }
        />
        <Route
          path="organizer/tournaments/:id"
          element={
            <RequireRole role="organizer">
              <ManageTournamentPage />
            </RequireRole>
          }
        />

        {/* Капитан */}
        <Route
          path="captain"
          element={
            <RequireRole role="captain" allowWithoutRole>
              <CaptainHome />
            </RequireRole>
          }
        />
        <Route
          path="captain/apply"
          element={
            <RequireRole role="captain" allowWithoutRole>
              <ApplyPage />
            </RequireRole>
          }
        />
        <Route
          path="captain/entries/:entryId"
          element={
            <RequireRole role="captain">
              <RosterPage />
            </RequireRole>
          }
        />
        <Route
          path="captain/matches/:id"
          element={
            <RequireRole role="captain">
              <LineupPage />
            </RequireRole>
          }
        />

        {/* Судья */}
        <Route
          path="judge"
          element={
            <RequireRole role="judge">
              <JudgeHome />
            </RequireRole>
          }
        />
        <Route
          path="judge/matches/:id"
          element={
            <RequireRole role="judge">
              <ProtocolPage />
            </RequireRole>
          }
        />

        <Route
          path="*"
          element={
            <div className="container page">
              <div className="card center stack">
                <h2>Страница не найдена</h2>
                <div>
                  <Link to="/" className="btn">
                    На главную
                  </Link>
                </div>
              </div>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
