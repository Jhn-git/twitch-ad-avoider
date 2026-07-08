window.Components = window.Components || {};

window.Components.SettingsView = function SettingsView({ api, state, onBack, onState, onToast }) {
  const Icon = window.Components.Icon;
  const [form, setForm] = React.useState(state.settings);
  const [errors, setErrors] = React.useState({});

  React.useEffect(() => setForm(state.settings), [state.settings]);

  const commit = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    api.validate_setting(key, value).then((result) => {
      setErrors((current) => ({ ...current, [key]: result.ok ? null : "Invalid value" }));
    });
  };

  const save = () => {
    api.save_settings(form).then((result) => {
      if (!result.ok) {
        onToast({ kind: "error", message: result.error || "Settings save failed" });
        return;
      }
      window.AppHelpers.applyTheme(result.settings.dark_mode);
      onState({
        settings: result.settings,
        ui_state: window.AppHelpers.uiStateFromSettings(result.settings),
      });
      onToast({ kind: "success", message: "Settings saved" });
      onBack();
    });
  };

  const reset = () => {
    api.reset_settings_to_defaults().then((result) => {
      if (result.ok) {
        setForm(result.settings);
        setErrors({});
        onState({
          settings: result.settings,
          ui_state: window.AppHelpers.uiStateFromSettings(result.settings),
        });
        onToast({ kind: "success", message: "Settings reset" });
      }
    });
  };

  const Field = ({ label, keyName, type = "text", options }) => {
    const value = form[keyName];
    let control = null;
    if (type === "bool") {
      control = (
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => commit(keyName, event.target.checked)}
        />
      );
    } else if (type === "select") {
      control = (
        <select value={value ?? ""} onChange={(event) => commit(keyName, event.target.value)}>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      );
    } else {
      control = (
        <input
          type={type}
          value={value ?? ""}
          onChange={(event) => {
            const raw = event.target.value;
            commit(keyName, type === "number" ? Number(raw) : raw);
          }}
        />
      );
    }
    return (
      <label className="setting-field">
        <span>{label}</span>
        {control}
        {errors[keyName] && <span className="field-error">{errors[keyName]}</span>}
      </label>
    );
  };

  return (
    <div className="app-shell" style={{ gridTemplateColumns: "1fr" }}>
      <main className="stage" style={{ overflowY: "auto", alignItems: "stretch" }}>
        <div className="settings-view">
          <div className="settings-head">
            <h1 className="settings-title">Settings</h1>
            <button className="btn" onClick={onBack}>Back</button>
          </div>
          <div className="settings-grid">
            <section className="settings-section">
              <h3>Stream</h3>
              <Field label="Quality" keyName="preferred_quality" type="select" options={state.qualities} />
              <Field label="Low latency" keyName="twitch_low_latency" type="bool" />
              <Field label="HLS live edge" keyName="hls_live_edge" type="number" />
            </section>
            <section className="settings-section">
              <h3>Clips</h3>
              <Field label="Enable clips" keyName="clip_enabled" type="bool" />
              <Field label="Clip directory" keyName="clip_directory" />
              <Field label="FFmpeg path" keyName="ffmpeg_path" />
            </section>
            <section className="settings-section">
              <h3>Network</h3>
              <Field label="Timeout" keyName="network_timeout" type="number" />
              <Field label="Retry attempts" keyName="connection_retry_attempts" type="number" />
              <Field label="Retry delay" keyName="retry_delay" type="number" />
              <Field label="Diagnostics" keyName="enable_network_diagnostics" type="bool" />
            </section>
            <section className="settings-section">
              <h3>Favorites</h3>
              <Field label="Auto refresh" keyName="favorites_auto_refresh" type="bool" />
              <Field label="Refresh interval" keyName="favorites_refresh_interval" type="number" />
              <Field label="Check timeout" keyName="favorites_check_timeout" type="number" />
              <Field label="Live notifications" keyName="favorite_live_notifications_enabled" type="bool" />
              <Field label="Notification sound" keyName="favorite_live_notification_sound_enabled" type="bool" />
            </section>
            <section className="settings-section">
              <h3>Interface</h3>
              <Field label="Dark mode" keyName="dark_mode" type="bool" />
              <Field label="Show preview" keyName="show_stream_preview" type="bool" />
              <Field label="Hover sound" keyName="button_hover_sound_enabled" type="bool" />
              <Field label="Window width" keyName="window_width" type="number" />
              <Field label="Window height" keyName="window_height" type="number" />
            </section>
            <section className="settings-section">
              <h3>Advanced</h3>
              <Field label="Debug" keyName="debug" type="bool" />
              <Field label="Log to file" keyName="log_to_file" type="bool" />
              <Field label="Log level" keyName="log_level" type="select" options={["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]} />
            </section>
          </div>
          <div className="settings-actions">
            <button className="btn" onClick={reset}>Reset</button>
            <button className="btn primary" onClick={save}><Icon name="save" /> Save</button>
          </div>
        </div>
      </main>
    </div>
  );
};
