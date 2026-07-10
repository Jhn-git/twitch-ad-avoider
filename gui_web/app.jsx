function App() {
  const [ready, setReady] = React.useState(false);
  const [api, setApi] = React.useState(null);
  const [view, setView] = React.useState("stream");
  const [state, setState] = React.useState(null);
  const [toasts, setToasts] = React.useState([]);

  const pushToast = React.useCallback((toast) => {
    const id = `t${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [...items, { id, kind: toast.kind || "info", message: toast.message }]);
    window.setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== id));
    }, 3600);
  }, []);

  const refreshInFlightRef = React.useRef(false);

  const refreshFavorites = React.useCallback((bridge) => {
    if (!bridge?.refresh_favorites || refreshInFlightRef.current) return;
    refreshInFlightRef.current = true;
    bridge.refresh_favorites().then((result) => {
      if (!result.ok) {
        pushToast({ kind: "error", message: result.error || "Favorites refresh failed" });
        return;
      }
      setState((current) => (
        current ? { ...current, favorites: result.favorites || current.favorites } : current
      ));
    }).catch((error) => {
      pushToast({ kind: "error", message: String(error) });
    }).finally(() => {
      refreshInFlightRef.current = false;
    });
  }, [pushToast]);

  const refreshFavoritesOnStartup = React.useCallback((bridge, initial) => {
    if (initial.settings?.favorites_auto_refresh === false) return;
    if (!initial.favorites?.length) return;
    refreshFavorites(bridge);
  }, [refreshFavorites]);

  React.useEffect(() => {
    window.__onStreamEvent = (event) => {
      if (event && event.state) {
        setState((current) => ({ ...current, stream: event.state }));
      }
      if (event && event.type === "clip_created") {
        pushToast({ kind: "success", message: "Clip saved" });
      }
      if (event && event.type === "error") {
        pushToast({ kind: "error", message: event.error || "Stream error" });
      }
    };
    window.__onActivity = (entry) => {
      setState((current) => ({
        ...current,
        activity: [...(current?.activity || []), entry].slice(-500),
      }));
    };
    window.__onFavoritesUpdated = (favorites) => {
      setState((current) => ({ ...current, favorites }));
    };
    window.__onSettingsUpdated = (settings) => {
      window.AppHelpers.applyTheme(settings.dark_mode);
      setState((current) => ({
        ...current,
        settings,
        ui_state: window.AppHelpers.uiStateFromSettings(settings),
      }));
    };
    window.__onToast = pushToast;
  }, [pushToast]);

  React.useEffect(() => {
    const demoMode = new URLSearchParams(window.location.search).has("demo");
    const init = () => {
      const bridge = demoMode ? window.AppHelpers.demoApi() : window.pywebview?.api;
      if (!bridge) return;
      setApi(bridge);
      bridge.get_initial_state().then((initial) => {
        window.AppHelpers.applyTheme(initial.settings?.dark_mode !== false);
        setState(initial);
        setReady(true);
        refreshFavoritesOnStartup(bridge, initial);
      }).catch((error) => {
        pushToast({ kind: "error", message: String(error) });
      });
    };

    if (demoMode || window.pywebview?.api) {
      init();
      return;
    }
    window.addEventListener("pywebviewready", init, { once: true });
    return () => window.removeEventListener("pywebviewready", init);
  }, [pushToast, refreshFavoritesOnStartup]);

  const autoRefreshEnabled = state?.settings?.favorites_auto_refresh !== false;
  const refreshIntervalSeconds = state?.settings?.favorites_refresh_interval;

  React.useEffect(() => {
    if (!api || !autoRefreshEnabled || !refreshIntervalSeconds || refreshIntervalSeconds <= 0) {
      return undefined;
    }
    const id = window.setInterval(() => {
      refreshFavorites(api);
    }, refreshIntervalSeconds * 1000);
    return () => window.clearInterval(id);
  }, [api, autoRefreshEnabled, refreshIntervalSeconds, refreshFavorites]);

  if (!ready || !state || !api) {
    return <div className="loading">Loading Stream Manager...</div>;
  }

  const updateState = (patch) => {
    setState((current) => {
      if (typeof patch === "function") return patch(current);
      return { ...current, ...patch };
    });
  };
  const setUiState = (key, value) => {
    updateState((current) => ({
      ...current,
      ui_state: { ...current.ui_state, [key]: value },
    }));
    api.set_ui_state?.(key, value);
  };

  return (
    <React.Fragment>
      <window.Components.StreamManager
        api={api}
        state={state}
        onState={updateState}
        onUiState={setUiState}
        onToast={pushToast}
        onOpenSettings={() => setView("settings")}
      />
      {view === "settings" && (
        <window.Components.SettingsView
          api={api}
          state={state}
          onBack={() => setView("stream")}
          onState={updateState}
          onToast={pushToast}
        />
      )}
      <window.Components.ToastStack toasts={toasts} />
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
