
def normalize_heading(heading):
    """Normalize any angle to 0-359"""
    return round(heading + 360) % 360