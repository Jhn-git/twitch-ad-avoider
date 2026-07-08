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
  const rootRef = React.useRef(null);
  const normalizedOptions = options.map((option) => (
    typeof option === "object" ? option : { value: option, label: String(option) }
  ));
  const selected = normalizedOptions.find((option) => option.value === value)
    || normalizedOptions[0]
    || { value, label: String(value || "") };

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
    <div className={`dropdown ${open ? "open" : ""} ${className}`} ref={rootRef}>
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
        <div className={`dropdown-menu ${menuClassName}`} role="listbox">
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
