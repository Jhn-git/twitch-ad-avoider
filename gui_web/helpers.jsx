window.AppHelpers = {
  applyTheme(isDark) {
    document.body.dataset.theme = isDark ? "dark" : "light";
  },

  uiStateFromSettings(settings) {
    return {
      stream_manager_left_sidebar_open: settings.stream_manager_left_sidebar_open !== false,
      stream_manager_right_sidebar_open: settings.stream_manager_right_sidebar_open !== false,
      stream_manager_activity_drawer_open:
        settings.stream_manager_activity_drawer_open === true,
      stream_manager_clip_duration_seconds:
        settings.stream_manager_clip_duration_seconds || 30,
    };
  },

  titleForPreview(preview) {
    if (!preview) return "";
    return preview.title || (preview.is_live ? "Live now" : "");
  },

  durationLabel(seconds) {
    if (seconds >= 60) return `${Math.round(seconds / 60)} min`;
    return `${seconds}s`;
  },

  demoApi() {
    const favorites = [
      { channel_name: "zubatlel", is_live: true, is_pinned: false, profile_image_url: null },
      { channel_name: "deadbydaylight", is_live: false, is_pinned: false, profile_image_url: null },
      { channel_name: "jg_darhk", is_live: false, is_pinned: false, profile_image_url: null },
      { channel_name: "littlespacerock", is_live: false, is_pinned: false, profile_image_url: null },
      { channel_name: "knightlight", is_live: true, is_pinned: false, profile_image_url: null },
      { channel_name: "theonlymonto", is_live: true, is_pinned: false, profile_image_url: null },
    ];
    const settings = {
      preferred_quality: "best",
      twitch_low_latency: true,
      hls_live_edge: 3,
      debug: false,
      log_to_file: true,
      log_level: "INFO",
      clip_enabled: true,
      clip_directory: "clips",
      ffmpeg_path: "",
      dark_mode: true,
      network_timeout: 30,
      connection_retry_attempts: 3,
      retry_delay: 5,
      enable_network_diagnostics: true,
      favorites_auto_refresh: true,
      favorites_refresh_interval: 300,
      favorites_check_timeout: 5,
      favorite_live_notifications_enabled: true,
      favorite_live_highlight_test_mode: false,
      favorite_live_notification_sound_enabled: true,
      button_hover_sound_enabled: true,
      show_stream_preview: true,
      window_width: 1440,
      window_height: 850,
      window_maximized: false,
      stream_manager_left_sidebar_open: true,
      stream_manager_right_sidebar_open: true,
      stream_manager_activity_drawer_open: false,
      stream_manager_clip_duration_seconds: 120,
      auto_collapse_panels_enabled: true,
    };
    let selected = "theonlymonto";
    let stream = {
      active: false,
      channel: null,
      quality: "best",
      playback_url: null,
      status: "idle",
      recording: false,
      last_error: null,
    };
    const preview = (channel) => ({
      channel,
      is_live: channel === "theonlymonto" || channel === "zubatlel" || channel === "knightlight",
      title: channel === "theonlymonto"
        ? "[DROPS] MONDAY MA DUDES | Survivor/Killer Winstreak /w Streamloots !cards"
        : "",
      preview_image_url: null,
      profile_image_url: null,
    });
    return {
      get_initial_state: () => Promise.resolve({
        settings,
        qualities: ["best", "worst", "720p", "480p", "360p", "160p"],
        favorites,
        selected_channel: selected,
        launch_quality: "best",
        preview: preview(selected),
        stream,
        ui_state: window.AppHelpers.uiStateFromSettings(settings),
        activity: [{ id: "demo", time: "12:00:00", level: "info", category: "APP", message: "Demo mode" }],
      }),
      select_channel: (channel) => {
        selected = channel;
        return Promise.resolve({ ok: true, selected_channel: channel, preview: preview(channel) });
      },
      get_preview: (channel) => Promise.resolve({ ok: true, preview: preview(channel) }),
      start_stream: (channel, quality) => {
        stream = { ...stream, active: true, channel, quality, status: "live", recording: true };
        return Promise.resolve({ ok: true, stream });
      },
      stop_stream: () => {
        stream = { ...stream, active: false, channel: null, status: "idle", recording: false };
        return Promise.resolve({ ok: true, stream });
      },
      refresh_favorites: () => Promise.resolve({ ok: true, favorites }),
      add_favorite: (channel) => Promise.resolve({
        ok: true,
        favorites: [
          ...favorites,
          { channel_name: channel, is_live: false, is_pinned: false, profile_image_url: null },
        ],
      }),
      remove_favorite: () => Promise.resolve({ ok: true, favorites }),
      toggle_pin: () => Promise.resolve({ ok: true, favorites }),
      create_clip: () => Promise.resolve({ ok: true, path: "clips/demo.mp4" }),
      open_channel: () => Promise.resolve({ ok: true }),
      open_chat: () => Promise.resolve({ ok: true }),
      open_clips_folder: () => Promise.resolve({ ok: true }),
      save_settings: (patch) => Promise.resolve({ ok: true, settings: { ...settings, ...patch } }),
      reset_settings_to_defaults: () => Promise.resolve({ ok: true, settings }),
      validate_setting: () => Promise.resolve({ ok: true }),
      set_ui_state: () => Promise.resolve({ ok: true }),
    };
  },
};
