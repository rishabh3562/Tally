"use client";

import { useAuth } from "@/hooks/useAuth";
import { useRouter } from "next/navigation";
import { LogOut, Menu, User } from "lucide-react";
import { useState } from "react";

export default function Header({
  user,
  onOpenNav,
}: {
  user: any;
  onOpenNav?: () => void;
}) {
  const router = useRouter();
  const { logout } = useAuth();
  const [showMenu, setShowMenu] = useState(false);

  const handleLogout = async () => {
    await logout();
    router.push("/auth/login");
  };

  return (
    <header
      className="border-b border-gray-200 bg-white shadow-sm"
      style={{ paddingTop: "env(safe-area-inset-top)" }}
    >
      <div className="px-4 py-3 md:px-6 md:py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <button
              onClick={onOpenNav}
              aria-label="Open menu"
              className="-ml-1 rounded-lg p-2 text-gray-700 transition hover:bg-gray-100 md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="text-xl font-bold text-gray-900">Tally</h1>
          </div>
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              aria-label="Account menu"
              className="flex items-center gap-2 rounded-lg p-2 transition hover:bg-gray-100"
            >
              <User className="h-5 w-5 text-gray-600" />
              <span className="hidden max-w-[10rem] truncate text-sm text-gray-700 sm:inline">
                {user?.email?.split("@")[0]}
              </span>
            </button>
            {showMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg z-50">
                <div className="p-4 border-b">
                  <p className="text-sm font-medium text-gray-900">{user?.email}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2 transition"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
