window.Components = window.Components || {};

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
  const [quality, setQuality] = React.useState(
    state.stream?.quality || state.settings.preferred_quality || state.launch_quality || "best"
  );

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

  const selectChannel = (channel, startAfterSelect = false) => {
    const requestId = previewRequestRef.current + 1;
    previewRequestRef.current = requestId;
    const optimisticPreview = state.preview?.channel === channel
      ? state.preview
      : basicPreviewForChannel(channel);
    onState({ selected_channel: channel, preview: optimisticPreview });

    api.select_channel(channel).then((result) => {
      if (!result.ok) {
        onToast({ kind: "error", message: result.error || "Channel select failed" });
        return;
      }
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
    });
  };

  const startStream = (channel = selectedChannel) => {
    if (!channel) return;
    api.start_stream(channel, quality).then((result) => {
      if (!result.ok) {
        onToast({ kind: "error", message: result.error || "Stream failed" });
        if (result.stream) onState({ stream: result.stream });
        return;
      }
      onState({ stream: result.stream, selected_channel: result.stream.channel || channel });
    });
  };

  const stopStream = () => {
    api.stop_stream().then((result) => {
      if (result.ok) onState({ stream: result.stream });
    });
  };

  const refreshFavorites = () => {
    api.refresh_favorites().then((result) => {
      if (result.ok) onState({ favorites: result.favorites });
    });
  };

  const addFavorite = () => {
    const channel = window.prompt("Channel name");
    if (!channel) return;
    api.add_favorite(channel).then((result) => {
      if (!result.ok) {
        onToast({ kind: "error", message: result.error || "Favorite not added" });
        return;
      }
      onState({ favorites: result.favorites });
    });
  };

  const removeFavorite = (channel) => {
    api.remove_favorite(channel).then((result) => {
      if (result.ok) {
        onState({
          favorites: result.favorites,
          selected_channel: result.selected_channel,
          preview: result.selected_channel ? state.preview : null,
        });
      }
    });
  };

  const togglePin = (channel) => {
    api.toggle_pin(channel).then((result) => {
      if (result.ok) onState({ favorites: result.favorites });
    });
  };

  const changeQuality = (nextQuality) => {
    setQuality(nextQuality);
    const nextSettings = { ...state.settings, preferred_quality: nextQuality };
    onState({ settings: nextSettings });
    api.save_settings(nextSettings).then((result) => {
      if (result.ok) onState({ settings: result.settings });
    });
  };

  const changeClipDuration = (seconds) => {
    onUiState("stream_manager_clip_duration_seconds", seconds);
  };

  const createClip = () => {
    api.create_clip(clipDuration).then((result) => {
      onToast({
        kind: result.ok ? "success" : "error",
        message: result.ok ? "Clip saved" : result.error || "Clip failed",
      });
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
