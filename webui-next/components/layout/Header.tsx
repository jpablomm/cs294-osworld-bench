"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, PlayCircle, Trophy, Scale } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/api/queries";
import { Badge } from "@/components/ui/badge";

const navigation = [
  { name: "Dashboard", href: "/", icon: BarChart3 },
  { name: "Launch", href: "/launch", icon: PlayCircle },
  { name: "Leaderboard", href: "/leaderboard", icon: Trophy },
  { name: "Compare", href: "/compare", icon: Scale },
];

export function Header() {
  const pathname = usePathname();
  const { data: health } = useHealth();

  const allHealthy =
    health?.green_agent.healthy &&
    health?.white_agent.healthy &&
    health?.database.healthy;

  // Get status message with details
  const getStatusMessage = () => {
    if (!health) return "Checking...";
    if (allHealthy) return "All Systems Operational";

    const issues = [];
    if (!health.green_agent.healthy) issues.push("Green Agent");
    if (!health.white_agent.healthy) issues.push("White Agent");
    if (!health.database.healthy) issues.push("Database");

    return `Issues: ${issues.join(", ")}`;
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center">
        {/* Logo */}
        <Link href="/" className="mr-6 flex items-center space-x-2">
          <Activity className="h-6 w-6 text-green-agent" />
          <span className="hidden font-bold sm:inline-block">
            OSWorld Agent
          </span>
        </Link>

        {/* Navigation */}
        <nav className="flex flex-1 items-center space-x-6 text-sm font-medium">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center space-x-2 transition-colors hover:text-foreground/80",
                  isActive
                    ? "text-foreground"
                    : "text-foreground/60"
                )}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* System Status */}
        <div className="flex items-center space-x-4">
          {health && (
            <Badge
              variant={allHealthy ? "default" : "destructive"}
              className={cn(
                "transition-colors cursor-help",
                allHealthy && "bg-success/10 text-success hover:bg-success/20"
              )}
              title={allHealthy ? "All services are running normally" :
                `${!health.green_agent.healthy ? `Green Agent: ${health.green_agent.error || "Offline"}\n` : ""}${!health.white_agent.healthy ? `White Agent: ${health.white_agent.error || "Offline"}\n` : ""}${!health.database.healthy ? `Database: ${health.database.error || "Offline"}` : ""}`}
            >
              <div
                className={cn(
                  "mr-2 h-2 w-2 rounded-full",
                  allHealthy ? "bg-success" : "bg-destructive"
                )}
              />
              {getStatusMessage()}
            </Badge>
          )}
        </div>
      </div>
    </header>
  );
}

