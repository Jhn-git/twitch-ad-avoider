window.Components = window.Components || {};

// video.buffered's end doesn't grow smoothly - it jumps forward each time a new
// segment lands, then holds flat while currentTime catches up to it. So the gap
// naturally sawtooths even while parked at live. Hysteresis (separate enter/exit
// thresholds) keeps a single segment arrival from flipping isLive back and forth.
const LIVE_EDGE_ENTER_SECONDS = 4;
const LIVE_EDGE_EXIT_SECONDS = 10;
// Well above LIVE_EDGE_EXIT_SECONDS - only trips for a genuinely large gap
// (stream startup, or a rare stall recovery), never for the everyday sawtooth.
const EMERGENCY_GAP_SECONDS = 15;
// Deliberately mild: closes a few seconds of drift within well under a
// minute, but stays slow enough that speech never sounds sped up.
const CATCHUP_PLAYBACK_RATE = 1.1;
// Floor for the live-buffer highlight's width within the session-scaled scrub
// track, so it stays comfortably draggable even once the session has run long
// enough that the real buffered window is a tiny sliver of the whole session.
const MIN_LIVE_WINDOW_PCT = 10;

window.Components.VideoStage = function VideoStage({
  selectedChannel,
  preview,
  stream,
  clipDuration,
  onClipDuration,
  onClip,
  onOpenClips,
  segmentsIndex,
  onToast,
}) {
  const Icon = window.Components.Icon;
  const Dropdown = window.Components.Dropdown;
  const videoRef = React.useRef(null);
  const hlsRef = React.useRef(null);
  const scrubTrackRef = React.useRef(null);
  const liveWindowRef = React.useRef(null);
  const scrubFillRef = React.useRef(null);
  const scrubThumbRef = React.useRef(null);
  const draggingRef = React.useRef(false);
  const isLiveRef = React.useRef(true);
  const userSeekedRef = React.useRef(false);
  const segmentsIndexRef = React.useRef(segmentsIndex);
  const timelineBoundsRef = React.useRef(null);
  const [isLive, setIsLive] = React.useState(true);
  const playbackUrl = stream?.playback_url;
  const previewImageUrl = preview?.preview_image_url;
  const [previewImageFailed, setPreviewImageFailed] = React.useState(false);
  const clipOptions = [30, 60, 120, 300].map((seconds) => ({
    value: seconds,
    label: window.AppHelpers.durationLabel(seconds),
  }));
  const clipReadySeconds = Number(stream?.clip_ready_seconds || 0);
  const clipReady = Boolean(
    stream?.recording && stream?.clip_ready && clipReadySeconds >= clipDuration
  );
  const defaultClipWarmupReason =
    `Recording is warming up (${Math.floor(clipReadySeconds)}s captured for a ${clipDuration}s clip).`;
  const clipWarmupReason = clipReady
    ? "Create clip"
    : (stream?.clip_warmup_reason || defaultClipWarmupReason);

  React.useEffect(() => {
    setPreviewImageFailed(false);
  }, [previewImageUrl]);

  // Session bounds (stream start -> now), shared by the segment background
  // bands and the live-buffer highlight below so both agree on the same scale.
  const timelineBounds = React.useMemo(() => {
    if (!segmentsIndex || !segmentsIndex.segments || !segmentsIndex.segments.length) return null;
    return window.AppHelpers.computeTimelineBounds(segmentsIndex);
  }, [segmentsIndex]);

  // Read via refs inside updateSeekVisuals (rather than as a dependency) so
  // segmentsIndex refreshing doesn't change updateSeekVisuals's identity and
  // re-trigger the hls attach effect below.
  React.useEffect(() => {
    segmentsIndexRef.current = segmentsIndex;
  }, [segmentsIndex]);
  React.useEffect(() => {
    timelineBoundsRef.current = timelineBounds;
  }, [timelineBounds]);

  const updateSeekVisuals = React.useCallback((video) => {
    if (!video.buffered || !video.buffered.length) return;
    const bufferedStart = video.buffered.start(0);
    const bufferedEnd = video.buffered.end(video.buffered.length - 1);
    const span = Math.max(0.001, bufferedEnd - bufferedStart);

    // Position the live-buffer highlight within the session-scaled track by
    // converting the buffered range to wall-clock time (video.currentTime
    // advances 1:1 with wall-clock time on a live source) and reusing the
    // same bounds/ratio math as the day-timeline segments. Falls back to a
    // full-width highlight when there's no session data yet.
    const bounds = timelineBoundsRef.current;
    const segmentsIndexNow = segmentsIndexRef.current;
    let liveLeftPct = 0;
    let liveWidthPct = 100;
    if (bounds && segmentsIndexNow) {
      const nowMs = segmentsIndexNow.now ? new Date(segmentsIndexNow.now).getTime() : Date.now();
      const bufferedStartWall = new Date(nowMs - (bufferedEnd - bufferedStart) * 1000);
      const rawLeft = window.AppHelpers.timestampToRatio(bufferedStartWall, bounds) * 100;
      // Never let the highlight shrink below MIN_LIVE_WINDOW_PCT, anchored to
      // the live (right) edge - once the session runs long relative to the
      // buffer window this is no longer strictly proportional, but it stays
      // draggable instead of collapsing to an unusable sliver.
      liveLeftPct = Math.min(rawLeft, 100 - MIN_LIVE_WINDOW_PCT);
      liveWidthPct = 100 - liveLeftPct;
    }
    if (liveWindowRef.current) {
      liveWindowRef.current.style.left = `${liveLeftPct}%`;
      liveWindowRef.current.style.width = `${liveWidthPct}%`;
    }

    const ratio = window.AppHelpers.clampRatio((video.currentTime - bufferedStart) / span, 0, 1);
    if (scrubFillRef.current) scrubFillRef.current.style.width = `${ratio * 100}%`;
    if (scrubThumbRef.current) scrubThumbRef.current.style.left = `${ratio * 100}%`;
    // Measured against the true buffered end (what dragging can actually reach),
    // not hls.js's own conservative liveSyncPosition target - for this stream's
    // segment cadence that target sits far enough behind the real edge that
    // comparing against it made "live" nearly unreachable.
    const gap = bufferedEnd - video.currentTime;
    const nowLive = isLiveRef.current ? gap <= LIVE_EDGE_EXIT_SECONDS : gap <= LIVE_EDGE_ENTER_SECONDS;
    if (nowLive !== isLiveRef.current) {
      isLiveRef.current = nowLive;
      setIsLive(nowLive);
    }
  }, []);

  // Shared by the Go Live button and the automatic emergency catch-up below -
  // an instant, clean seek to the true buffered edge. Re-arms auto catch-up
  // (userSeekedRef = false) since landing on live is exactly what a deliberate
  // rewind would otherwise be protecting the user from being pulled out of.
  const syncToLiveEdge = React.useCallback(
    (video) => {
      if (!video.buffered || !video.buffered.length) return;
      video.currentTime = Math.max(0, video.buffered.end(video.buffered.length - 1) - 0.5);
      video.playbackRate = 1;
      userSeekedRef.current = false;
      if (video.paused) {
        const playPromise = video.play();
        if (playPromise?.catch) playPromise.catch(() => {});
      }
      updateSeekVisuals(video);
    },
    [updateSeekVisuals]
  );

  // Runs every timeupdate/progress tick, right after updateSeekVisuals (so
  // isLiveRef already reflects the current gap). Never fights a deliberate
  // rewind or a paused video. A large gap - stream startup, or a rare stall -
  // gets one clean instant seek, the same jump Go Live already does. A
  // smaller "not live" gap is closed quietly with a mild capped playback
  // rate instead of a visible jump, and dropped back to 1x once caught up.
  const maybeAutoCatchUp = React.useCallback(
    (video) => {
      if (!video.buffered || !video.buffered.length) return;
      if (userSeekedRef.current || video.paused) {
        if (video.playbackRate !== 1) video.playbackRate = 1;
        return;
      }
      const bufferedEnd = video.buffered.end(video.buffered.length - 1);
      const gap = bufferedEnd - video.currentTime;
      if (gap > EMERGENCY_GAP_SECONDS) {
        syncToLiveEdge(video);
        return;
      }
      const targetRate = isLiveRef.current ? 1 : CATCHUP_PLAYBACK_RATE;
      if (video.playbackRate !== targetRate) video.playbackRate = targetRate;
    },
    [syncToLiveEdge]
  );

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;

    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    video.removeAttribute("src");
    video.load();
    video.playbackRate = 1;
    userSeekedRef.current = false;

    if (!playbackUrl) return undefined;

    if (window.Hls && window.Hls.isSupported()) {
      const hls = new window.Hls({
        lowLatencyMode: true,
        liveSyncDurationCount: 3,
        // hls.js would otherwise speed playback up to this rate whenever
        // currentTime falls behind its live-sync target - including when the
        // user deliberately scrubbed backward. The Go Live button is now the
        // explicit way to catch back up, so auto speed-up is disabled (1 = off).
        maxLiveSyncPlaybackRate: 1,
        backBufferLength: 900,
        liveBackBufferLength: 900,
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

    isLiveRef.current = true;
    setIsLive(true);
    const handleTimeUpdate = () => {
      updateSeekVisuals(video);
      maybeAutoCatchUp(video);
    };
    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("progress", handleTimeUpdate);

    return () => {
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("progress", handleTimeUpdate);
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [playbackUrl, updateSeekVisuals, maybeAutoCatchUp]);

  const seekFromEvent = (evt) => {
    const track = liveWindowRef.current;
    const video = videoRef.current;
    if (!track || !video || !video.buffered || !video.buffered.length) return;
    const rect = track.getBoundingClientRect();
    if (rect.width <= 0) return;
    const ratio = window.AppHelpers.clampRatio((evt.clientX - rect.left) / rect.width, 0, 1);
    const bufferedStart = video.buffered.start(0);
    const bufferedEnd = video.buffered.end(video.buffered.length - 1);
    video.currentTime = bufferedStart + ratio * (bufferedEnd - bufferedStart);
    userSeekedRef.current = true;
    updateSeekVisuals(video);
  };

  const handleSeekPointerDown = (evt) => {
    draggingRef.current = true;
    try {
      evt.currentTarget.setPointerCapture(evt.pointerId);
    } catch (_e) {
      // pointer capture unavailable for this pointer type; dragging still works via listeners
    }
    seekFromEvent(evt);
  };
  const handleSeekPointerMove = (evt) => {
    if (draggingRef.current) seekFromEvent(evt);
  };
  const handleSeekPointerUp = (evt) => {
    draggingRef.current = false;
    try {
      evt.currentTarget.releasePointerCapture(evt.pointerId);
    } catch (_e) {
      // pointer capture may already be released
    }
  };

  const goLive = () => {
    const video = videoRef.current;
    if (!video) return;
    syncToLiveEdge(video);
  };

  const handleClip = () => {
    const video = videoRef.current;
    let behindLiveSeconds = 0;
    if (video && video.buffered && video.buffered.length) {
      const bufferedEnd = video.buffered.end(video.buffered.length - 1);
      behindLiveSeconds = Math.max(0, bufferedEnd - video.currentTime);
    }
    onClip(behindLiveSeconds);
  };

  // Full-day recorded-history strip: shows today's recorded segments (and the
  // gaps between them, e.g. from closing and reopening the app) across the
  // whole stream's timeline, not just what hls.js still has buffered.
  const dayTimelineBands = React.useMemo(() => {
    if (!segmentsIndex || !segmentsIndex.segments || !segmentsIndex.segments.length || !timelineBounds) return [];
    const now = segmentsIndex.now ? new Date(segmentsIndex.now) : new Date();
    const currentId = window.AppHelpers.currentSegment(segmentsIndex)?.id;
    return segmentsIndex.segments.map((segment) => {
      const start = new Date(segment.start);
      const end = segment.end ? new Date(segment.end) : now;
      const leftPct = window.AppHelpers.timestampToRatio(start, timelineBounds) * 100;
      const rightPct = window.AppHelpers.timestampToRatio(end, timelineBounds) * 100;
      return {
        key: segment.id,
        leftPct,
        widthPct: Math.max(0.6, rightPct - leftPct),
        isCurrent: segment.id === currentId,
      };
    });
  }, [segmentsIndex, timelineBounds]);

  const handleDayTimelineClick = (evt) => {
    const track = scrubTrackRef.current;
    const video = videoRef.current;
    if (!track || !video || !segmentsIndex || !segmentsIndex.segments.length) return;
    const rect = track.getBoundingClientRect();
    if (rect.width <= 0) return;
    const ratio = window.AppHelpers.clampRatio((evt.clientX - rect.left) / rect.width, 0, 1);
    const bounds = window.AppHelpers.computeTimelineBounds(segmentsIndex);
    const target = window.AppHelpers.ratioToTimestamp(ratio, bounds);
    const segment = window.AppHelpers.findSegmentAt(segmentsIndex, target);
    const currentId = window.AppHelpers.currentSegment(segmentsIndex)?.id;

    if (!segment) {
      onToast?.({ kind: "info", message: "Nothing was recorded then - the app was probably closed." });
      return;
    }
    if (segment.id !== currentId) {
      onToast?.({ kind: "info", message: "Scrubbing into earlier sessions is coming soon." });
      return;
    }
    if (!video.buffered || !video.buffered.length) return;

    // Reuse the same "seconds behind live" reasoning handleClip already sends
    // to the backend: video.currentTime advances 1:1 with wall-clock time on a
    // live source, so the gap from "now" maps directly onto the buffered range.
    const nowMs = segmentsIndex.now ? new Date(segmentsIndex.now).getTime() : Date.now();
    const behindLiveSeconds = (nowMs - target.getTime()) / 1000;
    const bufferedStart = video.buffered.start(0);
    const bufferedEnd = video.buffered.end(video.buffered.length - 1);
    const desiredTime = bufferedEnd - behindLiveSeconds;

    if (desiredTime < bufferedStart) {
      onToast?.({
        kind: "info",
        message: "That's further back than what's currently loaded - loading it is coming soon.",
      });
      return;
    }
    video.currentTime = window.AppHelpers.clampRatio(desiredTime, bufferedStart, bufferedEnd);
    userSeekedRef.current = true;
    updateSeekVisuals(video);
  };

  const hasPlayback = Boolean(playbackUrl);
  const live = stream?.active || preview?.is_live;
  const showPreviewImage = Boolean(
    !hasPlayback && selectedChannel && preview?.is_live && previewImageUrl && !previewImageFailed
  );
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
        ) : showPreviewImage ? (
          <img
            className="stream-preview-image"
            src={previewImageUrl}
            alt=""
            onError={() => setPreviewImageFailed(true)}
          />
        ) : (
          <div className="placeholder">video player</div>
        )}
      </section>

      {hasPlayback && (
        <div className="scrub-row">
          <div className="scrub-track" ref={scrubTrackRef} onClick={handleDayTimelineClick}>
            {dayTimelineBands.map((band) => (
              <div
                key={band.key}
                className={`scrub-segment ${band.isCurrent ? "is-current" : "is-past"}`}
                style={{ left: `${band.leftPct}%`, width: `${band.widthPct}%` }}
              />
            ))}
            <div
              className="scrub-live-window"
              ref={liveWindowRef}
              onClick={(evt) => evt.stopPropagation()}
              onPointerDown={handleSeekPointerDown}
              onPointerMove={handleSeekPointerMove}
              onPointerUp={handleSeekPointerUp}
              onPointerCancel={handleSeekPointerUp}
            >
              <div className="scrub-fill" ref={scrubFillRef} />
              <div className="scrub-thumb" ref={scrubThumbRef} />
            </div>
          </div>
          <button className={`btn go-live-btn ${isLive ? "is-live" : ""}`} disabled={isLive} onClick={goLive}>
            <Icon name="skipToLive" /> Go Live
          </button>
        </div>
      )}

      <div className="stage-actions">
        <span className="clip-split">
          <button
            className="btn primary"
            disabled={!clipReady}
            onClick={handleClip}
            title={clipWarmupReason}
          >
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
