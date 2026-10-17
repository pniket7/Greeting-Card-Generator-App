"""
Occasion and relationship metadata mapping for Greeting Card Notes,
based on the Notion specification.
"""

# Categories
CATEGORIES = {
    "celebrate": "Celebrate them",
    "thank": "Thank them",
    "comfort": "Comfort them"
}

# Closeness Levels
CLOSENESS_LEVELS = {
    "formal": "Formal",
    "friendly": "Friendly",
    "warm": "Warm",
    "close": "Close",
    "very_close": "Very Close"
}

# Relationships
RELATIONSHIPS = {
    "friend": "Friend",
    "colleague": "Colleague",
    "sibling": "Sibling",
    "spouse": "Spouse",
    "parent": "Parent",
    "parent-in-law": "Parent-in-law",
    "acquaintance": "Acquaintance",
    "other": "Other"
}

# Intents
INTENTS = {
    "acknowledge_the_effort": "Acknowledge the effort",
    "mark_the_milestone": "Mark the milestone",
    "share_the_happiness": "Share the happiness"
}

# Feeling Definitions
FEELINGS = {
    "proud": "Proud (Personally invested in what the recipient accomplished)",
    "admiring": "Admiring (Respects the recipient's ability, effort, or way of working)",
    "pleased": "Pleased (Reserved satisfaction that a good outcome came through)",
    "delighted": "Delighted (Immediate happiness on hearing/receiving meaningful news)",
    "reflective": "Reflective (Attentive to the history and significance behind the moment)",
    "warm": "Warm (Affection or goodwill directed toward the recipient)",
    "excited": "Excited (Energetic enthusiasm about the occasion and what is beginning)"
}

# Mappings of Specific Moments to Intents and Feelings (Occasion Metadata)
MOMENT_METADATA = {
    "graduation": {
        "category": "celebrate",
        "label": "Graduation",
        "default_intent": "acknowledge_the_effort",
        "default_feeling": "proud"
    },
    "promotion": {
        "category": "celebrate",
        "label": "Promotion",
        "default_intent": "acknowledge_the_effort",
        "default_feeling": "admiring"
    },
    "new_business": {
        "category": "celebrate",
        "label": "New Business",
        "default_intent": "acknowledge_the_effort",
        "default_feeling": "admiring"
    },
    "publication": {
        "category": "celebrate",
        "label": "Publication",
        "default_intent": "acknowledge_the_effort",
        "default_feeling": "admiring"
    },
    "award_or_recognition": {
        "category": "celebrate",
        "label": "Award or Recognition",
        "default_intent": "acknowledge_the_effort",
        "default_feeling": "proud"
    },
    "new_job": {
        "category": "celebrate",
        "label": "New Job",
        "default_intent": "acknowledge_the_effort",
        "default_feeling": "pleased"
    },
    "new_home": {
        "category": "celebrate",
        "label": "New Home",
        "default_intent": "acknowledge_the_effort",
        "default_feeling": "pleased"
    },
    "engagement": {
        "category": "celebrate",
        "label": "Engagement",
        "default_intent": "mark_the_milestone",
        "default_feeling": "delighted"
    },
    "pregnancy_announcement": {
        "category": "celebrate",
        "label": "Pregnancy Announcement",
        "default_intent": "mark_the_milestone",
        "default_feeling": "delighted"
    },
    "retirement": {
        "category": "celebrate",
        "label": "Retirement",
        "default_intent": "mark_the_milestone",
        "default_feeling": "reflective"
    },
    "birthday": {
        "category": "celebrate",
        "label": "Birthday",
        "default_intent": "share_the_happiness",
        "default_feeling": "warm"
    },
    "wedding": {
        "category": "celebrate",
        "label": "Wedding",
        "default_intent": "share_the_happiness",
        "default_feeling": "excited"
    },
    "anniversary": {
        "category": "celebrate",
        "label": "Anniversary",
        "default_intent": "share_the_happiness",
        "default_feeling": "reflective"
    },
    "new_baby": {
        "category": "celebrate",
        "label": "New Baby",
        "default_intent": "share_the_happiness",
        "default_feeling": "delighted"
    }
}


def get_moment_defaults(moment_key):
    """
    Get the default intent and feeling for a specific moment key.
    
    :param moment_key: The string identifier of the specific moment.
    :return: dict with category, default_intent, default_feeling, or None if not found.
    """
    return MOMENT_METADATA.get(moment_key)
