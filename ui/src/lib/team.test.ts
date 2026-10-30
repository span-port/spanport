import { describe, expect, it } from "vitest";

import { canChangeUser, canLimitProjects, inviteLink, projectAccessLabel, roleLabel, rolesYouCanGive } from "./team";

describe("team helpers", () => {
  it("names roles", () => {
    expect(roleLabel("viewer")).toBe("Viewer");
  });

  it("lets only owners give the owner role", () => {
    expect(rolesYouCanGive("owner")).toEqual(["owner", "admin", "member", "viewer"]);
    expect(rolesYouCanGive("admin")).toEqual(["admin", "member", "viewer"]);
  });

  it("never lets you change yourself, and only owners change owners", () => {
    const owner = { id: "1", role: "owner" as const };
    const admin = { id: "2", role: "admin" as const };

    expect(canChangeUser(owner, owner)).toBe(false);
    expect(canChangeUser(owner, admin)).toBe(true);
    expect(canChangeUser(admin, owner)).toBe(false);
    expect(canChangeUser(undefined, admin)).toBe(false);
  });

  it("limits only members and viewers, and names their projects", () => {
    const projects = [
      { id: "p1", client: "northwind", project: "hr", environment: "production" },
      { id: "p2", client: "globex", project: "tracking", environment: "staging" },
    ];

    expect(canLimitProjects("admin")).toBe(false);
    expect(canLimitProjects("viewer")).toBe(true);
    expect(projectAccessLabel({ all_projects: true, project_ids: [] }, projects)).toBe("All projects");
    expect(projectAccessLabel({ all_projects: false, project_ids: ["p2"] }, projects)).toBe(
      "globex · tracking · staging",
    );
  });

  it("builds the invite link on the UI's own address", () => {
    expect(inviteLink("https://spanport.acme.com", "a/b+c")).toBe(
      "https://spanport.acme.com/accept-invite?token=a%2Fb%2Bc",
    );
  });
});
