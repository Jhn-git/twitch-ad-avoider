function App() {
  const [ready, setReady] = React.useState(false);
  const [api, setApi] = React.useState(null);
  const [view, setView] = React.useState("stream");
  const [state, setState] = React.useState(null);
  const [toasts, setToasts] = React.useState([]);
  const [recentClip, setRecentClip] = React.useState(null);
  const [clipEditorOpen, setClipEditorOpen] = React.useState(false);
  // { [channel]: { style, delay, duration } } - the animation each newly-live
  // favorite is currently playing in the rail.
  const [liveFx, setLiveFx] = React.useState({});

  const acknowledgeLive = React.useCallback((channel) => {
    setLiveFx((current) => {
      if (!current[channel]) return current;
      const next = { ...current };
      delete next[channel];
      return next;
    });
  }, []);

  // Replays the went-live animation on every favorite that is currently live, so
  // the effect can be seen on demand instead of only when someone actually goes
  // live. Returns how many channels it started, for the caller's feedback.
  const previewLiveAnimation = React.useCallback(() => {
    const live = (state?.favorites || [])
      .filter((favorite) => favorite.is_live)
      .map((favorite) => favorite.channel_name);
    if (live.length) setLiveFx(window.AppHelpers.liveFxForChannels(live));
    return live.length;
  }, [state?.favorites]);

  const pushToast = React.useCallback((toast) => {
    const id = `t${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [
      ...items,
      { id, kind: toast.kind || "info", message: toast.message, onClick: toast.onClick },
    ]);
    window.setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== id));
    }, 3600);
  }, []);

  const apiRef = React.useRef(null);
  React.useEffect(() => {
    apiRef.current = api;
  }, [api]);

  const hoverSoundEnabledRef = React.useRef(true);
  React.useEffect(() => {
    hoverSoundEnabledRef.current = state?.settings?.button_hover_sound_enabled !== false;
  }, [state?.settings?.button_hover_sound_enabled]);

  React.useEffect(() => {
    let lastPlayed = 0;
    const onButtonHover = (event) => {
      if (!hoverSoundEnabledRef.current) return;
      const button = event.target.closest("button");
      if (!button || button.disabled) return;
      if (button.contains(event.relatedTarget)) return;
      const now = Date.now();
      if (now - lastPlayed < 120) return;
      lastPlayed = now;
      window.AppHelpers.playSound("assets/minimalist-button-hover-sound-effect-399749.mp3");
    };
    document.addEventListener("mouseover", onButtonHover);
    return () => document.removeEventListener("mouseover", onButtonHover);
  }, []);

  const refreshInFlightRef = React.useRef(false);
  // Self-healing state: consecutive failed refreshes (toast only the first), a
  // short-backoff retry timer so recovery doesn't wait for the next slow
  // interval tick, and when we last succeeded (for wake-from-sleep catch-up).
  const refreshFailuresRef = React.useRef(0);
  const refreshRetryTimerRef = React.useRef(null);
  const lastRefreshOkRef = React.useRef(Date.now());
  const REFRESH_RETRY_DELAYS_SECONDS = [15, 30, 60];

  const refreshFavorites = React.useCallback((bridge) => {
    if (!bridge?.refresh_favorites || refreshInFlightRef.current) return;
    refreshInFlightRef.current = true;
    if (refreshRetryTimerRef.current) {
      window.clearTimeout(refreshRetryTimerRef.current);
      refreshRetryTimerRef.current = null;
    }
    const onFailure = (message) => {
      refreshFailuresRef.current += 1;
      if (refreshFailuresRef.current === 1) {
        pushToast({ kind: "error", message });
      }
      const delays = REFRESH_RETRY_DELAYS_SECONDS;
      const delay = delays[Math.min(refreshFailuresRef.current - 1, delays.length - 1)];
      refreshRetryTimerRef.current = window.setTimeout(() => {
        refreshRetryTimerRef.current = null;
        refreshFavorites(bridge);
      }, delay * 1000);
    };
    bridge.refresh_favorites().then((result) => {
      if (!result.ok) {
        onFailure(result.error || "Favorites refresh failed");
        return;
      }
      const recovered = refreshFailuresRef.current > 0;
      refreshFailuresRef.current = 0;
      lastRefreshOkRef.current = Date.now();
      if (recovered) pushToast({ kind: "success", message: "Reconnected - favorites updated" });
      setState((current) => (
        current ? { ...current, favorites: result.favorites || current.favorites } : current
      ));
    }).catch((error) => {
      onFailure(String(error));
    }).finally(() => {
      refreshInFlightRef.current = false;
    });
  }, [pushToast]);

  React.useEffect(() => () => {
    if (refreshRetryTimerRef.current) window.clearTimeout(refreshRetryTimerRef.current);
  }, []);

  const pinnedRefreshInFlightRef = React.useRef(false);

  // Separate, faster-cadence refresh scoped to pinned favorites only - a
  // background tick, so failures stay silent (no toast spam) same as the
  // idle preview refresh in stream_manager.jsx. Independent in-flight guard
  // from refreshFavorites' - the two check overlapping but different channel
  // sets and there's no need to block one on the other.
  const refreshPinnedFavorites = React.useCallback((bridge) => {
    if (!bridge?.refresh_favorites || pinnedRefreshInFlightRef.current) return;
    pinnedRefreshInFlightRef.current = true;
    bridge.refresh_favorites(true).then((result) => {
      if (!result.ok) return;
      lastRefreshOkRef.current = Date.now();
      // Connectivity is back but the full refresh is still waiting on its
      // backoff timer - run it now so the whole list heals together.
      if (refreshFailuresRef.current > 0) refreshFavorites(bridge);
      setState((current) => (
        current ? { ...current, favorites: result.favorites || current.favorites } : current
      ));
    }).catch(() => {}).finally(() => {
      pinnedRefreshInFlightRef.current = false;
    });
  }, [refreshFavorites]);

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
        if (event.clip) {
          setRecentClip(event.clip);
          if (event.open_editor !== false) setClipEditorOpen(true);
        }
        pushToast({
          kind: "success",
          message: "Clip saved",
          onClick: () => setClipEditorOpen(true),
        });
      }
      if (event && event.type === "clip_edit_updated" && event.clip) {
        setRecentClip(event.clip);
      }
      if (event && event.type === "screenshot_created") {
        pushToast({
          kind: "success",
          message: "Screenshot saved (click to open)",
          onClick: () => apiRef.current?.reveal_in_explorer?.(event.path),
        });
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
    window.__onFavoriteLiveSound = () => {
      window.AppHelpers.playSound("assets/live-notification-sound-effect-52434.mp3");
    };
    // Latest went-live batch only - replaces the previous batch so the rail
    // animates just the channels behind the most recent notification tone.
    window.__onFavoritesCameOnline = (payload) => {
      setLiveFx(window.AppHelpers.liveFxForChannels(payload?.channels));
    };
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
        bridge.get_recent_clip?.().then((result) => {
          if (result?.ok && result.clip) setRecentClip(result.clip);
        }).catch(() => {});
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

  // Catch up right away when the network returns or the window wakes after a
  // long gap (sleep/resume), instead of waiting out the interval timers.
  React.useEffect(() => {
    if (!api || !autoRefreshEnabled) return undefined;
    const STALE_AFTER_MS = 60 * 1000;
    const onOnline = () => refreshFavorites(api);
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      const stale = Date.now() - lastRefreshOkRef.current > STALE_AFTER_MS;
      if (refreshFailuresRef.current > 0 || stale) refreshFavorites(api);
    };
    window.addEventListener("online", onOnline);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("online", onOnline);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [api, autoRefreshEnabled, refreshFavorites]);

  const pinnedRefreshIntervalSeconds = state?.settings?.pinned_favorites_refresh_interval;

  React.useEffect(() => {
    if (!api || !autoRefreshEnabled || !pinnedRefreshIntervalSeconds || pinnedRefreshIntervalSeconds <= 0) {
      return undefined;
    }
    const id = window.setInterval(() => {
      refreshPinnedFavorites(api);
    }, pinnedRefreshIntervalSeconds * 1000);
    return () => window.clearInterval(id);
  }, [api, autoRefreshEnabled, pinnedRefreshIntervalSeconds, refreshPinnedFavorites]);

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
        recentClip={recentClip}
        clipEditorOpen={clipEditorOpen}
        onOpenClipEditor={() => setClipEditorOpen(true)}
        onCloseClipEditor={() => setClipEditorOpen(false)}
        onRecentClip={setRecentClip}
        liveFx={liveFx}
        onAcknowledgeLive={acknowledgeLive}
      />
      {view === "settings" && (
        <window.Components.SettingsView
          api={api}
          state={state}
          onBack={() => setView("stream")}
          onState={updateState}
          onToast={pushToast}
          onPreviewLiveAnimation={previewLiveAnimation}
        />
      )}
      <window.Components.ToastStack toasts={toasts} />
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
