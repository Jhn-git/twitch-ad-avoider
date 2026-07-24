window.Components = window.Components || {};

window.Components.ClipEditor = function ClipEditor({
  api,
  clip,
  open,
  onClose,
  onClipUpdate,
  onToast,
}) {
  const Icon = window.Components.Icon;
  const videoRef = React.useRef(null);
  const hlsRef = React.useRef(null);
  const pendingTailSelectionRef = React.useRef(null);
  const [selectionStart, setSelectionStart] = React.useState(0);
  const [selectionEnd, setSelectionEnd] = React.useState(1);
  const [title, setTitle] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  const previewDuration = Math.max(1, Number(clip?.preview_duration_seconds || 1));
  const busyStatuses = [
    "capturing_postroll",
    "rendering_postroll",
    "preparing_preview",
    "capturing_tail",
    "saving",
  ];
  const busy = saving || busyStatuses.includes(clip?.status);
  const editable = Boolean(clip?.preview_url) && !busy;

  React.useEffect(() => {
    if (!clip?.id) return;
    setTitle(clip.title || "");
  }, [clip?.id]);

  React.useEffect(() => {
    if (!clip?.id) return;
    const pending = pendingTailSelectionRef.current;
    if (pending && pending.clipId === clip.id) {
      const addedDuration = Math.max(0, previewDuration - pending.previewDuration);
      setSelectionStart(Math.min(pending.start, previewDuration - 1));
      setSelectionEnd(Math.min(previewDuration, pending.end + addedDuration));
      pendingTailSelectionRef.current = null;
      return;
    }
    setSelectionStart(Number(clip.selection_start_seconds || 0));
    setSelectionEnd(Number(clip.selection_end_seconds || 1));
  }, [clip?.id, clip?.preview_revision]);

  React.useEffect(() => {
    if (!open || !clip?.preview_url || !videoRef.current) return undefined;
    const video = videoRef.current;
    const url = clip.preview_url;
    let hls = null;
    if (/\.m3u8(?:\?|$)/i.test(url) && window.Hls?.isSupported()) {
      hls = new window.Hls();
      hls.loadSource(url);
      hls.attachMedia(video);
      hlsRef.current = hls;
    } else {
      video.src = url;
    }
    return () => {
      if (hls) hls.destroy();
      if (hlsRef.current === hls) hlsRef.current = null;
      video.pause();
      video.removeAttribute("src");
      video.load();
    };
  }, [open, clip?.id, clip?.preview_url, clip?.preview_revision]);

  const restartAt = React.useCallback((start, end) => {
    const video = videoRef.current;
    if (!video) return;
    const safeStart = Math.max(0, Math.min(start, Math.max(0, end - 0.05)));
    video.currentTime = safeStart;
    video.play().catch(() => {});
  }, []);

  const restartSelection = () => restartAt(selectionStart, selectionEnd);

  const applySelection = (nextStart, nextEnd) => {
    const boundedStart = window.AppHelpers.clampRatio(nextStart, 0, previewDuration - 1);
    const boundedEnd = window.AppHelpers.clampRatio(nextEnd, boundedStart + 1, previewDuration);
    setSelectionStart(boundedStart);
    setSelectionEnd(boundedEnd);
    window.requestAnimationFrame(() => restartAt(boundedStart, boundedEnd));
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.currentTime < selectionStart - 0.05 || video.currentTime >= selectionEnd - 0.03) {
      restartAt(selectionStart, selectionEnd);
    }
  };

  const requestMoreTail = () => {
    pendingTailSelectionRef.current = {
      clipId: clip.id,
      start: selectionStart,
      end: selectionEnd,
      previewDuration,
    };
    api.request_clip_tail_extension(clip.id, 5).then((result) => {
      if (!result.ok) {
        pendingTailSelectionRef.current = null;
        onToast({ kind: "error", message: result.error || "Could not capture more footage" });
        return;
      }
      if (result.clip) onClipUpdate(result.clip);
    }).catch((error) => {
      pendingTailSelectionRef.current = null;
      onToast({ kind: "error", message: String(error) });
    });
  };

  const saveAndReturn = () => {
    setSaving(true);
    api.save_clip_edit(clip.id, selectionStart, selectionEnd, title).then((result) => {
      if (!result.ok) {
        onToast({ kind: "error", message: result.error || "Clip save failed" });
        if (result.clip) onClipUpdate(result.clip);
        return;
      }
      if (result.clip) onClipUpdate(result.clip);
      onToast({ kind: "success", message: `Saved ${result.clip?.filename || "clip"}` });
      onClose();
    }).catch((error) => {
      onToast({ kind: "error", message: String(error) });
    }).finally(() => setSaving(false));
  };

  if (!open || !clip) return null;

  const startPct = (selectionStart / previewDuration) * 100;
  const endPct = (selectionEnd / previewDuration) * 100;
  const titleSlug = window.AppHelpers.kebabSlug(title).slice(0, 80);
  const requestedFilename = `${clip.base_name}${titleSlug ? `-${titleSlug}` : ""}.mp4`;
  const computedFilename = title === (clip.title || "")
    ? (clip.computed_filename || clip.filename || requestedFilename)
    : requestedFilename;
  const statusKind = clip.error ? "error" : busy ? "working" : "ready";

  return (
    <section className="clip-editor-drawer" aria-label="Recent clip editor">
      <header className="clip-editor-header">
        <div>
          <div className="clip-editor-eyebrow">Recent clip</div>
          <h2>Trim and name</h2>
        </div>
        <button className="icon-btn" onClick={onClose} title="Close clip editor">
          <Icon name="close" />
        </button>
      </header>

      <div className="clip-editor-body">
        <div className="clip-editor-preview">
          <video
            ref={videoRef}
            controls
            playsInline
            onLoadedMetadata={restartSelection}
            onTimeUpdate={handleTimeUpdate}
          />
          <div className={`clip-editor-status ${statusKind}`}>
            {clip.message || "Clip ready"}
          </div>
        </div>

        <div className="clip-editor-controls">
          <label className="clip-title-field">
            <span>Short title</span>
            <input
              value={title}
              maxLength="120"
              placeholder="Batman Cape look"
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <div className="clip-filename-preview">{computedFilename}</div>

          <div className={`trim-control ${editable ? "" : "is-disabled"}`}>
            <div className="trim-label-row">
              <span>Start {window.AppHelpers.timeLabel(selectionStart)}</span>
              <span>End {window.AppHelpers.timeLabel(selectionEnd)}</span>
            </div>
            <div className="trim-track">
              <div className="trim-selection" style={{
                left: `${startPct}%`,
                width: `${Math.max(0, endPct - startPct)}%`,
              }} />
              <input
                className="trim-range trim-start"
                type="range"
                aria-label="Clip start"
                min="0"
                max={Math.max(0, selectionEnd - 1)}
                step="0.05"
                value={selectionStart}
                disabled={!editable}
                onChange={(event) => setSelectionStart(Number(event.target.value))}
                onPointerUp={restartSelection}
                onKeyUp={restartSelection}
              />
              <input
                className="trim-range trim-end"
                type="range"
                aria-label="Clip end"
                min={Math.min(previewDuration, selectionStart + 1)}
                max={previewDuration}
                step="0.05"
                value={selectionEnd}
                disabled={!editable}
                onChange={(event) => setSelectionEnd(Number(event.target.value))}
                onPointerUp={restartSelection}
                onKeyUp={restartSelection}
              />
            </div>
          </div>

          <div className="clip-nudge-grid">
            <div>
              <span>Start</span>
              <button className="btn compact" disabled={!editable} onClick={() => (
                applySelection(selectionStart - 1, selectionEnd)
              )}>-1s</button>
              <button className="btn compact" disabled={!editable} onClick={() => (
                applySelection(selectionStart + 1, selectionEnd)
              )}>+1s</button>
            </div>
            <div>
              <span>End</span>
              <button className="btn compact" disabled={!editable} onClick={() => (
                applySelection(selectionStart, selectionEnd - 1)
              )}>-1s</button>
              <button className="btn compact" disabled={!editable} onClick={requestMoreTail}>
                Capture +5s
              </button>
            </div>
          </div>

          {clip.error && <div className="clip-editor-error">{clip.error}</div>}

          <div className="clip-editor-actions">
            <button className="btn" onClick={onClose}>Close</button>
            <button className="btn primary" disabled={!editable} onClick={saveAndReturn}>
              <Icon name="save" /> Save &amp; Return
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
