/**
 * Header Component
 */

export default function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="container px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">Tally</h1>
            <span className="text-sm text-gray-500">Personal Finance OS</span>
          </div>
          {/* TODO: Add navigation and user menu */}
        </div>
      </div>
    </header>
  );
}
