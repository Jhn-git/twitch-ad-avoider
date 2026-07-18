window.Components = window.Components || {};

window.Components.Icon = function Icon({ name }) {
  const common = {
    className: "icon",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };
  const paths = {
    activity: <React.Fragment><path d="M22 12h-4l-3 8-6-16-3 8H2" /></React.Fragment>,
    chevron: <path d="m9 18 6-6-6-6" />,
    chevronDown: <path d="m6 9 6 6 6-6" />,
    close: <React.Fragment><path d="M18 6 6 18" /><path d="m6 6 12 12" /></React.Fragment>,
    external: <React.Fragment><path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" /></React.Fragment>,
    folder: <React.Fragment><path d="M3 7h5l2 2h11v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" /></React.Fragment>,
    gear: <React.Fragment><path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.05.05a2 2 0 1 1-2.83 2.83l-.05-.05a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.08a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.88.34l-.05.05a2 2 0 1 1-2.83-2.83l.05-.05A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.08a1.7 1.7 0 0 0 1.55-1 1.7 1.7 0 0 0-.34-1.88l-.05-.05a2 2 0 1 1 2.83-2.83l.05.05A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.08a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.88-.34l.05-.05a2 2 0 1 1 2.83 2.83l-.05.05A1.7 1.7 0 0 0 19.4 9c.1.37.39.67.74.83.21.1.45.17.86.17a2 2 0 1 1 0 4h-.08a1.7 1.7 0 0 0-1.52 1Z" /></React.Fragment>,
    message: <React.Fragment><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z" /></React.Fragment>,
    pin: <React.Fragment><path d="m15 4 5 5-4 4v6l-4-4-5 5-2-2 5-5-4-4 4-4Z" /></React.Fragment>,
    play: <polygon points="6 3 20 12 6 21 6 3" />,
    plus: <React.Fragment><path d="M12 5v14" /><path d="M5 12h14" /></React.Fragment>,
    refresh: <React.Fragment><path d="M21 12a9 9 0 0 1-15 6.7" /><path d="M3 12a9 9 0 0 1 15-6.7" /><path d="M18 2v4h-4" /><path d="M6 22v-4h4" /></React.Fragment>,
    save: <React.Fragment><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" /><path d="M17 21v-8H7v8" /><path d="M7 3v5h8" /></React.Fragment>,
    scissors: <React.Fragment><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><path d="M20 4 8.1 15.9" /><path d="M8.1 8.1 20 20" /></React.Fragment>,
    skipToLive: <React.Fragment><polygon points="5 4 15 12 5 20 5 4" /><line x1="19" y1="5" x2="19" y2="19" /></React.Fragment>,
    stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
    trash: <React.Fragment><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /></React.Fragment>,
  };
  return <svg {...common}>{paths[name] || null}</svg>;
};
