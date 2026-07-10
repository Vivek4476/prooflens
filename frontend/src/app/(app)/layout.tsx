import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // print:* variants neutralise the fixed-height / overflow-hidden shell so a printed page
  // flows across as many sheets as the content needs, instead of clipping to one.
  return (
    <div className="flex h-dvh overflow-hidden bg-canvas print:block print:h-auto print:overflow-visible">
      <div className="hidden md:block">
        <Sidebar />
      </div>
      <div className="flex min-w-0 flex-1 flex-col print:block">
        <Topbar />
        <main className="flex-1 overflow-y-auto print:overflow-visible">
          <div className="mx-auto w-full max-w-[1200px] px-6 py-6 print:max-w-none print:p-0">{children}</div>
        </main>
      </div>
    </div>
  );
}
