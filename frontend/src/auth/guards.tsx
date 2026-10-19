import { Navigate, Outlet, useLocation } from "react-router-dom";

import { PageLoader } from "../components/Feedback";
import { useAuth } from "./AuthContext";

/** Signed in, and the one-time password already replaced. */
export function RequireAuth() {
  const { me, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <PageLoader />;
  if (!me) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (me.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  return <Outlet />;
}
