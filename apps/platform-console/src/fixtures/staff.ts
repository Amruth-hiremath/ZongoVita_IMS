/**
 * FIXTURE: the ZongoVita platform administrator the wireframes F51 to F53 are drawn for.
 *
 * Temporary. The Platform Console signs staff in against the Platform Service with mandatory MFA
 * (LLD 6.2, 15) and reads /platform/v1 through its own BFF; none of that exists yet.
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
