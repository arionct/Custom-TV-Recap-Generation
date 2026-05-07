"""
Lexicographic ordering helpers for (season, episode) tuples.
Used for deterministic corpus filtering and evaluation buckets (prior vs future).
"""

from __future__ import annotations


def ep_tuple(season: int, episode: int) -> tuple[int, int]:
    return (season, episode)


def strictly_before(
    season: int,
    episode: int,
    k_season: int,
    k_episode: int,
) -> bool:
    return ep_tuple(season, episode) < ep_tuple(k_season, k_episode)


def strictly_after(
    season: int,
    episode: int,
    k_season: int,
    k_episode: int,
) -> bool:
    return ep_tuple(season, episode) > ep_tuple(k_season, k_episode)


def at_stopping_episode(
    season: int,
    episode: int,
    k_season: int,
    k_episode: int,
) -> bool:
    return season == k_season and episode == k_episode
