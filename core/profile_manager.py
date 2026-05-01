import os
import json
import settings

REPLAYS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "replays")


def assign_profile() -> str:
    """
    Scans replays/ for existing Profile_N folders and returns the next available name. Sets settings.profile_name automatically."""
    os.makedirs(REPLAYS_DIR, exist_ok=True)
    existing = []
    for name in os.listdir(REPLAYS_DIR):
        if name.startswith("Profile_"):
            try:
                existing.append(int(name.split("_")[1]))
            except (IndexError, ValueError):
                pass
    next_n               = max(existing) + 1 if existing else 1
    profile_name         = f"Profile_{next_n}"
    settings.profile_name = profile_name
    print(f"[Profile] Assigned: {profile_name}")
    return profile_name


def load_saved_profile(profile_name: str) -> dict | None:
    """Load a previously synthesised profile.json if it exists."""
    path = os.path.join(REPLAYS_DIR, profile_name, "profile.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Profile] Could not read profile: {e}")
    return None


def init_profile() -> tuple[str, dict | None]:
    """Call once at the input_menu → main transition. Returns (profile_name, saved_profile_or_None)."""
    profile_name   = assign_profile()
    saved_profile  = load_saved_profile(profile_name)
    return profile_name, saved_profile