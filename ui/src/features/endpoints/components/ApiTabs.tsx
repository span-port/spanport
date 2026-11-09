import { NavLink, useLocation } from "react-router";

import { COMING_LATER } from "../../../constants/storage";
import { API_TABS } from "../../../constants/traces";

/** The APIs screens' tabs (Overview, Deploys, Service map), keeping the project and range. */
export function ApiTabs() {
  const { search } = useLocation();
  return (
    <nav className="tabs" aria-label="APIs sections">
      {API_TABS.map((tab) =>
        tab.path === null ? (
          <button key={tab.key} type="button" className="tab" disabled title={COMING_LATER}>
            {tab.label}
          </button>
        ) : (
          <NavLink key={tab.key} className="tab" to={`${tab.path}${search}`} end>
            {tab.label}
          </NavLink>
        ),
      )}
    </nav>
  );
}
