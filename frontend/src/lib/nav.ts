import {
  BarChart3,
  LayoutDashboard,
  ScanSearch,
  Settings,
  UploadCloud,
  History as HistoryIcon,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const NAV: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Analyze Photo", href: "/analyze", icon: ScanSearch },
  { label: "Bulk upload", href: "/bulk", icon: UploadCloud },
  { label: "Upload History", href: "/history", icon: HistoryIcon },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];
