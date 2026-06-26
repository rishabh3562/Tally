"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, TrendingDown, FileText, MessageCircle, Upload } from "lucide-react";

const navigationItems = [
  {
    name: "Dashboard",
    href: "/dashboard",
    icon: BarChart3,
  },
  {
    name: "Transactions",
    href: "/transactions",
    icon: TrendingDown,
  },
  {
    name: "Upload",
    href: "/upload",
    icon: Upload,
  },
  {
    name: "Chat",
    href: "/chat",
    icon: MessageCircle,
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="border-r border-gray-200 bg-white w-64 flex flex-col">
      <nav className="p-4 flex-1">
        <ul className="space-y-2">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition ${
                    isActive
                      ? "bg-blue-50 text-blue-600 font-medium"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="p-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">Personal Finance OS v0.1</p>
      </div>
    </aside>
  );
}
