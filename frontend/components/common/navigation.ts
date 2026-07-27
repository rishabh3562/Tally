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

/** Single source of truth for app navigation — the desktop sidebar and the
 *  mobile drawer both render from this list so they can never drift. */
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
