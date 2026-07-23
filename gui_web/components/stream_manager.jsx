window.Components = window.Components || {};

// How often to silently refresh the selected channel's preview while idle,
// so its thumbnail/title don't go stale between explicit selections. Chosen
// to comfortably outlast Twitch's own thumbnail regeneration cadence
// without hammering the GQL endpoint on every render.
const PREVIEW_IDLE_REFRESH_INTERVAL_MS = 60000;

window.Components.StreamManager = function StreamManager({
  api,
  state,
  onState,
  onUiState,
  onToast,
  onOpenSettings,
}) {
  const selectedChannel = state.selected_channel;
  const clipDuration = state.ui_state.stream_manager_clip_duration_seconds || 30;
  const leftRailOpen = state.ui_state.stream_manager_left_sidebar_open !== false;
  const rightRailOpen = state.ui_state.stream_manager_right_sidebar_open !== false;
  const previewRequestRef = React.useRef(0);
  const avatarRequestsRef = React.useRef(new Set());
  const onUiStateRef = React.useRef(onUiState);
  React.useEffect(() => {
    onUiStateRef.current = onUiState;
  }, [onUiState]);

  const autoCollapseEnabled = state.settings.auto_collapse_panels_enabled !== false;
  const isWatching = Boolean(state.stream?.active);

  React.useEffect(() => {
    if (!autoCollapseEnabled || !isWatching) return undefined;

    let timer = null;
    const collapseAll = () => {
      onUiStateRef.current("stream_manager_left_sidebar_open", false);
      onUiStateRef.current("stream_manager_right_sidebar_open", false);
      onUiStateRef.current("stream_manager_activity_drawer_open", false);
    };
    const resetTimer = () => {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(collapseAll, 10000);
    };

    const activityEvents = ["mousemove", "mousedown", "keydown", "wheel", "touchstart"];
    activityEvents.forEach((eventName) => window.addEventListener(eventName, resetTimer));
    resetTimer();

    return () => {
      activityEvents.forEach((eventName) => window.removeEventListener(eventName, resetTimer));
      if (timer) window.clearTimeout(timer);
    };
  }, [autoCollapseEnabled, isWatching]);
  const quality =
    state.stream?.quality || state.settings.preferred_quality || state.launch_quality || "best";

  const [segmentsIndex, setSegmentsIndex] = React.useState(null);
  const streamActive = Boolean(state.stream?.active);
  // Recording segments (the day-timeline / scrub bar data) belong to
  // whichever channel is actually playing, not whichever channel is merely
  // selected/previewed - without this, clicking a different favorite while a
  // background stream keeps playing starts polling that favorite's unrelated
  // (or nonexistent) segment history every 30s. Mirrors video_stage.jsx's
  // isViewingActiveStream.
  const isViewingActiveStream = streamActive && selectedChannel === state.stream?.channel;

  React.useEffect(() => {
    if (!isViewingActiveStream) {
      setSegmentsIndex(null);
      return undefined;
    }
    let cancelled = false;
    const fetchSegments = () => {
      api.get_recording_segments(selectedChannel).then((result) => {
        if (!cancelled && result.ok) setSegmentsIndex(result.segments);
      });
    };
    fetchSegments();
    const interval = window.setInterval(fetchSegments, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [api, selectedChannel, isViewingActiveStream]);

  const mergeFavoriteProfile = (favorites, channel, profileImageUrl) => {
    if (!profileImageUrl) return favorites;
    let changed = false;
    const nextFavorites = favorites.map((favorite) => {
      if (favorite.channel_name !== channel || favorite.profile_image_url === profileImageUrl) {
        return favorite;
      }
      changed = true;
      return { ...favorite, profile_image_url: profileImageUrl };
    });
    return changed ? nextFavorites : favorites;
  };

  const favoriteForChannel = (channel) => (
    (state.favorites || []).find((favorite) => favorite.channel_name === channel)
  );

  const basicPreviewForChannel = (channel) => {
    const favorite = favoriteForChannel(channel);
    return {
      channel,
      is_live: Boolean(favorite?.is_live),
      title: null,
      preview_image_url: null,
      profile_image_url: favorite?.profile_image_url || null,
    };
  };

  const applySelectedPreview = (channel, preview, requestId) => {
    onState((current) => {
      if (!current || current.selected_channel !== channel || requestId !== previewRequestRef.current) {
        return current;
      }
      return {
        ...current,
        preview,
        favorites: mergeFavoriteProfile(current.favorites || [], channel, preview.profile_image_url),
      };
    });
  };

  const fetchSelectedPreview = (channel, requestId) => {
    api.get_preview(channel).then((result) => {
      if (!result.ok) {
        onToast({ kind: "error", message: result.error || "Preview failed" });
        return;
      }
      applySelectedPreview(channel, result.preview, requestId);
    });
  };

  // Idle preview refresh (TODO.md #6): periodically re-fetches the selected
  // channel's preview so its thumbnail/title don't go stale while the user
  // just leaves it selected. Deliberately silent on failure (no onToast) -
  // a transient network blip on a background ~60s tick shouldn't interrupt
  // the user the way a user-initiated fetchSelectedPreview failure should.
  // applySelectedPreview's own selected-channel/requestId guards keep a slow
  // response from clobbering a channel switch that happened in the
  // meantime, and it only ever patches state.preview/state.favorites -
  // never state.selected_channel or state.stream.
  React.useEffect(() => {
    if (!selectedChannel) return undefined;
    const interval = window.setInterval(() => {
      const requestId = previewRequestRef.current + 1;
      previewRequestRef.current = requestId;
      api.get_preview(selectedChannel).then((result) => {
        if (!result.ok) return;
        applySelectedPreview(selectedChannel, result.preview, requestId);
      });
    }, PREVIEW_IDLE_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [api, selectedChannel]);

  React.useEffect(() => {
    const preview = state.preview;
    if (!preview?.channel || !preview.profile_image_url) return;
    onState((current) => {
      if (!current) return current;
      const favorites = mergeFavoriteProfile(
        current.favorites || [],
        preview.channel,
        preview.profile_image_url
      );
      return favorites === current.favorites ? current : { ...current, favorites };
    });
  }, [state.preview?.channel, state.preview?.profile_image_url]);

  React.useEffect(() => {
    (state.favorites || []).forEach((favorite, index) => {
      const channel = favorite.channel_name;
      if (favorite.profile_image_url || avatarRequestsRef.current.has(channel)) return;
      avatarRequestsRef.current.add(channel);
      window.setTimeout(() => {
        api.get_preview(channel).then((result) => {
          if (!result.ok || !result.preview?.profile_image_url) return;
          onState((current) => {
            if (!current) return current;
            const favorites = mergeFavoriteProfile(
              current.favorites || [],
              channel,
              result.preview.profile_image_url
            );
            return favorites === current.favorites ? current : { ...current, favorites };
          });
        });
      }, Math.min(index, 10) * 120);
    });
  }, [api, state.favorites]);

  // Runs an api.* call, always toasting on failure (result.ok === false)
  // instead of leaving individual call sites to remember to do it themselves.
  const runApiAction = (promise, { errorMessage, onSuccess, onError } = {}) => {
    promise.then((result) => {
      if (!result.ok) {
        onToast({ kind: "error", message: result.error || errorMessage || "Action failed" });
        onError?.(result);
        return;
      }
      onSuccess?.(result);
    });
  };

  const selectChannel = (channel, startAfterSelect = false) => {
    const requestId = previewRequestRef.current + 1;
    previewRequestRef.current = requestId;
    const optimisticPreview = state.preview?.channel === channel
      ? state.preview
      : basicPreviewForChannel(channel);
    onState({ selected_channel: channel, preview: optimisticPreview });

    runApiAction(api.select_channel(channel), {
      errorMessage: "Channel select failed",
      onSuccess: (result) => {
        onState((current) => {
          if (!current || current.selected_channel !== channel) return current;
          return {
            ...current,
            selected_channel: result.selected_channel,
            preview: result.preview || optimisticPreview,
          };
        });
        fetchSelectedPreview(result.selected_channel, requestId);
        if (startAfterSelect) startStream(result.selected_channel);
      },
    });
  };

  const startStream = (channel = selectedChannel) => {
    if (!channel) return;
    runApiAction(api.start_stream(channel, quality), {
      errorMessage: "Stream failed",
      onError: (result) => {
        if (result.stream) onState({ stream: result.stream });
      },
      onSuccess: (result) => {
        onState({ stream: result.stream, selected_channel: result.stream.channel || channel });
      },
    });
  };

  const stopStream = () => {
    runApiAction(api.stop_stream(), {
      errorMessage: "Stop stream failed",
      onSuccess: (result) => onState({ stream: result.stream }),
    });
  };

  // Auto-swap to the next live pinned favorite when the currently-playing
  // pinned streamer goes offline, so watching isn't left staring at a
  // frozen, no-longer-live stream. Deliberately scoped to the natural
  // "ended" status (reconnect attempts exhausted - the streamer is actually
  // offline), not "stopped" (the user clicked Stop) or "error" (a different
  // failure class the user should notice via the existing error toast, not
  // have silently papered over). Only triggers when the ended channel was
  // pinned, per spec - never auto-swaps to a non-pinned favorite, and does
  // nothing if no other pinned favorite is currently live.
  const handledEndedStreamRef = React.useRef(false);
  React.useEffect(() => {
    const stream = state.stream;
    if (!stream) return;
    if (stream.active) {
      // A session is live/recording - re-arm so the *next* time a pinned
      // stream ends (even the same channel, restarted), this can fire again.
      handledEndedStreamRef.current = false;
      return;
    }
    if (stream.status !== "ended" || handledEndedStreamRef.current) return;
    handledEndedStreamRef.current = true;

    const endedChannel = stream.channel;
    if (!endedChannel || !favoriteForChannel(endedChannel)?.is_pinned) return;

    const nextPinnedLive = (state.favorites || []).find(
      (favorite) => favorite.is_pinned && favorite.is_live && favorite.channel_name !== endedChannel
    );
    if (!nextPinnedLive) return;

    onToast({
      kind: "info",
      message: `${endedChannel} went offline - switched to ${nextPinnedLive.channel_name}`,
    });
    startStream(nextPinnedLive.channel_name);
  }, [state.stream, state.favorites]);

  const refreshFavorites = () => {
    runApiAction(api.refresh_favorites(), {
      errorMessage: "Favorites refresh failed",
      onSuccess: (result) => onState({ favorites: result.favorites }),
    });
  };

  const addFavorite = () => {
    const channel = window.prompt("Channel name");
    if (!channel) return;
    runApiAction(api.add_favorite(channel), {
      errorMessage: "Favorite not added",
      onSuccess: (result) => onState({ favorites: result.favorites }),
    });
  };

  const removeFavorite = (channel) => {
    runApiAction(api.remove_favorite(channel), {
      errorMessage: "Failed to remove favorite",
      onSuccess: (result) => onState({
        favorites: result.favorites,
        selected_channel: result.selected_channel,
        preview: result.selected_channel ? state.preview : null,
      }),
    });
  };

  const togglePin = (channel) => {
    runApiAction(api.toggle_pin(channel), {
      errorMessage: "Failed to update pin",
      onSuccess: (result) => onState({ favorites: result.favorites }),
    });
  };

  const changeQuality = (nextQuality) => {
    const nextSettings = { ...state.settings, preferred_quality: nextQuality };
    onState({ settings: nextSettings });
    runApiAction(api.save_settings(nextSettings), {
      errorMessage: "Failed to save quality setting",
      onSuccess: (result) => onState({ settings: result.settings }),
    });
  };

  const changeClipDuration = (seconds) => {
    onUiState("stream_manager_clip_duration_seconds", seconds);
  };

  const createClip = (behindLiveSeconds = 0) => {
    runApiAction(api.create_clip(clipDuration, behindLiveSeconds), {
      errorMessage: "Clip failed",
    });
  };

  return (
    <div className={`app-shell ${leftRailOpen ? "" : "left-collapsed"} ${rightRailOpen ? "" : "right-collapsed"}`}>
      <window.Components.FavoritesRail
        favorites={state.favorites || []}
        selectedChannel={selectedChannel}
        open={leftRailOpen}
        onToggle={(open) => onUiState("stream_manager_left_sidebar_open", open)}
        onSelect={selectChannel}
        onAdd={addFavorite}
        onRemove={removeFavorite}
        onPin={togglePin}
        onRefresh={refreshFavorites}
      />
      <div style={{ position: "relative", minWidth: 0, minHeight: 0 }}>
        <window.Components.VideoStage
          selectedChannel={selectedChannel}
          preview={state.preview}
          stream={state.stream}
          clipDuration={clipDuration}
          onClipDuration={changeClipDuration}
          onClip={createClip}
          onOpenClips={() => api.open_clips_folder()}
          segmentsIndex={segmentsIndex}
          onToast={onToast}
        />
        <window.Components.ActivityDrawer
          activity={state.activity || []}
          open={state.ui_state.stream_manager_activity_drawer_open}
          onToggle={(open) => onUiState("stream_manager_activity_drawer_open", open)}
        />
      </div>
      <window.Components.OptionsRail
        selectedChannel={selectedChannel}
        quality={quality}
        qualities={state.qualities || ["best"]}
        stream={state.stream}
        open={rightRailOpen}
        onToggle={(open) => onUiState("stream_manager_right_sidebar_open", open)}
        onQuality={changeQuality}
        onStart={() => startStream()}
        onStop={stopStream}
        onOpenChannel={() => api.open_channel(selectedChannel)}
        onOpenChat={() => api.open_chat(selectedChannel)}
        onOpenSettings={onOpenSettings}
      />
    </div>
  );
};
