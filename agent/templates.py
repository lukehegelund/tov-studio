"""Luke's documented voice + pricing. Source: Take One Visuals/inquiry-system.md (Feb 2026).
Updated June 2026: pricing page retired — send leads to the homepage and invite a call
(425-524-5565) or to describe what they want so Luke can recommend a package.
"""

HOME_URL = "takeonevisuals.com"
PHONE = "425-524-5565"
PRICES = {"Ceremony": 1500, "Ceremony & Reception": 2500, "Full Day": 3500}
ADDONS = {"Raw footage": 200, "Social media reel": 300, "Additional hour": 300}
COVERAGE = "North Idaho, Eastern Washington (Spokane, CDA, Kennewick, Yakima)"

# AVAILABLE — used when the calendar shows the date is free (or the date is unknown).
def AVAILABLE(name):
    return (f"Hi {name}! Thanks for reaching out!\n\n"
            f"I'd love to be a part of your day. You can check out my work at {HOME_URL}.\n\n"
            f"If you'd like to talk through packages and details, feel free to give me a call at "
            f"{PHONE} — or just send me what you're looking for and I'll recommend the right "
            "package for you! :)")

# Back-compat alias (scanner used T.SAFE)
SAFE = AVAILABLE

# UNAVAILABLE — used when the calendar shows the date is already booked.
def UNAVAILABLE(name):
    return (f"Hi {name}! Unfortunately, I'm unavailable on that day. "
            "Best of luck finding a videographer!")

# FAR_OUT — wedding date is beyond Luke's current booking horizon (changeable cutoff).
def FAR_OUT(name):
    return (f"Hi {name}, thanks for reaching out!\n\n"
            "Unfortunately I'm not booking that far ahead yet. If you'd like, I can get back to "
            "you this winter with availability.")

# Needs-more-info (no date given and Luke wants to qualify first)
def NEED_INFO(name):
    return (f"Hi {name}! Thanks for reaching out! I'd love to learn more about what you're looking for.\n\n"
            "Could you share your wedding date and a bit about the coverage you're hoping for? Then I can "
            f"point you to the right package — or feel free to give me a call at {PHONE}.\n\n"
            "Looking forward to hearing more!")
