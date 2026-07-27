import {
  BarChart3,
  TrendingDown,
  MessageCircle,
  Upload,
  Banknote,
  History,
  PieChart,
  Layers,
  ListChecks,
  BookMarked,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  name: string;
  href: string;
  icon: LucideIcon;
};

/** Single source of truth for app navigation — the desktop sidebar, the mobile
 *  drawer and the mobile tab bar all render from this list so they can't drift. */
export const navigationItems: NavItem[] = [
  { name: "Dashboard", href: "/dashboard", icon: BarChart3 },
  { name: "Accounts", href: "/accounts", icon: Banknote },
  { name: "Transactions", href: "/transactions", icon: TrendingDown },
  { name: "Triage", href: "/triage", icon: ListChecks },
  { name: "Groups", href: "/groups", icon: Layers },
  { name: "Case Studies", href: "/events", icon: BookMarked },
  { name: "Upload", href: "/upload", icon: Upload },
  { name: "Jobs", href: "/jobs", icon: History },
  { name: "Insights", href: "/insights", icon: PieChart },
  { name: "Chat", href: "/chat", icon: MessageCircle },
];

/** The four screens worth a permanent thumb-reachable tab on a phone. Everything
 *  else stays one tap away in the drawer. Order matters — this is the bar. */
const TAB_HREFS = ["/dashboard", "/transactions", "/insights", "/chat"];

// filter, not a non-null assertion: renaming an href above should drop a tab,
// not throw at module load and take the whole app down.
export const tabBarItems: NavItem[] = TAB_HREFS.map((href) =>
  navigationItems.find((i) => i.href === href)
).filter((i): i is NavItem => Boolean(i));
