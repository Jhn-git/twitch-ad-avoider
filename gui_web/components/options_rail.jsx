window.Components = window.Components || {};

window.Components.OptionsRail = function OptionsRail({
  selectedChannel,
  quality,
  qualities,
  stream,
  open,
  onToggle,
  onQuality,
  onStart,
  onStop,
  onOpenChannel,
  onOpenChat,
  onOpenSettings,
}) {
  const Icon = window.Components.Icon;
  const Dropdown = window.Components.Dropdown;
  const qualityOptions = qualities.map((item) => ({ value: item, label: item }));
  const streamAction = stream?.active
    ? { label: "Stop Stream", icon: "stop", action: onStop, disabled: false, primary: false }
    : {
        label: "Watch Stream",
        icon: "play",
        action: onStart,
        disabled: !selectedChannel,
        primary: true,
      };

  return (
    <aside className={`rail right ${open ? "" : "collapsed"}`}>
      <div className="rail-head">
        <span className="rail-title">Options</span>
        <div className="rail-actions">
          {open && (
            <button className="icon-btn" title="Settings" onClick={onOpenSettings}>
              <Icon name="gear" />
            </button>
          )}
          <button
            className="icon-btn rail-toggle"
            title={open ? "Collapse options" : "Expand options"}
            onClick={() => onToggle(!open)}
          >
            <Icon name="chevron" />
          </button>
        </div>
      </div>
      {open ? (
        <div className="options-body">
          <button
            className={`btn block ${streamAction.primary ? "primary" : ""}`}
            disabled={streamAction.disabled}
            onClick={streamAction.action}
          >
            <Icon name={streamAction.icon} /> {streamAction.label}
          </button>
          <button className="btn block" disabled={!selectedChannel} onClick={onOpenChannel}>
            <Icon name="external" /> Open Channel
          </button>
          <button className="btn block" disabled={!selectedChannel} onClick={onOpenChat}>
            <Icon name="message" /> Open Chat
          </button>
          <label className="field-label">Quality</label>
          <Dropdown
            value={quality}
            options={qualityOptions}
            onChange={onQuality}
            title="Quality"
            className="quality-dropdown"
            buttonClassName="select-like"
          />
        </div>
      ) : (
        <div className="options-body compact-actions">
          <button
            className={`icon-command ${streamAction.primary ? "primary" : ""}`}
            disabled={streamAction.disabled}
            title={streamAction.label}
            onClick={streamAction.action}
          >
            <Icon name={streamAction.icon} />
          </button>
          <button
            className="icon-command"
            disabled={!selectedChannel}
            title="Open Channel"
            onClick={onOpenChannel}
          >
            <Icon name="external" />
          </button>
          <button
            className="icon-command"
            disabled={!selectedChannel}
            title="Open Chat"
            onClick={onOpenChat}
          >
            <Icon name="message" />
          </button>
          <button className="icon-command" title="Settings" onClick={onOpenSettings}>
            <Icon name="gear" />
          </button>
        </div>
      )}
      <div className="right-spacer" />
    </aside>
  );
};
