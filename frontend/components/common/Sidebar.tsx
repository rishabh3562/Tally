/**
 * Sidebar Navigation Component
 */

export default function Sidebar() {
  return (
    <aside className="border-r border-gray-200 bg-gray-50 w-64">
      <nav className="p-4">
        {/* TODO: Add navigation menu items */}
        <ul className="space-y-2">
          <li><a href="/dashboard">Dashboard</a></li>
          <li><a href="/transactions">Transactions</a></li>
          <li><a href="/events">Events</a></li>
          <li><a href="/chat">Chat</a></li>
        </ul>
      </nav>
    </aside>
  );
}
