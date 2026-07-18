window.Components = window.Components || {};

window.Components.Dropdown = function Dropdown({
  value,
  options,
  onChange,
  title,
  className = "",
  buttonClassName = "",
  menuClassName = "",
  renderValue,
}) {
  const Icon = window.Components.Icon;
  const [open, setOpen] = React.useState(false);
  const [placement, setPlacement] = React.useState({ direction: "down", maxHeight: null });
  const rootRef = React.useRef(null);
  const menuRef = React.useRef(null);
  const normalizedOptions = options.map((option) => (
    typeof option === "object" ? option : { value: option, label: String(option) }
  ));
  const selected = normalizedOptions.find((option) => option.value === value)
    || normalizedOptions[0]
    || { value, label: String(value || "") };

  React.useLayoutEffect(() => {
    if (!open || !rootRef.current || !menuRef.current) return undefined;

    const updatePlacement = () => {
      const rootRect = rootRef.current.getBoundingClientRect();
      const menuRect = menuRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
      const gap = 6;
      const margin = 8;
      const spaceBelow = Math.max(0, viewportHeight - rootRect.bottom - gap - margin);
      const spaceAbove = Math.max(0, rootRect.top - gap - margin);
      const openUp = menuRect.height > spaceBelow && spaceAbove > spaceBelow;
      const available = openUp ? spaceAbove : spaceBelow;
      const maxHeight = Math.max(0, Math.floor(available));

      setPlacement({ direction: openUp ? "up" : "down", maxHeight });
    };

    updatePlacement();
    window.addEventListener("resize", updatePlacement);
    window.addEventListener("scroll", updatePlacement, true);
    return () => {
      window.removeEventListener("resize", updatePlacement);
      window.removeEventListener("scroll", updatePlacement, true);
    };
  }, [open, normalizedOptions.length]);

  React.useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const choose = (nextValue) => {
    setOpen(false);
    if (nextValue !== value) onChange(nextValue);
  };

  return (
    <div
      className={`dropdown ${open ? "open" : ""} dropdown-${placement.direction} ${className}`}
      ref={rootRef}
    >
      <button
        type="button"
        className={`dropdown-button ${buttonClassName}`}
        title={title}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="dropdown-value">
          {renderValue ? renderValue(selected) : selected.label}
        </span>
        <Icon name="chevronDown" />
      </button>
      {open && (
        <div
          className={`dropdown-menu ${menuClassName}`}
          role="listbox"
          ref={menuRef}
          style={placement.maxHeight !== null ? { maxHeight: `${placement.maxHeight}px` } : null}
        >
          {normalizedOptions.map((option) => (
            <button
              type="button"
              key={option.value}
              className={`dropdown-option ${option.value === value ? "selected" : ""}`}
              role="option"
              aria-selected={option.value === value}
              onClick={() => choose(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
