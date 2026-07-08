window.Components = window.Components || {};

window.Components.VideoStage = function VideoStage({
  selectedChannel,
  preview,
  stream,
  clipDuration,
  onClipDuration,
  onClip,
  onOpenClips,
}) {
  const Icon = window.Components.Icon;
  const Dropdown = window.Components.Dropdown;
  const videoRef = React.useRef(null);
  const hlsRef = React.useRef(null);
  const playbackUrl = stream?.playback_url;
  const clipOptions = [30, 60, 120, 300].map((seconds) => ({
    value: seconds,
    label: window.AppHelpers.durationLabel(seconds),
  }));

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;

    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    video.removeAttribute("src");
    video.load();

    if (!playbackUrl) return undefined;

    if (window.Hls && window.Hls.isSupported()) {
      const hls = new window.Hls({
        lowLatencyMode: true,
        liveSyncDurationCount: 3,
        maxLiveSyncPlaybackRate: 1.5,
      });
      hlsRef.current = hls;
      hls.loadSource(playbackUrl);
      hls.attachMedia(video);
      hls.on(window.Hls.Events.ERROR, (_event, data) => {
        if (data?.fatal) {
          if (data.type === window.Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad();
          else if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError();
          else hls.destroy();
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = playbackUrl;
    }

    const playPromise = video.play();
    if (playPromise?.catch) playPromise.catch(() => {});

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [playbackUrl]);

  const hasPlayback = Boolean(playbackUrl);
  const live = stream?.active || preview?.is_live;
  const title = window.AppHelpers.titleForPreview(preview);

  return (
    <main className="stage">
      <div className="channel-meta">
        <h1 className="channel-name">{selectedChannel || "No channel selected"}</h1>
        <div className="channel-title">{title}</div>
      </div>

      <section className="player-shell">
        {live && (
          <div className="live-badge">
            <span className="live-dot" /> LIVE
          </div>
        )}
        {hasPlayback ? (
          <video ref={videoRef} controls playsInline />
        ) : (
          <div className="placeholder">video player</div>
        )}
      </section>

      <div className="stage-actions">
        <span className="clip-split">
          <button className="btn primary" disabled={!stream?.recording} onClick={onClip}>
            <Icon name="scissors" />
            Clip ({window.AppHelpers.durationLabel(clipDuration)})
          </button>
          <Dropdown
            title="Clip duration"
            value={clipDuration}
            options={clipOptions}
            onChange={(seconds) => onClipDuration(Number(seconds))}
            className="clip-duration-dropdown"
            buttonClassName="clip-menu-button"
            renderValue={() => ""}
          />
        </span>
        <button className="btn" onClick={onOpenClips}>
          <Icon name="folder" /> Open Clips Folder
        </button>
      </div>
    </main>
  );
};
