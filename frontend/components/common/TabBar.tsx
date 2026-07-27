"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { tabBarItems } from "./navigation";

/** Thumb-reachable bottom tabs for the four main screens — phones only.
 *  Below `md` the sidebar is a drawer, and opening a drawer to move between the
 *  screens you use constantly is a tap too many; the tab bar makes the app feel
 *  native. Everything else still lives in the drawer. */
export default function TabBar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main"
      className="shrink-0 border-t border-gray-200 bg-white md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="flex">
        {tabBarItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname.startsWith(item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition active:bg-gray-100 ${
                  isActive ? "text-blue-600" : "text-gray-500"
                }`}
              >
                <Icon
                  className={`h-5 w-5 transition-transform ${
                    isActive ? "scale-110" : ""
                  }`}
                />
                <span>{item.name}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
