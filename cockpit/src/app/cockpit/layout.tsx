import Link from "next/link";

export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden">
      <nav className="w-48 shrink-0 border-r border-border bg-sidebar flex flex-col gap-1 p-3">
        <p className="px-2 py-1 text-xs font-semibold text-sidebar-foreground/50 uppercase tracking-wider mb-1">
          BizBrain
        </p>
        <NavLink href="/cockpit">Home</NavLink>
        <NavLink href="/cockpit/chat">Chat</NavLink>
        <NavLink href="/cockpit/approvals">Approvals</NavLink>
        <NavLink href="/cockpit/activity">Activity</NavLink>
        <NavLink href="/cockpit/clients">Clients</NavLink>
        <NavLink href="/cockpit/integrations">Integrations</NavLink>
      </nav>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="rounded-md px-2 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
    >
      {children}
    </Link>
  );
}
