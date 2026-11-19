/**
 * FIXTURE: the ZongoVita platform administrator the wireframes F51 to F53 are drawn for.
 *
 * Used only in `fixtures` mode (IMS_CONSOLE_SESSION_SOURCE=fixtures). Signed in to the Platform
 * Service, the session is GET /platform/v1/me (src/session/server.ts).
 */
export const staff = {
  name: "Kiran Desai",
  role: "ZongoVita Super Admin",
  initials: "KD",
  unread_notifications: 3,
  enterprises: [
    { code: "ENT-0007", name: "ZongoVita Industries" },
    { code: "ENT-0012", name: "Gokulda Metals Pvt Ltd" },
    { code: "ENT-0009", name: "Deccan Polymers LLP" },
    { code: "ENT-0016", name: "Sunrise Auto Components" },
  ],
};
