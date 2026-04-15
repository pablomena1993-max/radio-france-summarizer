"""Client pour l'API Radio France v1 — listing des podcasts récents par catégorie."""

from datetime import datetime, timedelta

import httpx
from config import RADIO_FRANCE_API_BASE, RADIO_FRANCE_TOKEN, STATIONS

HEADERS = {
    "x-token": RADIO_FRANCE_TOKEN,
    "Accept": "application/x.radiofrance.mobileapi+json",
    "User-Agent": "AppRF",
}


def _fetch_station_diffusions(station_id: str, page: int = 0) -> dict:
    """Récupère une page de diffusions pour une station."""
    url = f"{RADIO_FRANCE_API_BASE}/stations/{station_id}/diffusions"
    params = [
        ("filter[manifestations][exists]", "true"),
        ("include", "show"),
        ("include", "manifestations"),
        ("include", "themes"),
        ("page[offset]", str(page)),
    ]
    resp = httpx.get(url, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_all_recent_podcasts(hours: int = 24) -> list[dict]:
    """
    Récupère tous les podcasts des dernières `hours` heures
    sur l'ensemble des stations Radio France.

    Retourne une liste de dicts triés par catégorie, chacun contenant :
    - id, title, description, date, duration, mp3_url
    - show_name, station_name, themes (liste de noms de catégories)
    """
    cutoff = datetime.now().timestamp() - (hours * 3600)
    all_podcasts = []
    seen_ids = set()

    for station in STATIONS:
        sid = station["id"]
        sname = station["name"]
        page = 0

        while True:
            data = _fetch_station_diffusions(sid, page)
            taxonomies = data.get("included", {}).get("taxonomies", {})
            manifestations = data.get("included", {}).get("manifestations", {})
            shows = data.get("included", {}).get("shows", {})

            found_old = False

            for item in data.get("data", []):
                diff = item.get("diffusions", item)
                start_time = diff.get("startTime", 0)

                # Ignorer les épisodes trop anciens
                if start_time < cutoff:
                    found_old = True
                    continue

                diff_id = diff.get("id", diff.get("diffusionId", ""))
                if diff_id in seen_ids:
                    continue
                seen_ids.add(diff_id)

                # Récupérer le MP3 principal
                mp3_url = None
                duration = 0
                rel_manifs = diff.get("relationships", {}).get("manifestations", [])
                for m_id in rel_manifs:
                    m = manifestations.get(m_id, {})
                    if m.get("mediaType") in ("youtube", "dailymotion"):
                        continue
                    if m.get("principal", False) or m.get("mediaType") == "mp3":
                        mp3_url = m.get("url")
                        duration = m.get("duration", 0)
                        break

                if not mp3_url:
                    continue

                # Récupérer les thèmes
                theme_ids = diff.get("relationships", {}).get("themes", [])
                theme_names = []
                for tid in theme_ids:
                    t = taxonomies.get(tid, {})
                    if t.get("type") == "theme":
                        theme_names.append(t.get("name", "Autre"))

                if not theme_names:
                    theme_names = ["Autre"]

                # Récupérer le nom de l'émission
                show_ids = diff.get("relationships", {}).get("show", [])
                show_name = ""
                for s_id in show_ids:
                    show_name = shows.get(s_id, {}).get("title", "")
                    if show_name:
                        break

                all_podcasts.append({
                    "id": diff_id,
                    "title": diff.get("title", "Sans titre"),
                    "description": diff.get("standfirst", ""),
                    "date": start_time,
                    "duration": duration,
                    "mp3_url": mp3_url,
                    "show_name": show_name,
                    "station_name": sname,
                    "themes": theme_names,
                })

            # Arrêter si on a trouvé des épisodes anciens ou pas de page suivante
            if found_old or "next" not in data.get("links", {}):
                break
            page += 1

    # Trier par date décroissante
    all_podcasts.sort(key=lambda p: p["date"], reverse=True)
    return all_podcasts


def group_by_theme(podcasts: list[dict]) -> dict[str, list[dict]]:
    """
    Groupe les podcasts par catégorie/thème.
    Un podcast avec plusieurs thèmes apparaît dans chaque catégorie.
    """
    groups: dict[str, list[dict]] = {}
    for p in podcasts:
        for theme in p["themes"]:
            groups.setdefault(theme, []).append(p)

    # Trier les catégories par nombre de podcasts décroissant
    return dict(sorted(groups.items(), key=lambda x: -len(x[1])))
