"""
jobs_data.py — tweak job names, payouts, and flavor text here.
"""

JOBS = {
    "call_center": {
        "label": "Call Center Agent",
        "min": 1500,
        "max": 4000,
        "flavor": "Nag-survive ng graveyard shift at nakipagbardagulan sa customers.",
    },

    "tricycle": {
        "label": "Tricycle Driver",
        "min": 1000,
        "max": 2500,
        "flavor": "Umikot buong barangay para kumita ng extra cash.",
    },

    "sari_sari": {
        "label": "Sari-Sari Store Owner",
        "min": 1200,
        "max": 3500,
        "flavor": "Nagbantay ng tindahan at nakichika sa mga suki.",
    },

    "grab": {
        "label": "Grab Rider",
        "min": 1500,
        "max": 5000,
        "flavor": "Nakipagsabayan sa traffic para ma-deliver ang orders.",
    },

    "construction": {
        "label": "Construction Worker",
        "min": 1000,
        "max": 3000,
        "flavor": "Nagbuhat ng semento at nagpakapagod sa site.",
    },

    "student_hustle": {
        "label": "Student Side Hustle",
        "min": 500,
        "max": 2000,
        "flavor": "Kumita gamit ang side hustles imbes na mag-review.",
    },
}

TRABAHO_COOLDOWN_SECONDS = 8 * 60 * 60  # 8 hrs
