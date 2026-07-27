"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { X } from "lucide-react";
import { navigationItems } from "./navigation";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <ul className="space-y-1.5">
      {navigationItems.map((item) => {
        const Icon = item.icon;
        const isActive = pathname.startsWith(item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={isActive ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-4 py-3 transition ${
                isActive
                  ? "bg-blue-50 font-medium text-blue-600"
                  : "text-gray-700 hover:bg-gray-100 active:bg-gray-200"
              }`}
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span>{item.name}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function Footer() {
  return (
    <div className="border-t border-gray-200 p-4">
      <p className="text-xs text-gray-500">Personal Finance OS v0.1</p>
    </div>
  );
}

/** Desktop rail. Hidden below `md`, where `MobileNav` takes over. */
export default function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-gray-200 bg-white md:flex">
      <nav className="flex-1 overflow-y-auto p-4">
        <NavLinks />
      </nav>
      <Footer />
    </aside>
  );
}

/** Mobile slide-over drawer, opened from the header's menu button. */
export function MobileNav({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();

  // Any navigation closes the drawer — otherwise the overlay stays over the
  // page the user just tapped through to.
  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div className="md:hidden" aria-hidden={!open}>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-gray-900/40 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
        className={`fixed inset-y-0 left-0 z-50 flex w-[17rem] max-w-[85%] flex-col bg-white shadow-xl transition-transform duration-200 ease-out ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-4">
          <span className="text-lg font-bold text-gray-900">Tally</span>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto p-4">
          <NavLinks onNavigate={onClose} />
        </nav>
        <Footer />
      </div>
    </div>
  );
}
