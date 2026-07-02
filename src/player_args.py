"""Helpers for normalizing managed player arguments."""

import shlex
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class ManagedCacheFlags:
    """Cache-flag vocabulary for one player, plus how to build them from a duration."""

    flag_names: Tuple[str, ...]
    build: Callable[[int], List[str]]


def _build_vlc_cache_args(cache_duration_seconds: int) -> List[str]:
    """Return VLC cache flags for a cache duration in seconds."""
    if cache_duration_seconds <= 0:
        return []

    cache_duration_ms = cache_duration_seconds * 1000
    return [
        f"--network-caching={cache_duration_ms}",
        f"--file-caching={cache_duration_ms}",
        f"--live-caching={cache_duration_ms}",
    ]


MANAGED_CACHE_FLAGS: Dict[str, ManagedCacheFlags] = {
    "vlc": ManagedCacheFlags(
        flag_names=("--network-caching", "--file-caching", "--live-caching"),
        build=_build_vlc_cache_args,
    ),
}


def split_player_args(player_args: Optional[str]) -> List[str]:
    """Return a tokenized player argument list."""
    if not isinstance(player_args, str) or not player_args:
        return []
    return shlex.split(player_args)


def serialize_player_args(player_args: List[str]) -> Optional[str]:
    """Return a config-safe player argument string."""
    if not player_args:
        return None
    return shlex.join(player_args)


def _strip_flags(player_args: List[str], flag_names: Set[str]) -> List[str]:
    """Remove the given bare/`=`-valued flags (and their separate-token values)."""
    stripped_args: List[str] = []
    skip_next = False

    for index, arg in enumerate(player_args):
        if skip_next:
            skip_next = False
            continue

        if arg in flag_names:
            if index + 1 < len(player_args) and not player_args[index + 1].startswith("-"):
                skip_next = True
            continue

        if any(arg.startswith(f"{flag}=") for flag in flag_names):
            continue

        stripped_args.append(arg)

    return stripped_args


def strip_all_managed_cache_args(player_args: List[str]) -> List[str]:
    """Remove managed cache flags for every known player.

    Used during config migration, which doesn't know which player is active.
    """
    all_flags = {flag for spec in MANAGED_CACHE_FLAGS.values() for flag in spec.flag_names}
    return _strip_flags(player_args, all_flags)


def strip_managed_cache_args_for_player(player_key: str, player_args: List[str]) -> List[str]:
    """Remove managed cache flags for one player, used once the active player is known."""
    spec = MANAGED_CACHE_FLAGS.get(player_key)
    if spec is None:
        return player_args
    return _strip_flags(player_args, set(spec.flag_names))


def build_managed_cache_args_for_player(
    player_key: str, cache_duration_seconds: int
) -> List[str]:
    """Return the managed cache flags for one player and duration, or [] if unmanaged."""
    spec = MANAGED_CACHE_FLAGS.get(player_key)
    if spec is None:
        return []
    return spec.build(cache_duration_seconds)
