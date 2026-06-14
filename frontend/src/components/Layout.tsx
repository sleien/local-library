import { type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  BookMarked,
  Boxes,
  HandHelping,
  Moon,
  PlusCircle,
  ScanLine,
  Settings,
  Sun,
  Users,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { useTheme } from "@/theme/ThemeProvider";
import { cn } from "@/lib/utils";
import { Button } from "./ui";

const nav = [
  { to: "/", label: "Library", icon: BookMarked, end: true },
  { to: "/add", label: "Add", icon: PlusCircle, end: false },
  { to: "/scan", label: "Scan", icon: ScanLine, end: false },
  { to: "/people", label: "People", icon: Users, end: false },
  { to: "/loans", label: "Loans", icon: HandHelping, end: false },
  { to: "/locations", label: "Locations", icon: Boxes, end: false },
];

// Items surfaced in the mobile bottom bar (the rest live behind the header).
const mobileNav = nav.filter((n) => ["/", "/add", "/scan", "/people", "/loans"].includes(n.to));

// Routes that mutate the collection; hidden for read-only (viewer) households.
const WRITE_ROUTES = ["/add", "/scan"];

export function Layout({ children }: { children: ReactNode }) {
  const { me, household, setHouseholdId, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();

  const canWrite = household?.role !== "viewer";
  const sideNav = canWrite ? nav : nav.filter((n) => !WRITE_ROUTES.includes(n.to));
  const bottomNav = canWrite ? mobileNav : mobileNav.filter((n) => !WRITE_ROUTES.includes(n.to));

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-card md:flex">
        <div className="flex items-center gap-2 px-5 py-4 text-lg font-semibold">
          <img src="/icon.svg" className="h-7 w-7" alt="" />
          Bibliothek
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {sideNav.map((item) => (
            <SideLink key={item.to} {...item} />
          ))}
          <SideLink to="/settings" label="Settings" icon={Settings} end={false} />
        </nav>
        <div className="border-t p-3 text-sm text-muted-foreground">{me?.user.display_name}</div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-2 border-b bg-card/80 px-4 py-2.5 backdrop-blur">
          <span className="font-semibold md:hidden">Bibliothek</span>
          <div className="ml-auto flex items-center gap-2">
            {me && me.households.length > 0 && (
              <select
                value={household?.id ?? ""}
                onChange={(e) => setHouseholdId(Number(e.target.value))}
                className="h-9 max-w-[10rem] rounded-md border border-input bg-background px-2 text-sm"
                data-tour="household"
              >
                {me.households.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.name}
                  </option>
                ))}
              </select>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggle}
              aria-label="Toggle theme"
              data-tour="theme"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Settings"
              onClick={() => navigate("/settings")}
            >
              <Settings className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="hidden md:inline-flex"
              aria-label="Log out"
              onClick={() => logout()}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-5 md:pb-8">{children}</main>
      </div>

      {/* Mobile bottom navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex border-t bg-card safe-bottom md:hidden">
        {bottomNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px]",
                isActive ? "text-primary" : "text-muted-foreground",
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function SideLink({
  to,
  label,
  icon: Icon,
  end,
}: {
  to: string;
  label: string;
  icon: typeof BookMarked;
  end: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent",
        )
      }
    >
      <Icon className="h-4 w-4" />
      {label}
    </NavLink>
  );
}
