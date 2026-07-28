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
  /** One line on what the screen is for. The name alone is enough in a sidebar
   *  you already know; the home launcher shows this so a screen you've never
   *  opened says what it does before you tap it. */
  description: string;
};

/** Single source of truth for app navigation — the desktop sidebar, the mobile
 *  drawer, the mobile tab bar and the home launcher all render from this list so
 *  they can't drift. */
export const navigationItems: NavItem[] = [
  { name: "Dashboard", href: "/dashboard", icon: BarChart3, description: "Where your money went, at a glance" },
  { name: "Accounts", href: "/accounts", icon: Banknote, description: "The banks and cards you've added" },
  { name: "Transactions", href: "/transactions", icon: TrendingDown, description: "Every payment, searchable" },
  { name: "Triage", href: "/triage", icon: ListChecks, description: "Label the merchants Tally couldn't place" },
  { name: "Groups", href: "/groups", icon: Layers, description: "Payments clubbed together, by hand or automatically" },
  { name: "Case Studies", href: "/events", icon: BookMarked, description: "A trip or occasion, totalled" },
  { name: "Upload", href: "/upload", icon: Upload, description: "Add a bank or UPI statement" },
  { name: "Jobs", href: "/jobs", icon: History, description: "What Tally imported, and what it found" },
  { name: "Insights", href: "/insights", icon: PieChart, description: "Jumps, repeats and habits worth knowing" },
  { name: "Chat", href: "/chat", icon: MessageCircle, description: "Ask a question — or tell it to categorize" },
];

/** The four screens worth a permanent thumb-reachable tab on a phone. Everything
 *  else stays one tap away in the drawer. Order matters — this is the bar. */
const TAB_HREFS = ["/dashboard", "/transactions", "/insights", "/chat"];

// filter, not a non-null assertion: renaming an href above should drop a tab,
// not throw at module load and take the whole app down.
export const tabBarItems: NavItem[] = TAB_HREFS.map((href) =>
  navigationItems.find((i) => i.href === href)
).filter((i): i is NavItem => Boolean(i));
