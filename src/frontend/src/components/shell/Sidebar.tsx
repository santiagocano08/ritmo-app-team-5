import type { MouseEvent } from "react";
import { SECTIONS, type SectionId } from "./sections";

interface SidebarProps {
  activeSection: SectionId;
  onSelect: (section: SectionId) => void;
}

export function Sidebar({ activeSection, onSelect }: SidebarProps) {
  return (
    <nav
      aria-label="Secciones"
      className="flex h-full w-[248px] flex-col gap-1.5 bg-sidebar px-3.5 py-5 text-white"
    >
      <div className="flex items-center gap-2.5 px-2.5 pb-5 pt-1">
        <span aria-hidden="true" className="text-2xl text-logo">
          ⬳
        </span>
        <span className="font-brand text-xl font-bold">PulsoFlota</span>
      </div>

      <ul className="flex flex-col gap-1.5">
        {SECTIONS.map((item) => {
          const isActive = item.id === activeSection;
          // Section state is in-memory only, so the hash must not change: a reload would ignore it.
          const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
            event.preventDefault();
            onSelect(item.id);
          };
          return (
            <li key={item.id}>
              <a
                href={item.href}
                onClick={handleClick}
                aria-current={isActive ? "page" : undefined}
                className={`flex h-11 items-center gap-3 rounded-token px-3 text-[15px] font-semibold no-underline ${
                  isActive ? "bg-surface text-sidebar" : "text-sidebar-inactive"
                }`}
              >
                <span aria-hidden="true">{item.icon}</span>
                {item.label}
              </a>
            </li>
          );
        })}
      </ul>

      <div className="mt-auto flex flex-col gap-2.5 border-t border-sidebar-divider p-3">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="flex h-9 w-9 items-center justify-center rounded-pill bg-sidebar-divider text-[13px] font-bold"
          >
            UD
          </span>
          <span className="flex flex-col">
            <span className="text-sm font-semibold">Usuario demo</span>
            <span className="text-[13px] text-sidebar-role">Despachador</span>
          </span>
        </div>
        <a
          href="#logout"
          className="flex h-10 items-center gap-2.5 px-1 text-sm font-semibold text-sidebar-inactive no-underline"
        >
          <span aria-hidden="true">⇥</span>
          Cerrar sesión
        </a>
      </div>
    </nav>
  );
}
