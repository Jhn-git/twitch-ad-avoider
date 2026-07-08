window.Components = window.Components || {};

window.Components.FavoritesRail = function FavoritesRail({
  favorites,
  selectedChannel,
  open,
  onToggle,
  onSelect,
  onAdd,
  onRemove,
  onPin,
  onRefresh,
}) {
  const Icon = window.Components.Icon;

  return (
    <aside className={`rail left ${open ? "" : "collapsed"}`}>
      <div className="rail-head">
        <span className="rail-title">Favorites</span>
        <div className="rail-actions">
          {open && (
            <button className="icon-btn" title="Refresh favorites" onClick={onRefresh}>
              <Icon name="refresh" />
            </button>
          )}
          <button
            className="icon-btn rail-toggle"
            title={open ? "Collapse favorites" : "Expand favorites"}
            onClick={() => onToggle(!open)}
          >
            <Icon name="chevron" />
          </button>
        </div>
      </div>
      <div className="favorites-list">
        {favorites.length === 0 && <div className="empty-state">No favorites yet</div>}
        {favorites.map((favorite) => {
          const channel = favorite.channel_name;
          const selected = channel === selectedChannel;
          return (
            <button
              key={channel}
              className={`favorite-row ${selected ? "selected" : ""} ${favorite.is_pinned ? "pinned" : ""}`}
              onClick={() => onSelect(channel)}
              onDoubleClick={() => onSelect(channel, true)}
            >
              <span
                className={`avatar ${favorite.is_live ? "live" : ""} ${favorite.profile_image_url ? "has-image" : ""}`}
                title={open ? undefined : channel}
              >
                {favorite.profile_image_url && (
                  <img src={favorite.profile_image_url} alt="" loading="lazy" />
                )}
              </span>
              <span className="fav-name" title={channel}>{channel}</span>
              <span className="rail-actions">
                <span
                  className="icon-btn pin"
                  title={favorite.is_pinned ? "Unpin" : "Pin"}
                  onClick={(event) => {
                    event.stopPropagation();
                    onPin(channel);
                  }}
                >
                  <Icon name="pin" />
                </span>
                {selected && (
                  <span
                    className="icon-btn"
                    title="Remove"
                    onClick={(event) => {
                      event.stopPropagation();
                      onRemove(channel);
                    }}
                  >
                    <Icon name="trash" />
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
      <button className="add-favorite" onClick={onAdd} title="Add favorite">
        <Icon name="plus" />
        <span>Add favorite</span>
      </button>
    </aside>
  );
};
