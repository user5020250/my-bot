"""
jobs_data.py — central place to tweak job names & pay ranges.
"""

JOBS = {
    "call_center": {
        "label": "Call Center Agent",
        "emoji": "🎧",
        "min": 1500,
        "max": 4000,
        "flavor": "Pumasok ng graveyard shift para sa mga Amerikanong customer.",
    },
    "tricycle": {
        "label": "Tricycle Driver",
        "emoji": "🛺",
        "min": 1000,
        "max": 2500,
        "flavor": "Sunog-pahingahan sa tricycle terminal buong araw.",
    },
    "sari_sari": {
        "label": "Sari-Sari Store Owner",
        "emoji": "🏪",
        "min": 1200,
        "max": 3500,
        "flavor": "Nagbantay ng tindahan, nakipag-usap sa mga suki.",
    },
    "grab": {
        "label": "Grab Rider",
        "emoji": "🏍️",
        "min": 1500,
        "max": 5000,
        "flavor": "Nag-deliver ng food at pasahero buong shift.",
    },
    "construction": {
        "label": "Construction Worker",
        "emoji": "🧱",
        "min": 1000,
        "max": 3000,
        "flavor": "Nagpawis sa site, todo hakot ng semento at bakal.",
    },
    "student_hustle": {
        "label": "Student Side Hustle",
        "emoji": "🎓",
        "min": 500,
        "max": 2000,
        "flavor": "Nagbenta ng baon, tumulong mag-tutor, freelance gigs.",
    },
}

TRABAHO_COOLDOWN_SECONDS = 30 * 60  # 30 minutes
