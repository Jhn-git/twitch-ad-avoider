window.AppHelpers = {
  _soundCache: {},

  clampRatio(value, min, max) {
    return Math.min(max, Math.max(min, value));
  },

  playSound(relativePath) {
    let audio = this._soundCache[relativePath];
    if (!audio) {
      audio = new Audio(relativePath);
      this._soundCache[relativePath] = audio;
    }
    audio.currentTime = 0;
    audio.play().catch(() => {});
  },

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
      stream_manager_edit_after_clip:
        settings.stream_manager_edit_after_clip !== false,
      volume: settings.volume ?? 0.2,
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

  timeLabel(seconds) {
    const safe = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(safe / 60);
    const remainder = safe - minutes * 60;
    return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
  },

  kebabSlug(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  },

  // Full-day recording timeline math (day-scoped scrub history). segmentsIndex
  // is the payload from api.get_recording_segments(): { stream_created_at,
  // segments: [{id, start, end}], now } - all timestamps ISO strings, `end`
  // null means still recording.

  computeTimelineBounds(segmentsIndex) {
    const now = segmentsIndex?.now ? new Date(segmentsIndex.now) : new Date();
    let start = segmentsIndex?.stream_created_at ? new Date(segmentsIndex.stream_created_at) : null;
    if (!start && segmentsIndex?.segments?.length) {
      start = segmentsIndex.segments.reduce((earliest, segment) => {
        const segStart = new Date(segment.start);
        return !earliest || segStart < earliest ? segStart : earliest;
      }, null);
    }
    if (!start || Number.isNaN(start.getTime())) start = now;
    return { start, end: now };
  },

  timestampToRatio(date, bounds) {
    const span = bounds.end.getTime() - bounds.start.getTime();
    if (span <= 0) return 1;
    return this.clampRatio((date.getTime() - bounds.start.getTime()) / span, 0, 1);
  },

  ratioToTimestamp(ratio, bounds) {
    const span = bounds.end.getTime() - bounds.start.getTime();
    const clamped = this.clampRatio(ratio, 0, 1);
    return new Date(bounds.start.getTime() + clamped * span);
  },

  // The segment a timestamp falls inside (open segments extend to `now`), or
  // null if it lands in a gap.
  findSegmentAt(segmentsIndex, date) {
    if (!segmentsIndex?.segments?.length) return null;
    const now = segmentsIndex.now ? new Date(segmentsIndex.now) : new Date();
    for (const segment of segmentsIndex.segments) {
      const start = new Date(segment.start);
      const end = segment.end ? new Date(segment.end) : now;
      if (date >= start && date <= end) return segment;
    }
    return null;
  },

  // The most recently started segment - the one still being recorded (if any).
  currentSegment(segmentsIndex) {
    const segments = segmentsIndex?.segments;
    if (!segments?.length) return null;
    return segments[segments.length - 1];
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
      pinned_favorites_refresh_interval: 60,
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
      stream_manager_edit_after_clip: true,
      auto_collapse_panels_enabled: true,
    };
    let selected = "theonlymonto";
    let recentClip = null;
    let stream = {
      active: false,
      channel: null,
      quality: "best",
      playback_url: null,
      status: "idle",
      recording: false,
      clip_ready: false,
      clip_ready_seconds: 0,
      clip_warmup_reason: null,
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
        stream = {
          ...stream,
          active: true,
          channel,
          quality,
          status: "live",
          recording: true,
          clip_ready: true,
          clip_ready_seconds: 300,
          clip_warmup_reason: null,
          // Local test clip generated by scripts/run_demo_server.py - gives
          // the player a real playback_url so hls.js actually buffers and
          // the scrub bar has real video.buffered data to work with, instead
          // of demo mode's video stage staying permanently empty.
          playback_url: "demo-assets/stream.m3u8",
        };
        return Promise.resolve({ ok: true, stream });
      },
      stop_stream: () => {
        stream = {
          ...stream,
          active: false,
          channel: null,
          status: "idle",
          recording: false,
          clip_ready: false,
          clip_ready_seconds: 0,
          clip_warmup_reason: null,
        };
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
      create_clip: (durationSeconds = 30, _behindLiveSeconds = 0, editAfterClipping = true) => {
        const capturedAt = new Date();
        const channelSlug = window.AppHelpers.kebabSlug(stream.channel || selected);
        const stamp = capturedAt.toISOString().replace(/\D/g, "").slice(0, 14);
        const baseName = `${channelSlug}-${stamp.slice(0, 8)}-${stamp.slice(8)}`;
        const duration = Math.min(Number(durationSeconds) || 30, 45);
        recentClip = {
          id: `demo-${Date.now()}`,
          channel: stream.channel || selected,
          captured_at: capturedAt.toISOString(),
          path: `clips/${baseName}.mp4`,
          base_name: baseName,
          filename: `${baseName}.mp4`,
          title: "",
          status: "ready",
          message: "Added 5s post-roll",
          error: null,
          retry_available: false,
          preview_url: "demo-assets/stream.m3u8",
          preview_revision: 1,
          preview_verified: true,
          can_edit: true,
          preview_duration_seconds: duration,
          selection_start_seconds: 0,
          selection_end_seconds: duration,
          tail_seconds: 5,
        };
        window.__onStreamEvent?.({
          type: "clip_created",
          path: recentClip.path,
          clip: recentClip,
          open_editor: editAfterClipping,
        });
        return Promise.resolve({ ok: true, path: recentClip.path, clip: recentClip });
      },
      get_recent_clip: () => Promise.resolve({ ok: true, clip: recentClip }),
      request_clip_tail_extension: () => {
        if (!recentClip) return Promise.resolve({ ok: false, error: "No recent clip" });
        recentClip = {
          ...recentClip,
          preview_revision: recentClip.preview_revision + 1,
          preview_duration_seconds: recentClip.preview_duration_seconds + 5,
          selection_end_seconds: recentClip.selection_end_seconds + 5,
          tail_seconds: recentClip.tail_seconds + 5,
          message: `Captured ${recentClip.tail_seconds + 5}s after the original clip point`,
        };
        window.__onStreamEvent?.({ type: "clip_edit_updated", clip: recentClip });
        return Promise.resolve({ ok: true, clip: recentClip });
      },
      retry_clip_edit_preparation: () => {
        if (!recentClip) return Promise.resolve({ ok: false, error: "No recent clip" });
        recentClip = {
          ...recentClip,
          status: "ready",
          message: "Padded clip preview ready",
          error: null,
          retry_available: false,
          preview_verified: true,
          can_edit: true,
        };
        window.__onStreamEvent?.({ type: "clip_edit_updated", clip: recentClip });
        return Promise.resolve({ ok: true, clip: recentClip });
      },
      save_clip_edit: (_clipId, startSeconds, endSeconds, title) => {
        if (!recentClip) return Promise.resolve({ ok: false, error: "No recent clip" });
        const titleSlug = window.AppHelpers.kebabSlug(title).slice(0, 80);
        const filename = `${recentClip.base_name}${titleSlug ? `-${titleSlug}` : ""}.mp4`;
        recentClip = {
          ...recentClip,
          filename,
          path: `clips/${filename}`,
          title,
          selection_start_seconds: startSeconds,
          selection_end_seconds: endSeconds,
          message: "Clip saved",
        };
        window.__onStreamEvent?.({ type: "clip_edit_updated", clip: recentClip });
        return Promise.resolve({ ok: true, path: recentClip.path, clip: recentClip });
      },
      save_screenshot: () => {
        const path = "clips/screenshots/demo.png";
        window.__onStreamEvent?.({ type: "screenshot_created", path });
        return Promise.resolve({ ok: true, path });
      },
      reveal_in_explorer: () => Promise.resolve({ ok: true }),
      open_channel: () => Promise.resolve({ ok: true }),
      open_chat: () => Promise.resolve({ ok: true }),
      open_clips_folder: () => Promise.resolve({ ok: true }),
      save_settings: (patch) => Promise.resolve({ ok: true, settings: { ...settings, ...patch } }),
      reset_settings_to_defaults: () => Promise.resolve({ ok: true, settings }),
      validate_setting: () => Promise.resolve({ ok: true }),
      set_ui_state: () => Promise.resolve({ ok: true }),
      // Synthetic session history so the day-timeline segment bands and the
      // live-window highlight (gui_web/components/video_stage.jsx) have real
      // data to render/interact with in demo mode: a closed segment from
      // earlier, a gap (app closed), then the still-recording current one.
      get_recording_segments: () => {
        const now = new Date();
        const hoursAgo = (h) => new Date(now.getTime() - h * 3600000).toISOString();
        return Promise.resolve({
          ok: true,
          segments: {
            stream_created_at: hoursAgo(4),
            now: now.toISOString(),
            segments: [
              { id: "demo-1", start: hoursAgo(4), end: hoursAgo(2.5) },
              { id: "demo-2", start: hoursAgo(2), end: null },
            ],
          },
        });
      },
    };
  },
};
