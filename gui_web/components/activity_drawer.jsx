window.Components = window.Components || {};

window.Components.ActivityDrawer = function ActivityDrawer({ activity, open, onToggle }) {
  const Icon = window.Components.Icon;
  const count = activity.length;
  const visible = activity.slice(-120).reverse();

  return (
    <React.Fragment>
      <button className="activity-tab" onClick={() => onToggle(!open)}>
        <Icon name="activity" /> Activity ({count})
      </button>
      <section className={`activity-drawer ${open ? "open" : ""}`}>
        <div className="activity-head">
          <span>Activity</span>
          <button className="icon-btn" onClick={() => onToggle(false)}>
            <Icon name="close" />
          </button>
        </div>
        <div className="activity-list">
          {visible.length === 0 && <div className="empty-state">No activity yet</div>}
          {visible.map((entry) => (
            <div key={entry.id} className={`activity-entry ${entry.level || "info"}`}>
              <span className="time">{entry.time}</span>
              <span className="category">{entry.category || "APP"}</span>
              <span className="message">{entry.message}</span>
            </div>
          ))}
        </div>
      </section>
    </React.Fragment>
  );
};
