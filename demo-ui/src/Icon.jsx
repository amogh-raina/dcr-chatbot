export default function Icon({ name, size = 22, stroke = 1.8 }) {
  const paths = {
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    search: <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    down: <path d="m6 9 6 6 6-6" />,
    pause: <><path d="M8 6v12M16 6v12" /></>,
    play: <path d="m9 6 9 6-9 6V6Z" />,
    message: <path d="M20 11.5a7.5 7.5 0 0 1-8 7.48 8.8 8.8 0 0 1-3.9-.97L4 19l1.15-3.45A7.32 7.32 0 0 1 4 11.5 7.5 7.5 0 0 1 12 4a7.5 7.5 0 0 1 8 7.5Z" />,
    restart: <><path d="M20 11a8 8 0 1 1-2.34-5.66" /><path d="M20 4v7h-7" /></>,
    send: <path d="m3 4 18 8-18 8 3-8-3-8Zm3 8h15" />,
    scale: <><path d="M12 3v18M5 7h14M4 20h16" /><path d="m7 7-3 7h6L7 7Zm10 0-3 7h6l-3-7Z" /></>,
    cursor: <path d="m5 3 13 8-6 1 4 7-3 2-4-7-4 4V3Z" />,
    file: <><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v5h5M10 13h5M10 17h5" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.7 9a2.5 2.5 0 1 1 4.25 1.8c-1.3 1.2-1.95 1.8-1.95 3.2M12 17h.01" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></>,
    card: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18" /></>,
    edit: (
      <>
        <path d="M11.5 4H6a2.5 2.5 0 0 0-2.5 2.5v11A2.5 2.5 0 0 0 6 20h11a2.5 2.5 0 0 0 2.5-2.5v-5.5" />
        <path d="M19.2 3.3a2.3 2.3 0 0 1 3.2 3.2L11.5 17.4l-4.2 1 1-4.2L19.2 3.3Z" />
        <path d="m15.8 6.7 3.2 3.2" />
      </>
    ),
    external: (
      <>
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
        <polyline points="15 3 21 3 21 9" />
        <line x1="10" y1="14" x2="21" y2="3" />
      </>
    ),
    check: <polyline points="20 6 9 17 4 12" />,
    'arrow-right': (
      <>
        <line x1="4" y1="12" x2="20" y2="12" />
        <polyline points="14 6 20 12 14 18" />
      </>
    ),
    shield: (
      <>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <line x1="12" y1="8" x2="12.01" y2="8" strokeWidth={stroke * 1.3} />
        <line x1="12" y1="12" x2="12" y2="16" />
      </>
    ),
    save: (
      <>
        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
        <polyline points="17 21 17 13 7 13 7 21" />
        <polyline points="7 3 7 8 15 8" />
      </>
    ),
  };
  return (
    <svg
      className={`icon icon-${name}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.message}
    </svg>
  );
}

