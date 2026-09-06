"""Session-language strings for template and fallback replies."""

from __future__ import annotations

import re

SUPPORTED = ("English", "Hindi", "Marathi", "Kannada")

# Topic keywords used to detect a multi-slot question dump in any language.
SLOT_TOPICS: dict[str, tuple[str, ...]] = {
    "state": ("state", "rajya", "\u0930\u093e\u091c\u094d\u092f", "\u0cb0\u0cbe\u0c9c\u0ccd\u0caf"),
    "age_group": ("age group", "age", "\u0906\u092f\u0941", "\u0935\u092f\u094b\u0917\u091f", "\u0cb5\u0caf\u0ccb"),
    "occupation": ("occupation", "what do you do", "\u092a\u0947\u0936\u093e", "\u0935\u094d\u092f\u0935\u0938\u093e\u092f"),
    "household_income": (
        "income",
        "household income",
        "\u092e\u093e\u0938\u093f\u0915 \u0906\u092f",
        "\u0909\u0924\u094d\u092a\u0928\u094d\u0928",
        "\u0c86\u0ca6\u0cbe\u0caf",
        "\u20b910,000",
    ),
    "social_category": ("social category", "\u0938\u093e\u092e\u093e\u091c\u093f\u0915", "obc", "minority"),
    "marital_status": ("marital", "married", "\u0935\u0948\u0935\u093e\u0939\u093f\u0915", "\u0cb5\u0cc8\u0cb5\u0cbe\u0cb9\u0cbf\u0c95"),
    "disability": ("disability", "disabled", "\u0935\u093f\u0915\u0932\u093e\u0902\u0917", "\u0905\u092a\u0902\u0917\u0924\u094d\u0935", "\u0c85\u0c82\u0c97\u0cb5\u0cc8"),
    "household_size": ("household size", "how many people", "\u0915\u093f\u0924\u0940 \u0932\u094b\u0915", "\u0c8e\u0cb7\u0ccd\u0c9f\u0cc1 \u0c9c\u0ca8"),
    "children_under_18": ("children", "under 18", "\u092e\u0941\u0932\u0947", "\u092c\u091a\u094d\u091a\u0947", "\u0cae\u0c95\u0ccd\u0c95\u0cb3"),
    "members_60_plus": ("aged 60", "60+", "members 60", "\u0935\u0930\u094d\u0937\u0947 \u0915\u093f\u0902\u0935\u093e", "\u0cb5\u0cb0\u0ccd\u0cb7"),
    "family_disability": (
        "family member with disability",
        "anyone in the household have a disability",
        "\u0905\u092a\u0902\u0917\u0924\u094d\u0935",
        "\u0935\u093f\u0915\u0932\u093e\u0902\u0917",
    ),
    "pregnant_or_breastfeeding": ("pregnant", "breastfeed", "\u0917\u0930\u094d\u092d\u0935\u0924\u0940", "\u0938\u094d\u0924\u0928\u092a\u093e\u0928", "\u0c97\u0cb0\u0ccd\u0cad\u0cbf\u0ca3\u0cbf"),
    "primary_occupation": ("primary occupation", "household occupation", "\u092a\u0947\u0936\u093e", "\u0935\u094d\u092f\u0935\u0938\u093e\u092f"),
    "housing": ("housing", "pucca", "kutcha", "rented", "\u0906\u0935\u093e\u0938"),
    "ration_card": ("ration", "\u0930\u093e\u0936\u0928", "\u0936\u093f\u0927\u093e", "\u0cb0\u0cc7\u0cb7\u0ca8\u0ccd"),
    "has_insurance": ("insurance", "\u092c\u0940\u092e\u093e", "\u0935\u093f\u092e\u093e", "\u0cb5\u0cbf\u0cae\u0cc6"),
}

_SLOT_PROMPTS: dict[str, dict[str, str]] = {
    "state": {
        "English": "Which state do you currently live in?",
        "Hindi": "\u0915\u0943\u092a\u092f\u093e \u0905\u092a\u0928\u0947 \u0930\u093e\u091c\u094d\u092f \u0915\u093e \u0928\u093e\u092e \u092c\u0924\u093e\u090f\u0902\u0964",
        "Marathi": "\u0915\u0943\u092a\u092f\u093e \u0924\u0941\u092e\u091a\u094d\u092f\u093e \u0930\u093e\u091c\u094d\u092f\u093e\u091a\u0947 \u0928\u093e\u0935 \u0938\u093e\u0902\u0917\u093e\u0964",
        "Kannada": "\u0ca6\u0caf\u0cb5\u0cbf\u0c9f\u0ccd\u0c9f\u0cc1 \u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0cb0\u0cbe\u0c9c\u0ccd\u0caf\u0ca6 \u0cb9\u0cc6\u0cb8\u0cb0\u0cc1 \u0cb9\u0cc7\u0cb3\u0cbf.",
    },
    "age_group": {
        "English": "Which age group are you in?",
        "Hindi": "\u0906\u092a \u0915\u093f\u0938 \u0906\u092f\u0941 \u0935\u0930\u094d\u0917 \u092e\u0947\u0902 \u0939\u0948\u0902?",
        "Marathi": "\u0924\u0941\u092e\u094d\u0939\u0940 \u0915\u094b\u0923\u0924\u094d\u092f\u093e \u0935\u092f\u094b\u0917\u091f\u093e\u0924 \u0906\u0939\u093e\u0924?",
        "Kannada": "\u0ca8\u0c80\u0cb5\u0cc1 \u0caf\u0cbe\u0cb5 \u0cb5\u0caf\u0ccb\u0cae\u0cbf\u0ca4\u0cbf\u0caf\u0cb2\u0ccd\u0cb2\u0cbf\u0ca6\u0ccd\u0ca6\u0cc0\u0cb0\u0cbf?",
    },
    "occupation": {
        "English": "What best describes your current occupation?",
        "Hindi": "\u0906\u092a\u0915\u093e \u0935\u0930\u094d\u0924\u092e\u093e\u0928 \u092a\u0947\u0936\u093e \u0915\u094d\u092f\u093e \u0939\u0948?",
        "Marathi": "\u0924\u0941\u092e\u091a\u093e \u0938\u0927\u094d\u092f\u093e\u091a\u093e \u0935\u094d\u092f\u0935\u0938\u093e\u092f \u0915\u093e\u092f \u0906\u0939\u0947?",
        "Kannada": "\u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0caa\u0ccd\u0cb0\u0cb8\u0ccd\u0ca4\u0cc1\u0ca4 \u0c89\u0ca6\u0ccd\u0caf\u0ccb\u0c97 \u0caf\u0cbe\u0cb5\u0cc1\u0ca6\u0cc1?",
    },
    "household_income": {
        "English": "Which range best describes your total monthly household income?",
        "Hindi": "\u0906\u092a\u0915\u0947 \u092a\u0930\u093f\u0935\u093e\u0930 \u0915\u0940 \u0915\u0941\u0932 \u092e\u093e\u0938\u093f\u0915 \u0906\u092f \u0915\u093f\u0938 \u0936\u094d\u0930\u0947\u0923\u0940 \u092e\u0947\u0902 \u0939\u0948?",
        "Marathi": "\u0924\u0941\u092e\u091a\u0947 \u090f\u0915\u0942\u0923 \u092e\u093e\u0938\u093f\u0915 \u0915\u094c\u091f\u0941\u0902\u092c\u093f\u0915 \u0909\u0924\u094d\u092a\u0928\u094d\u0928 \u0915\u094b\u0923\u0924\u094d\u092f\u093e \u0936\u094d\u0930\u0947\u0923\u0940\u0924 \u0906\u0939\u0947?",
        "Kannada": "\u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0c92\u0c9f\u0ccd\u0c9f\u0cc1 \u0cae\u0cbe\u0cb8\u0cbf\u0c95 \u0c86\u0ca6\u0cbe\u0caf \u0caf\u0cbe\u0cb5 \u0cb5\u0ccd\u0caf\u0cbe\u0caa\u0ccd\u0ca4\u0cbf\u0caf\u0cb2\u0ccd\u0cb2\u0cbf\u0ca6\u0cc6?",
    },
    "social_category": {
        "English": "Which social category would you like to select?",
        "Hindi": "\u0906\u092a \u0915\u094c\u0928 \u0938\u0940 \u0938\u093e\u092e\u093e\u091c\u093f\u0915 \u0936\u094d\u0930\u0947\u0923\u0940 \u091a\u0941\u0928\u0928\u093e \u091a\u093e\u0939\u0947\u0902\u0917\u0947?",
        "Marathi": "\u0924\u0941\u092e\u094d\u0939\u0940 \u0915\u094b\u0923\u0924\u0940 \u0938\u093e\u092e\u093e\u091c\u093f\u0915 \u0936\u094d\u0930\u0947\u0923\u0940 \u0928\u093f\u0935\u0921\u093e\u0932?",
        "Kannada": "\u0ca8\u0c80\u0cb5\u0cc1 \u0caf\u0cbe\u0cb5 \u0cb8\u0cbe\u0cae\u0cbe\u0c9c\u0cbf\u0c95 \u0cb5\u0cb0\u0ccd\u0c97\u0cb5\u0ca8\u0ccd\u0ca8\u0cc1 \u0c86\u0caf\u0ccd\u0c95\u0cc6 \u0cae\u0cbe\u0ca1\u0cb2\u0cbf\u0c9a\u0ccd\u0c9b\u0cbf\u0cb8\u0cc1\u0ca4\u0ccd\u0ca4\u0cc0\u0cb0\u0cbf?",
    },
    "marital_status": {
        "English": "What is your marital status?",
        "Hindi": "\u0906\u092a\u0915\u0940 \u0935\u0948\u0935\u093e\u0939\u093f\u0915 \u0938\u094d\u0925\u093f\u0924\u093f \u0915\u094d\u092f\u093e \u0939\u0948?",
        "Marathi": "\u0924\u0941\u092e\u091a\u0940 \u0935\u0948\u0935\u093e\u0939\u093f\u0915 \u0938\u094d\u0925\u093f\u0924\u0940 \u0915\u093e\u092f \u0906\u0939\u0947?",
        "Kannada": "\u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0cb5\u0cc8\u0cb5\u0cbe\u0cb9\u0cbf\u0c95 \u0cb8\u0ccd\u0ca5\u0cbf\u0ca4\u0cbf \u0c8f\u0ca8\u0cc1?",
    },
    "disability": {
        "English": "Do you have a disability?",
        "Hindi": "\u0915\u094d\u092f\u093e \u0906\u092a\u0915\u094b \u0915\u094b\u0908 \u0935\u093f\u0915\u0932\u093e\u0902\u0917\u0924\u093e \u0939\u0948?",
        "Marathi": "\u0924\u0941\u092e\u094d\u0939\u093e\u0932\u093e \u0905\u092a\u0902\u0917\u0924\u094d\u0935 \u0906\u0939\u0947 \u0915\u093e?",
        "Kannada": "\u0ca8\u0cbf\u0cae\u0c97\u0cc6 \u0caf\u0cbe\u0cb5\u0cc1\u0ca6\u0cbe\u0ca6\u0cb0\u0cc2 \u0c85\u0c82\u0c97\u0cb5\u0cc8\u0c95\u0cb2\u0ccd\u0caf\u0cb5\u0cbf\u0ca6\u0cc6\u0caf\u0cc7?",
    },
    "household_size": {
        "English": "How many people live in your household, including you?",
        "Hindi": "\u0906\u092a\u0915\u0947 \u0918\u0930 \u092e\u0947\u0902 \u0906\u092a \u0938\u0939\u093f\u0924 \u0915\u093f\u0924\u0928\u0947 \u0932\u094b\u0917 \u0930\u0939\u0924\u0947 \u0939\u0948\u0902?",
        "Marathi": "\u0924\u0941\u092e\u091a\u094d\u092f\u093e \u0918\u0930\u093e\u0924 \u0924\u0941\u092e\u094d\u0939\u093e\u0902\u0938\u0939 \u0915\u093f\u0924\u0940 \u0932\u094b\u0915 \u0930\u093e\u0939\u0924\u093e\u0924?",
        "Kannada": "\u0ca8\u0cbf\u0cae\u0ccd\u0cae\u0ca8\u0ccd\u0ca8\u0cc2 \u0cb8\u0cc7\u0cb0\u0cbf\u0cb8\u0cbf \u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0cae\u0ca8\u0cc6\u0caf\u0cb2\u0ccd\u0cb2\u0cbf \u0c8e\u0cb7\u0ccd\u0c9f\u0cc1 \u0c9c\u0ca8\u0cb0\u0cc1 \u0cb5\u0cbe\u0cb8\u0cbf\u0cb8\u0cc1\u0ca4\u0ccd\u0ca4\u0cbe\u0cb0\u0cc6?",
    },
    "children_under_18": {
        "English": "How many children under 18 are in the household? (0 is fine)",
        "Hindi": "\u0918\u0930 \u092e\u0947\u0902 18 \u0935\u0930\u094d\u0937 \u0938\u0947 \u0915\u092e \u0906\u092f\u0941 \u0915\u0947 \u0915\u093f\u0924\u0928\u0947 \u092c\u091a\u094d\u091a\u0947 \u0939\u0948\u0902? (0 \u0920\u0940\u0915 \u0939\u0948)",
        "Marathi": "\u0915\u0941\u091f\u0941\u0902\u092c\u093e\u0924 18 \u0935\u0930\u094d\u0937\u093e\u0902\u0916\u093e\u0932\u0940\u0932 \u0915\u093f\u0924\u0940 \u092e\u0941\u0932\u0947 \u0906\u0939\u0947\u0924? (0 \u091a\u093e\u0932\u0947\u0932)",
        "Kannada": "\u0cae\u0ca8\u0cc6\u0caf\u0cb2\u0ccd\u0cb2\u0cbf 18 \u0cb5\u0cb0\u0ccd\u0cb7\u0c95\u0ccd\u0c95\u0cbf\u0c82\u0ca4 \u0c95\u0ca1\u0cbf\u0cae\u0cc6 \u0cb5\u0caf\u0cb8\u0ccd\u0cb8\u0cbf\u0ca8 \u0c8e\u0cb7\u0ccd\u0c9f\u0cc1 \u0cae\u0c95\u0ccd\u0c95\u0cb3\u0cbf\u0ca6\u0ccd\u0ca6\u0cbe\u0cb0\u0cc6? (0 \u0cb8\u0cb0\u0cbf)",
    },
    "members_60_plus": {
        "English": "How many household members are aged 60 or above? (0 is fine)",
        "Hindi": "\u0918\u0930 \u092e\u0947\u0902 60 \u0935\u0930\u094d\u0937 \u092f\u093e \u0909\u0938\u0938\u0947 \u0905\u0927\u093f\u0915 \u0906\u092f\u0941 \u0915\u0947 \u0915\u093f\u0924\u0928\u0947 \u0938\u0926\u0938\u094d\u092f \u0939\u0948\u0902? (0 \u0920\u0940\u0915 \u0939\u0948)",
        "Marathi": "\u0918\u0930\u093e\u0924 60 \u0935\u0930\u094d\u0937\u0947 \u0915\u093f\u0902\u0935\u093e \u0924\u094d\u092f\u093e\u0939\u0942\u0928 \u0905\u0927\u093f\u0915 \u0935\u092f\u093e\u091a\u0947 \u0915\u093f\u0924\u0940 \u0938\u0926\u0938\u094d\u092f \u0906\u0939\u0947\u0924? (0 \u091a\u093e\u0932\u0947\u0932)",
        "Kannada": "\u0cae\u0ca8\u0cc6\u0caf\u0cb2\u0ccd\u0cb2\u0cbf 60 \u0cb5\u0cb0\u0ccd\u0cb7 \u0c85\u0ca5\u0cb5\u0cbe \u0cb9\u0cc6\u0c9a\u0ccd\u0c9a\u0cbf\u0ca8 \u0cb5\u0caf\u0cb8\u0ccd\u0cb8\u0cbf\u0ca8 \u0c8e\u0cb7\u0ccd\u0c9f\u0cc1 \u0cb8\u0ca6\u0cb8\u0ccd\u0caf\u0cb0\u0cbf\u0ca6\u0ccd\u0ca6\u0cbe\u0cb0\u0cc6? (0 \u0cb8\u0cb0\u0cbf)",
    },
    "family_disability": {
        "English": "Does anyone in the household have a disability?",
        "Hindi": "\u0915\u094d\u092f\u093e \u0918\u0930 \u092e\u0947\u0902 \u0915\u093f\u0938\u0940 \u0915\u094b \u0935\u093f\u0915\u0932\u093e\u0902\u0917\u0924\u093e \u0939\u0948?",
        "Marathi": "\u0918\u0930\u093e\u0924\u0940\u0932 \u0915\u094b\u0923\u093e\u0932\u093e \u0905\u092a\u0902\u0917\u0924\u094d\u0935 \u0906\u0939\u0947 \u0915\u093e?",
        "Kannada": "\u0cae\u0ca8\u0cc6\u0caf\u0cb2\u0ccd\u0cb2\u0cbf \u0caf\u0cbe\u0cb0\u0cbf\u0c97\u0cbe\u0ca6\u0cb0\u0cc2 \u0c85\u0c82\u0c97\u0cb5\u0cc8\u0c95\u0cb2\u0ccd\u0caf\u0cb5\u0cbf\u0ca6\u0cc6\u0caf\u0cc7?",
    },
    "pregnant_or_breastfeeding": {
        "English": "Is anyone in the household pregnant or breastfeeding?",
        "Hindi": "\u0915\u094d\u092f\u093e \u0918\u0930 \u092e\u0947\u0902 \u0915\u094b\u0908 \u0917\u0930\u094d\u092d\u0935\u0924\u0940 \u0939\u0948 \u092f\u093e \u0938\u094d\u0924\u0928\u092a\u093e\u0928 \u0915\u0930\u093e \u0930\u0939\u0940 \u0939\u0948?",
        "Marathi": "\u0918\u0930\u093e\u0924\u0940\u0932 \u0915\u094b\u0923\u0940 \u0917\u0930\u094d\u092d\u0935\u0924\u0940 \u0915\u093f\u0902\u0935\u093e \u0938\u094d\u0924\u0928\u092a\u093e\u0928 \u0915\u0930\u0923\u093e\u0930\u0940 \u0906\u0939\u0947 \u0915\u093e?",
        "Kannada": "\u0cae\u0ca8\u0cc6\u0caf\u0cb2\u0ccd\u0cb2\u0cbf \u0caf\u0cbe\u0cb0\u0cbe\u0ca6\u0cb0\u0cc2 \u0c97\u0cb0\u0ccd\u0cad\u0cbf\u0ca3\u0cbf\u0caf\u0cbe\u0c97\u0cbf\u0ca6\u0ccd\u0ca6\u0cbe\u0cb0\u0cc6\u0caf\u0cc7 \u0c85\u0ca5\u0cb5\u0cbe \u0cb8\u0ccd\u0ca4\u0ca8\u0ccd\u0caf\u0caa\u0cbe\u0ca8 \u0cae\u0cbe\u0ca1\u0cc1\u0ca4\u0ccd\u0ca4\u0cbf\u0ca6\u0ccd\u0ca6\u0cbe\u0cb0\u0cc6\u0caf\u0cc7?",
    },
    "primary_occupation": {
        "English": "What is the primary occupation of the household?",
        "Hindi": "\u092a\u0930\u093f\u0935\u093e\u0930 \u0915\u093e \u092e\u0941\u0916\u094d\u092f \u092a\u0947\u0936\u093e \u0915\u094d\u092f\u093e \u0939\u0948?",
        "Marathi": "\u0915\u0941\u091f\u0941\u0902\u092c\u093e\u091a\u093e \u092e\u0941\u0916\u094d\u092f \u0935\u094d\u092f\u0935\u0938\u093e\u092f \u0915\u093e\u092f \u0906\u0939\u0947?",
        "Kannada": "\u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0cae\u0cc1\u0c96\u0ccd\u0caf \u0c89\u0ca6\u0ccd\u0caf\u0ccb\u0c97 \u0caf\u0cbe\u0cb5\u0cc1\u0ca6\u0cc1?",
    },
    "housing": {
        "English": "What best describes your family's housing?",
        "Hindi": "\u0906\u092a\u0915\u0947 \u092a\u0930\u093f\u0935\u093e\u0930 \u0915\u093e \u0906\u0935\u093e\u0938 \u0915\u0948\u0938\u093e \u0939\u0948?",
        "Marathi": "\u0924\u0941\u092e\u091a\u094d\u092f\u093e \u0915\u0941\u091f\u0941\u0902\u092c\u093e\u091a\u0947 \u0918\u0930 \u0915\u0938\u0947 \u0906\u0939\u0947?",
        "Kannada": "\u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0cb5\u0cb8\u0ca4\u0cbf \u0cb9\u0cc7\u0c97\u0cbf\u0ca6\u0cc6?",
    },
    "ration_card": {
        "English": "What type of ration card does the household have?",
        "Hindi": "\u092a\u0930\u093f\u0935\u093e\u0930 \u0915\u0947 \u092a\u093e\u0938 \u0915\u093f\u0938 \u092a\u094d\u0930\u0915\u093e\u0930 \u0915\u093e \u0930\u093e\u0936\u0928 \u0915\u093e\u0930\u094d\u0921 \u0939\u0948?",
        "Marathi": "\u0915\u0941\u091f\u0941\u0902\u092c\u093e\u0915\u0921\u0947 \u0915\u094b\u0923\u0924\u094d\u092f\u093e \u092a\u094d\u0930\u0915\u093e\u0930\u091a\u0940 \u0936\u093f\u0927\u093e\u092a\u0924\u094d\u0930\u093f\u0915\u093e \u0906\u0939\u0947?",
        "Kannada": "\u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0cac\u0cb3\u0cbf \u0caf\u0cbe\u0cb5 \u0cb0\u0cc0\u0ca4\u0cbf\u0caf \u0cb0\u0cc7\u0cb7\u0ca8\u0ccd \u0c95\u0cbe\u0cb0\u0ccd\u0ca1\u0ccd \u0c87\u0ca6\u0cc6?",
    },
    "has_insurance": {
        "English": "Does the household have health insurance?",
        "Hindi": "\u0915\u094d\u092f\u093e \u092a\u0930\u093f\u0935\u093e\u0930 \u0915\u0947 \u092a\u093e\u0938 \u0938\u094d\u0935\u093e\u0938\u094d\u0925\u094d\u092f \u092c\u0940\u092e\u093e \u0939\u0948?",
        "Marathi": "\u0915\u0941\u091f\u0941\u0902\u092c\u093e\u0915\u0921\u0947 \u0906\u0930\u094b\u0917\u094d\u092f \u0935\u093f\u092e\u093e \u0906\u0939\u0947 \u0915\u093e?",
        "Kannada": "\u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0cac\u0cb3\u0cbf \u0c86\u0cb0\u0ccb\u0c97\u0ccd\u0caf \u0cb5\u0cbf\u0cae\u0cc6 \u0c87\u0ca6\u0cc6\u0caf\u0cc7?",
    },
}

_LABELS: dict[str, dict[str, str]] = {
    "state": {"English": "State", "Hindi": "\u0930\u093e\u091c\u094d\u092f", "Marathi": "\u0930\u093e\u091c\u094d\u092f", "Kannada": "\u0cb0\u0cbe\u0c9c\u0ccd\u0caf"},
    "age_group": {"English": "Age group", "Hindi": "\u0906\u092f\u0941 \u0935\u0930\u094d\u0917", "Marathi": "\u0935\u092f\u094b\u0917\u091f", "Kannada": "\u0cb5\u0caf\u0ccb\u0cae\u0cbf\u0ca4\u0cbf"},
    "occupation": {"English": "Occupation", "Hindi": "\u092a\u0947\u0936\u093e", "Marathi": "\u0935\u094d\u092f\u0935\u0938\u093e\u092f", "Kannada": "\u0c89\u0ca6\u0ccd\u0caf\u0ccb\u0c97"},
    "household_income": {"English": "Household income", "Hindi": "\u092a\u093e\u0930\u093f\u0935\u093e\u0930\u093f\u0915 \u0906\u092f", "Marathi": "\u0915\u094c\u091f\u0941\u0902\u092c\u093f\u0915 \u0909\u0924\u094d\u092a\u0928\u094d\u0928", "Kannada": "\u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0c86\u0ca6\u0cbe\u0caf"},
    "social_category": {"English": "Social category", "Hindi": "\u0938\u093e\u092e\u093e\u091c\u093f\u0915 \u0936\u094d\u0930\u0947\u0923\u0940", "Marathi": "\u0938\u093e\u092e\u093e\u091c\u093f\u0915 \u0936\u094d\u0930\u0947\u0923\u0940", "Kannada": "\u0cb8\u0cbe\u0cae\u0cbe\u0c9c\u0cbf\u0c95 \u0cb5\u0cb0\u0ccd\u0c97"},
    "marital_status": {"English": "Marital status", "Hindi": "\u0935\u0948\u0935\u093e\u0939\u093f\u0915 \u0938\u094d\u0925\u093f\u0924\u093f", "Marathi": "\u0935\u0948\u0935\u093e\u0939\u093f\u0915 \u0938\u094d\u0925\u093f\u0924\u0940", "Kannada": "\u0cb5\u0cc8\u0cb5\u0cbe\u0cb9\u0cbf\u0c95 \u0cb8\u0ccd\u0ca5\u0cbf\u0ca4\u0cbf"},
    "disability": {"English": "Disability", "Hindi": "\u0935\u093f\u0915\u0932\u093e\u0902\u0917\u0924\u093e", "Marathi": "\u0905\u092a\u0902\u0917\u0924\u094d\u0935", "Kannada": "\u0c85\u0c82\u0c97\u0cb5\u0cc8\u0c95\u0cb2\u0ccd\u0caf"},
    "household_size": {"English": "Household size", "Hindi": "\u092a\u0930\u093f\u0935\u093e\u0930 \u0915\u093e \u0906\u0915\u093e\u0930", "Marathi": "\u0915\u0941\u091f\u0941\u0902\u092c \u0906\u0915\u093e\u0930", "Kannada": "\u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0c97\u0cbe\u0ca4\u0ccd\u0cb0"},
    "children_under_18": {"English": "Children under 18", "Hindi": "18 \u0935\u0930\u094d\u0937 \u0938\u0947 \u0915\u092e \u092c\u091a\u094d\u091a\u0947", "Marathi": "18 \u0935\u0930\u094d\u0937\u093e\u0902\u0916\u093e\u0932\u0940\u0932 \u092e\u0941\u0932\u0947", "Kannada": "18\u0c95\u0ccd\u0c95\u0cbf\u0c82\u0ca4 \u0c95\u0ca1\u0cbf\u0cae\u0cc6 \u0cae\u0c95\u0ccd\u0c95\u0cb3\u0cc1"},
    "members_60_plus": {"English": "Members aged 60+", "Hindi": "60+ \u0935\u0930\u094d\u0937 \u0915\u0947 \u0938\u0926\u0938\u094d\u092f", "Marathi": "60+ \u0935\u092f\u093e\u091a\u0947 \u0938\u0926\u0938\u094d\u092f", "Kannada": "60+ \u0cb5\u0cb0\u0ccd\u0cb7\u0ca6 \u0cb8\u0ca6\u0cb8\u0ccd\u0caf\u0cb0\u0cc1"},
    "family_disability": {"English": "Family member with disability", "Hindi": "\u0935\u093f\u0915\u0932\u093e\u0902\u0917\u0924\u093e \u0935\u093e\u0932\u093e \u0938\u0926\u0938\u094d\u092f", "Marathi": "\u0905\u092a\u0902\u0917\u0924\u094d\u0935 \u0905\u0938\u0932\u0947\u0932\u093e \u0938\u0926\u0938\u094d\u092f", "Kannada": "\u0c85\u0c82\u0c97\u0cb5\u0cc8\u0c95\u0cb2\u0ccd\u0caf\u0cb5\u0cbf\u0cb0\u0cc1\u0cb5 \u0cb8\u0ca6\u0cb8\u0ccd\u0caf"},
    "pregnant_or_breastfeeding": {"English": "Pregnant or breastfeeding", "Hindi": "\u0917\u0930\u094d\u092d\u0935\u0924\u0940 \u092f\u093e \u0938\u094d\u0924\u0928\u092a\u093e\u0928", "Marathi": "\u0917\u0930\u094d\u092d\u0935\u0924\u0940 \u0915\u093f\u0902\u0935\u093e \u0938\u094d\u0924\u0928\u092a\u093e\u0928", "Kannada": "\u0c97\u0cb0\u0ccd\u0cad\u0cbf\u0ca3\u0cbf \u0c85\u0ca5\u0cb5\u0cbe \u0cb8\u0ccd\u0ca4\u0ca8\u0ccd\u0caf\u0caa\u0cbe\u0ca8"},
    "primary_occupation": {"English": "Primary occupation", "Hindi": "\u092e\u0941\u0916\u094d\u092f \u092a\u0947\u0936\u093e", "Marathi": "\u092e\u0941\u0916\u094d\u092f \u0935\u094d\u092f\u0935\u0938\u093e\u092f", "Kannada": "\u0cae\u0cc1\u0c96\u0ccd\u0caf \u0c89\u0ca6\u0ccd\u0caf\u0ccb\u0c97"},
    "housing": {"English": "Housing", "Hindi": "\u0906\u0935\u093e\u0938", "Marathi": "\u0918\u0930", "Kannada": "\u0cb5\u0cb8\u0ca4\u0cbf"},
    "ration_card": {"English": "Ration card", "Hindi": "\u0930\u093e\u0936\u0928 \u0915\u093e\u0930\u094d\u0921", "Marathi": "\u0936\u093f\u0927\u093e\u092a\u0924\u094d\u0930\u093f\u0915\u093e", "Kannada": "\u0cb0\u0cc7\u0cb7\u0ca8\u0ccd \u0c95\u0cbe\u0cb0\u0ccd\u0ca1\u0ccd"},
    "has_insurance": {"English": "Health insurance", "Hindi": "\u0938\u094d\u0935\u093e\u0938\u094d\u0925\u094d\u092f \u092c\u0940\u092e\u093e", "Marathi": "\u0906\u0930\u094b\u0917\u094d\u092f \u0935\u093f\u092e\u093e", "Kannada": "\u0c86\u0cb0\u0ccb\u0c97\u0ccd\u0caf \u0cb5\u0cbf\u0cae\u0cc6"},
}

_STRINGS: dict[str, dict[str, str]] = {
    "reply_own_words": {
        "English": "(You can reply in your own words.)",
        "Hindi": "(\u0906\u092a \u0905\u092a\u0928\u0947 \u0936\u092c\u094d\u0926\u094b\u0902 \u092e\u0947\u0902 \u091c\u0935\u093e\u092c \u0926\u0947 \u0938\u0915\u0924\u0947 \u0939\u0948\u0902\u0964)",
        "Marathi": "(\u0924\u0941\u092e\u094d\u0939\u0940 \u0924\u0941\u092e\u091a\u094d\u092f\u093e \u0936\u092c\u094d\u0926\u093e\u0902\u0924 \u0909\u0924\u094d\u0924\u0930 \u0926\u0947\u090a \u0936\u0915\u0924\u093e.)",
        "Kannada": "(\u0ca8\u0cbf\u0cae\u0ccd\u0cae\u0ca6\u0cc7 \u0cae\u0cbe\u0ca4\u0cc1\u0c97\u0cb3\u0cb2\u0ccd\u0cb2\u0cbf \u0c89\u0ca4\u0ccd\u0ca4\u0cb0\u0cbf\u0cb8\u0cac\u0cb9\u0cc1\u0ca6\u0cc1.)",
    },
    "reply_examples": {
        "English": "(You can reply in your own words. Examples: {examples}\u2026)",
        "Hindi": "(\u0906\u092a \u0905\u092a\u0928\u0947 \u0936\u092c\u094d\u0926\u094b\u0902 \u092e\u0947\u0902 \u091c\u0935\u093e\u092c \u0926\u0947 \u0938\u0915\u0924\u0947 \u0939\u0948\u0902\u0964 \u0909\u0926\u093e\u0939\u0930\u0923: {examples}\u2026)",
        "Marathi": "(\u0924\u0941\u092e\u094d\u0939\u0940 \u0924\u0941\u092e\u091a\u094d\u092f\u093e \u0936\u092c\u094d\u0926\u093e\u0902\u0924 \u0909\u0924\u094d\u0924\u0930 \u0926\u0947\u090a \u0936\u0915\u0924\u093e. \u0909\u0926\u093e\u0939\u0930\u0923\u0947: {examples}\u2026)",
        "Kannada": "(\u0ca8\u0cbf\u0cae\u0ccd\u0cae\u0ca6\u0cc7 \u0cae\u0cbe\u0ca4\u0cc1\u0c97\u0cb3\u0cb2\u0ccd\u0cb2\u0cbf \u0c89\u0ca4\u0ccd\u0ca4\u0cb0\u0cbf\u0cb8\u0cac\u0cb9\u0cc1\u0ca6\u0cc1. \u0c89\u0ca6\u0cbe\u0cb9\u0cb0\u0ca3\u0cc6: {examples}\u2026)",
    },
    "language_switch_ack": {
        "English": "Sure, let's continue in English.",
        "Hindi": "\u0920\u0940\u0915 \u0939\u0948, \u0905\u092c \u0939\u092e \u0939\u093f\u0902\u0926\u0940 \u092e\u0947\u0902 \u092c\u093e\u0924 \u0915\u0930\u0947\u0902\u0917\u0947\u0964",
        "Marathi": "\u0920\u0940\u0915 \u0906\u0939\u0947, \u0906\u0924\u093e \u0906\u092a\u0923 \u092e\u0930\u093e\u0920\u0940\u0924 \u092c\u094b\u0932\u0942\u092f\u093e.",
        "Kannada": "\u0cb8\u0cb0\u0cbf, \u0c87\u0ca8\u0ccd\u0ca8\u0cc1 \u0cae\u0cc1\u0c82\u0ca6\u0cc6 \u0c95\u0ca8\u0ccd\u0ca8\u0ca1\u0ca6\u0cb2\u0ccd\u0cb2\u0cbf \u0cae\u0cc1\u0c82\u0ca6\u0cc1\u0cb5\u0cb0\u0cbf\u0cb8\u0ccb\u0ca3.",
    },
    "profile_header": {
        "English": "Here's what I have so far:",
        "Hindi": "\u0905\u092d\u0940 \u0924\u0915 \u092e\u0947\u0930\u0947 \u092a\u093e\u0938 \u092f\u0939 \u091c\u093e\u0928\u0915\u093e\u0930\u0940 \u0939\u0948:",
        "Marathi": "\u0906\u0924\u094d\u0924\u093e\u092a\u0930\u094d\u092f\u0902\u0924 \u092e\u093e\u091d\u094d\u092f\u093e\u0915\u0921\u0947 \u0939\u0940 \u092e\u093e\u0939\u093f\u0924\u0940 \u0906\u0939\u0947:",
        "Kannada": "\u0c87\u0cb2\u0ccd\u0cb2\u0cbf\u0caf\u0cb5\u0cb0\u0cc6\u0c97\u0cc6 \u0ca8\u0ca8\u0ccd\u0ca8 \u0cac\u0cb3\u0cbf \u0c87\u0cb0\u0cc1\u0cb5 \u0cae\u0cbe\u0cb9\u0cbf\u0ca4\u0cbf:",
    },
    "profile_confirm": {
        "English": "Does this look right? Reply *Proceed* or *Edit details*.",
        "Hindi": "\u0915\u094d\u092f\u093e \u092f\u0939 \u0938\u0939\u0940 \u0939\u0948? *Proceed* \u092f\u093e *Edit details* \u0932\u093f\u0916\u0947\u0902\u0964",
        "Marathi": "\u0939\u0947 \u092c\u0930\u094b\u092c\u0930 \u0906\u0939\u0947 \u0915\u093e? *Proceed* \u0915\u093f\u0902\u0935\u093e *Edit details* \u0932\u093f\u0939\u093e.",
        "Kannada": "\u0c87\u0ca6\u0cc1 \u0cb8\u0cb0\u0cbf\u0caf\u0cbe\u0c97\u0cbf\u0ca6\u0cc6\u0caf\u0cc7? *Proceed* \u0c85\u0ca5\u0cb5\u0cbe *Edit details* \u0c8e\u0c82\u0ca6\u0cc1 \u0cac\u0cb0\u0cc6\u0caf\u0cbf\u0cb0\u0cbf.",
    },
    "didnt_catch": {
        "English": "I didn't catch that clearly.",
        "Hindi": "\u092e\u0941\u091d\u0947 \u0935\u0939 \u0938\u093e\u092b\u093c \u0938\u092e\u091d \u0928\u0939\u0940\u0902 \u0906\u092f\u093e\u0964",
        "Marathi": "\u092e\u0932\u093e \u0924\u0947 \u0938\u094d\u092a\u0937\u094d\u091f\u092a\u0923\u0947 \u0938\u092e\u091c\u0932\u0947 \u0928\u093e\u0939\u0940.",
        "Kannada": "\u0ca8\u0ca8\u0c97\u0cc6 \u0c85\u0ca6\u0cc1 \u0cb8\u0ccd\u0caa\u0cb7\u0ccd\u0c9f\u0cb5\u0cbe\u0c97\u0cbf \u0c85\u0cb0\u0ccd\u0ca5\u0cb5\u0cbe\u0c97\u0cb2\u0cbf\u0cb2\u0ccd\u0cb2.",
    },
    "got_it": {
        "English": "Got it \u2014 {bits}.",
        "Hindi": "\u0938\u092e\u091d \u0917\u092f\u093e \u2014 {bits}.",
        "Marathi": "\u0938\u092e\u091c\u0932\u0947 \u2014 {bits}.",
        "Kannada": "\u0cb8\u0cb0\u0cbf \u2014 {bits}.",
    },
    "got_it_short": {
        "English": "Got it.",
        "Hindi": "\u0938\u092e\u091d \u0917\u092f\u093e\u0964",
        "Marathi": "\u0938\u092e\u091c\u0932\u0947.",
        "Kannada": "\u0cb8\u0cb0\u0cbf.",
    },
    "main_menu": {
        "English": "What would you like to explore today?\n\u2022 Individual Schemes\n\u2022 Family Schemes\n\u2022 I need help\n\nJust type your choice in your own words.",
        "Hindi": "\u0906\u091c \u0906\u092a \u0915\u094d\u092f\u093e \u0926\u0947\u0916\u0928\u093e \u091a\u093e\u0939\u0947\u0902\u0917\u0947?\n\u2022 Individual Schemes\n\u2022 Family Schemes\n\u2022 I need help\n\n\u0905\u092a\u0928\u0947 \u0936\u092c\u094d\u0926\u094b\u0902 \u092e\u0947\u0902 \u0932\u093f\u0916\u0947\u0902\u0964",
        "Marathi": "\u0906\u091c \u0924\u0941\u092e\u094d\u0939\u093e\u0932\u093e \u0915\u093e\u092f \u092a\u093e\u0939\u093e\u092f\u091a\u0947 \u0906\u0939\u0947?\n\u2022 Individual Schemes\n\u2022 Family Schemes\n\u2022 I need help\n\n\u0924\u0941\u092e\u091a\u094d\u092f\u093e \u0936\u092c\u094d\u0926\u093e\u0902\u0924 \u0932\u093f\u0939\u093e.",
        "Kannada": "\u0c87\u0c82\u0ca6\u0cc1 \u0ca8\u0c80\u0cb5\u0cc1 \u0c8f\u0ca8\u0ca8\u0ccd\u0ca8\u0cc1 \u0ca8\u0ccb\u0ca1\u0cb2\u0cc1 \u0cac\u0caf\u0cb8\u0cc1\u0ca4\u0ccd\u0ca4\u0cc0\u0cb0\u0cbf?\n\u2022 Individual Schemes\n\u2022 Family Schemes\n\u2022 I need help\n\n\u0ca8\u0cbf\u0cae\u0ccd\u0cae\u0ca6\u0cc7 \u0cae\u0cbe\u0ca4\u0cc1\u0c97\u0cb3\u0cb2\u0ccd\u0cb2\u0cbf \u0cac\u0cb0\u0cc6\u0caf\u0cbf\u0cb0\u0cbf.",
    },
    "menu_unclear": {
        "English": "Please choose Individual Schemes, Family Schemes, or I need help.",
        "Hindi": "\u0915\u0943\u092a\u092f\u093e Individual Schemes, Family Schemes, \u092f\u093e I need help \u091a\u0941\u0928\u0947\u0902\u0964",
        "Marathi": "\u0915\u0943\u092a\u092f\u093e Individual Schemes, Family Schemes, \u0915\u093f\u0902\u0935\u093e I need help \u0928\u093f\u0935\u0921\u093e.",
        "Kannada": "\u0ca6\u0caf\u0cb5\u0cbf\u0c9f\u0ccd\u0c9f\u0cc1 Individual Schemes, Family Schemes, \u0c85\u0ca5\u0cb5\u0cbe I need help \u0c86\u0caf\u0ccd\u0c95\u0cc6\u0cae\u0cbe\u0ca1\u0cbf.",
    },
    "family_intro": {
        "English": "You've chosen Family Schemes. I'll ask a few short questions about your household so I can show schemes that may be relevant.",
        "Hindi": "\u0906\u092a\u0928\u0947 Family Schemes \u091a\u0941\u0928\u093e \u0939\u0948\u0964 \u092e\u0948\u0902 \u092a\u0930\u093f\u0935\u093e\u0930 \u0915\u0947 \u092c\u093e\u0930\u0947 \u092e\u0947\u0902 \u0915\u0941\u091b \u091b\u094b\u091f\u0947 \u0938\u0935\u093e\u0932 \u092a\u0942\u091b\u0942\u0901\u0917\u093e\u0964",
        "Marathi": "\u0924\u0941\u092e\u094d\u0939\u0940 Family Schemes \u0928\u093f\u0935\u0921\u0932\u0947 \u0906\u0939\u0947. \u092e\u0940 \u0915\u0941\u091f\u0941\u0902\u092c\u093e\u092c\u0926\u094d\u0926\u0932 \u0915\u093e\u0939\u0940 \u091b\u094b\u091f\u0947 \u092a\u094d\u0930\u0936\u094d\u0928 \u0935\u093f\u091a\u093e\u0930\u0947\u0928.",
        "Kannada": "\u0ca8\u0c80\u0cb5\u0cc1 Family Schemes \u0c86\u0caf\u0ccd\u0c95\u0cc6 \u0cae\u0cbe\u0ca1\u0cbf\u0ca6\u0ccd\u0ca6\u0cc0\u0cb0\u0cbf. \u0ca8\u0cbe\u0ca8\u0cc1 \u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0c95\u0cc1\u0c9f\u0cc1\u0c82\u0cac\u0ca6 \u0cac\u0c97\u0ccd\u0c97\u0cc6 \u0c95\u0cc6\u0cb2\u0cb5\u0cc1 \u0c9a\u0cbf\u0c95\u0ccd\u0c95 \u0caa\u0ccd\u0cb0\u0cb6\u0ccd\u0ca8\u0cc6\u0c97\u0cb3\u0ca8\u0ccd\u0ca8\u0cc1 \u0c95\u0cc7\u0cb3\u0cc1\u0ca4\u0ccd\u0ca4\u0cc7\u0ca8\u0cc6.",
    },
    "individual_intro": {
        "English": "You've chosen Individual Schemes. I'll ask a few short questions so I can show schemes that may be relevant to you.",
        "Hindi": "\u0906\u092a\u0928\u0947 Individual Schemes \u091a\u0941\u0928\u093e \u0939\u0948\u0964 \u092e\u0948\u0902 \u0915\u0941\u091b \u091b\u094b\u091f\u0947 \u0938\u0935\u093e\u0932 \u092a\u0942\u091b\u0942\u0901\u0917\u093e\u0964",
        "Marathi": "\u0924\u0941\u092e\u094d\u0939\u0940 Individual Schemes \u0928\u093f\u0935\u0921\u0932\u0947 \u0906\u0939\u0947. \u092e\u0940 \u0915\u093e\u0939\u0940 \u091b\u094b\u091f\u0947 \u092a\u094d\u0930\u0936\u094d\u0928 \u0935\u093f\u091a\u093e\u0930\u0947\u0928.",
        "Kannada": "\u0ca8\u0c80\u0cb5\u0cc1 Individual Schemes \u0c86\u0caf\u0ccd\u0c95\u0cc6 \u0cae\u0cbe\u0ca1\u0cbf\u0ca6\u0ccd\u0ca6\u0cc0\u0cb0\u0cbf. \u0ca8\u0cbe\u0ca8\u0cc1 \u0c95\u0cc6\u0cb2\u0cb5\u0cc1 \u0c9a\u0cbf\u0c95\u0ccd\u0c95 \u0caa\u0ccd\u0cb0\u0cb6\u0ccd\u0ca8\u0cc6\u0c97\u0cb3\u0ca8\u0ccd\u0ca8\u0cc1 \u0c95\u0cc7\u0cb3\u0cc1\u0ca4\u0ccd\u0ca4\u0cc7\u0ca8\u0cc6.",
    },
    "help_intro": {
        "English": "I can help with that. Please tell me briefly what you need support with, and I'll create a support request for the SETU team.",
        "Hindi": "\u092e\u0948\u0902 \u0907\u0938\u092e\u0947\u0902 \u092e\u0926\u0926 \u0915\u0930 \u0938\u0915\u0924\u093e \u0939\u0942\u0901\u0964 \u0915\u0943\u092a\u092f\u093e \u0938\u0902\u0915\u094d\u0937\u0947\u092a \u092e\u0947\u0902 \u092c\u0924\u093e\u090f\u0902 \u0915\u093f \u0906\u092a\u0915\u094b \u0915\u093f\u0938 \u0938\u0939\u093e\u092f\u0924\u093e \u0915\u0940 \u091c\u093c\u0930\u0942\u0930\u0924 \u0939\u0948\u0964",
        "Marathi": "\u092e\u0940 \u092f\u093e\u0924 \u092e\u0926\u0924 \u0915\u0930\u0942 \u0936\u0915\u0924\u094b. \u0915\u0943\u092a\u092f\u093e \u0925\u094b\u0921\u0915\u094d\u092f\u093e\u0924 \u0938\u093e\u0902\u0917\u093e \u0915\u0940 \u0924\u0941\u092e\u094d\u0939\u093e\u0932\u093e \u0915\u0936\u093e\u0938\u093e\u0920\u0940 \u092e\u0926\u0924 \u0939\u0935\u0940 \u0906\u0939\u0947.",
        "Kannada": "\u0ca8\u0cbe\u0ca8\u0cc1 \u0c87\u0ca6\u0cb0\u0cb2\u0ccd\u0cb2\u0cbf \u0cb8\u0cb9\u0cbe\u0caf \u0cae\u0cbe\u0ca1\u0cac\u0cb2\u0ccd\u0cb2\u0cc6. \u0ca8\u0cbf\u0cae\u0c97\u0cc6 \u0caf\u0cbe\u0cb5 \u0cac\u0cc6\u0c82\u0cac\u0cb2 \u0cac\u0cc7\u0c95\u0cc1 \u0c8e\u0c82\u0ca6\u0cc1 \u0cb8\u0c82\u0c95\u0ccd\u0cb7\u0cbf\u0caa\u0ccd\u0ca4\u0cb5\u0cbe\u0c97\u0cbf \u0cb9\u0cc7\u0cb3\u0cbf.",
    },
    "help_logged": {
        "English": "Thanks \u2014 I've logged a support request for the SETU team (ref: SETU-{ref}).",
        "Hindi": "\u0927\u0928\u094d\u092f\u0935\u093e\u0926 \u2014 \u092e\u0948\u0902\u0928\u0947 SETU \u091f\u0940\u092e \u0915\u0947 \u0932\u093f\u090f \u090f\u0915 \u0938\u0939\u093e\u092f\u0924\u093e \u0905\u0928\u0941\u0930\u094b\u0927 \u0926\u0930\u094d\u091c \u0915\u0930 \u0926\u093f\u092f\u093e \u0939\u0948 (ref: SETU-{ref})\u0964",
        "Marathi": "\u0927\u0928\u094d\u092f\u0935\u093e\u0926 \u2014 \u092e\u0940 SETU \u091f\u0940\u092e\u0938\u093e\u0920\u0940 \u090f\u0915 \u092e\u0926\u0924 \u0935\u093f\u0928\u0902\u0924\u0940 \u0928\u094b\u0902\u0926\u0935\u0932\u0940 \u0906\u0939\u0947 (ref: SETU-{ref}).",
        "Kannada": "\u0ca7\u0ca8\u0ccd\u0caf\u0cb5\u0cbe\u0ca6\u0c97\u0cb3\u0cc1 \u2014 \u0ca8\u0cbe\u0ca8\u0cc1 SETU \u0ca4\u0c82\u0ca1\u0c95\u0ccd\u0c95\u0cbe\u0c97\u0cbf \u0cac\u0cc6\u0c82\u0cac\u0cb2 \u0cb5\u0cbf\u0ca8\u0c82\u0ca4\u0cbf\u0caf\u0ca8\u0ccd\u0ca8\u0cc1 \u0ca6\u0cbe\u0c96\u0cb2\u0cbf\u0cb8\u0cbf\u0ca6\u0ccd\u0ca6\u0cc7\u0ca8\u0cc6 (ref: SETU-{ref}).",
    },
    "end_menu": {
        "English": "Would you like to go back to the *Main Menu* or *End Chat*?",
        "Hindi": "\u0915\u094d\u092f\u093e \u0906\u092a *Main Menu* \u092a\u0930 \u091c\u093e\u0928\u093e \u091a\u093e\u0939\u0924\u0947 \u0939\u0948\u0902 \u092f\u093e *End Chat*?",
        "Marathi": "\u0924\u0941\u092e\u094d\u0939\u093e\u0932\u093e *Main Menu* \u0939\u0935\u0947 \u0906\u0939\u0947 \u0915\u0940 *End Chat*?",
        "Kannada": "\u0ca8\u0c80\u0cb5\u0cc1 *Main Menu* \u0c97\u0cc6 \u0cb9\u0ccb\u0c97\u0cb2\u0cc1 \u0cac\u0caf\u0cb8\u0cc1\u0cb5\u0cbf\u0cb0\u0cbe \u0c85\u0ca5\u0cb5\u0cbe *End Chat*?",
    },
    "choose_end": {
        "English": "Please choose *Main Menu* or *End Chat*.",
        "Hindi": "\u0915\u0943\u092a\u092f\u093e *Main Menu* \u092f\u093e *End Chat* \u091a\u0941\u0928\u0947\u0902\u0964",
        "Marathi": "\u0915\u0943\u092a\u092f\u093e *Main Menu* \u0915\u093f\u0902\u0935\u093e *End Chat* \u0928\u093f\u0935\u0921\u093e.",
        "Kannada": "\u0ca6\u0caf\u0cb5\u0cbf\u0c9f\u0ccd\u0c9f\u0cc1 *Main Menu* \u0c85\u0ca5\u0cb5\u0cbe *End Chat* \u0c86\u0caf\u0ccd\u0c95\u0cc6\u0cae\u0cbe\u0ca1\u0cbf.",
    },
    "confirm_unclear": {
        "English": "Please reply *Proceed* to match schemes, or *Edit details* to change something.",
        "Hindi": "\u092f\u094b\u091c\u0928\u093e\u090f\u0901 \u0926\u0947\u0916\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f *Proceed* \u0932\u093f\u0916\u0947\u0902, \u092f\u093e \u092c\u0926\u0932\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f *Edit details*\u0964",
        "Marathi": "\u092f\u094b\u091c\u0928\u093e \u092a\u093e\u0939\u0923\u094d\u092f\u093e\u0938\u093e\u0920\u0940 *Proceed* \u0932\u093f\u0939\u093e, \u0915\u093f\u0902\u0935\u093e \u092c\u0926\u0932\u0923\u094d\u092f\u093e\u0938\u093e\u0920\u0940 *Edit details*.",
        "Kannada": "Please reply *Proceed* or *Edit details*.",
    },
    "edit_ack": {
        "English": "No problem \u2014 let's update your details.",
        "Hindi": "\u0915\u094b\u0908 \u092c\u093e\u0924 \u0928\u0939\u0940\u0902 \u2014 \u091a\u0932\u093f\u090f \u0935\u093f\u0935\u0930\u0923 \u0905\u092a\u0921\u0947\u091f \u0915\u0930\u0924\u0947 \u0939\u0948\u0902\u0964",
        "Marathi": "\u0939\u0930\u0915\u0924 \u0928\u093e\u0939\u0940 \u2014 \u091a\u0932\u093e \u0924\u092a\u0936\u0940\u0932 \u0905\u092a\u0921\u0947\u091f \u0915\u0930\u0942\u092f\u093e.",
        "Kannada": "No problem \u2014 let's update your details.",
    },
    "scheme_pick": {
        "English": "Please reply with the scheme number or name from the list.",
        "Hindi": "\u0915\u0943\u092a\u092f\u093e \u0938\u0942\u091a\u0940 \u0938\u0947 \u092f\u094b\u091c\u0928\u093e \u0915\u093e \u0928\u0902\u092c\u0930 \u092f\u093e \u0928\u093e\u092e \u0932\u093f\u0916\u0947\u0902\u0964",
        "Marathi": "\u0915\u0943\u092a\u092f\u093e \u092f\u093e\u0926\u0940\u0924\u0940\u0932 \u092f\u094b\u091c\u0928\u0947\u091a\u093e \u0915\u094d\u0930\u092e\u093e\u0902\u0915 \u0915\u093f\u0902\u0935\u093e \u0928\u093e\u0935 \u0932\u093f\u0939\u093e.",
        "Kannada": "Please reply with the scheme number or name from the list.",
    },
    "feedback_prompt": {
        "English": "Before you go, how would you rate your experience with SETU today? (1\u20135)",
        "Hindi": "\u091c\u093e\u0928\u0947 \u0938\u0947 \u092a\u0939\u0932\u0947, SETU \u0915\u0947 \u0905\u0928\u0941\u092d\u0935 \u0915\u094b 1 \u0938\u0947 5 \u092e\u0947\u0902 \u0930\u0947\u091f \u0915\u0930\u0947\u0902\u0964",
        "Marathi": "\u091c\u093e\u0923\u094d\u092f\u093e\u092a\u0942\u0930\u094d\u0935\u0940, SETU \u0905\u0928\u0941\u092d\u0935\u093e\u0932\u093e 1 \u0924\u0947 5 \u092e\u0927\u094d\u092f\u0947 \u0930\u0947\u091f \u0915\u0930\u093e.",
        "Kannada": "Before you go, how would you rate your experience with SETU today? (1\u20135)",
    },
    "feedback_need_rating": {
        "English": "Please rate from 1 to 5.",
        "Hindi": "\u0915\u0943\u092a\u092f\u093e 1 \u0938\u0947 5 \u0924\u0915 \u0930\u0947\u091f \u0915\u0930\u0947\u0902\u0964",
        "Marathi": "\u0915\u0943\u092a\u092f\u093e 1 \u0924\u0947 5 \u092e\u0927\u094d\u092f\u0947 \u0930\u0947\u091f \u0915\u0930\u093e.",
        "Kannada": "Please rate from 1 to 5.",
    },
    "restart_menu": {
        "English": "Let's restart from the menu.",
        "Hindi": "\u091a\u0932\u093f\u090f \u092e\u0947\u0928\u094d\u092f\u0942 \u0938\u0947 \u092b\u093f\u0930 \u0936\u0941\u0930\u0942 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902\u0964",
        "Marathi": "\u091a\u0932\u093e \u092e\u0947\u0928\u0942\u092a\u093e\u0938\u0942\u0928 \u092a\u0941\u0928\u094d\u0939\u093e \u0938\u0941\u0930\u0942 \u0915\u0930\u0942\u092f\u093e.",
        "Kannada": "Let's restart from the menu.",
    },
    "after_detail_j2": {
        "English": "Reply *I need help* or *Go Back* to the list.",
        "Hindi": "*I need help* \u092f\u093e \u0938\u0942\u091a\u0940 \u092a\u0930 *Go Back* \u0932\u093f\u0916\u0947\u0902\u0964",
        "Marathi": "*I need help* \u0915\u093f\u0902\u0935\u093e \u092f\u093e\u0926\u0940\u0935\u0930 *Go Back* \u0932\u093f\u0939\u093e.",
        "Kannada": "Reply *I need help* or *Go Back* to the list.",
    },
    "after_detail_j1": {
        "English": "Reply *help* for support, or *other schemes* to go back to the list.",
        "Hindi": "\u0938\u0939\u093e\u092f\u0924\u093e \u0915\u0947 \u0932\u093f\u090f *help*, \u092f\u093e \u0938\u0942\u091a\u0940 \u0915\u0947 \u0932\u093f\u090f *other schemes* \u0932\u093f\u0916\u0947\u0902\u0964",
        "Marathi": "\u092e\u0926\u0924\u0940\u0938\u093e\u0920\u0940 *help*, \u0915\u093f\u0902\u0935\u093e \u092f\u093e\u0926\u0940\u0938\u093e\u0920\u0940 *other schemes* \u0932\u093f\u0939\u093e.",
        "Kannada": "Reply *help* for support, or *other schemes* to go back to the list.",
    },
    "continuing_in": {
        "English": "Great \u2014 continuing in {chosen}.",
        "Hindi": "\u092c\u0939\u0941\u0924 \u0905\u091a\u094d\u091b\u093e \u2014 \u0905\u092c {chosen} \u092e\u0947\u0902 \u092c\u093e\u0924 \u0915\u0930\u0947\u0902\u0917\u0947\u0964",
        "Marathi": "\u091b\u093e\u0928 \u2014 \u0906\u0924\u093e {chosen} \u092e\u0927\u094d\u092f\u0947 \u0938\u0941\u0930\u0942 \u0920\u0947\u0935\u0942\u092f\u093e.",
        "Kannada": "Great \u2014 continuing in {chosen}.",
    },
}


def normalize_language(language: str | None) -> str:
    if language in SUPPORTED:
        return language
    return "English"


def t(key: str, language: str | None, **kwargs: str) -> str:
    lang = normalize_language(language)
    packed = _STRINGS.get(key) or {}
    template = packed.get(lang) or packed.get("English") or key
    return template.format(**kwargs) if kwargs else template


def slot_prompt(slot_id: str, language: str | None, fallback: str | None = None) -> str:
    lang = normalize_language(language)
    packed = _SLOT_PROMPTS.get(slot_id) or {}
    return packed.get(lang) or packed.get("English") or fallback or slot_id


def profile_label(slot_id: str, language: str | None, fallback: str | None = None) -> str:
    lang = normalize_language(language)
    packed = _LABELS.get(slot_id) or {}
    return packed.get(lang) or packed.get("English") or fallback or slot_id


def language_instruction(language: str | None) -> str:
    lang = normalize_language(language)
    return (
        f"\nSession language is {lang}. Write EVERY user-facing sentence in {lang} only. "
        "Do not revert to a previous language. If the user just requested a language change, "
        "acknowledge once and continue entirely in the new session language.\n"
    )


def _script_counts(reply: str) -> tuple[int, int, int]:
    n_deva = n_knda = n_latin = 0
    for ch in reply:
        code = ord(ch)
        if 0x0900 <= code <= 0x097F:
            n_deva += 1
        elif 0x0C80 <= code <= 0x0CFF:
            n_knda += 1
        elif ch.isascii() and ch.isalpha():
            n_latin += 1
    return n_deva, n_knda, n_latin


def reply_matches_language(reply: str, language: str | None) -> bool:
    """True when the reply's dominant script matches the session language.

    Allows light code-mixing (a state name, an English option) so a natural
    WhatsApp reply is not discarded for a few characters in another script.
    """
    if not reply or not language:
        return True
    n_deva, n_knda, n_latin = _script_counts(reply)
    letters = n_deva + n_knda + n_latin
    if letters == 0:
        return True
    indic = n_deva + n_knda
    if language == "Kannada":
        return n_knda >= 2 and n_knda >= n_deva
    if language in ("Hindi", "Marathi"):
        return n_deva >= 2 and n_deva >= n_knda
    # English: reject a mostly Indic reply; keep a mostly-Latin one with a few native chars.
    return indic <= max(8, letters // 4)


def _slot_id(slot: object) -> str:
    if isinstance(slot, dict):
        return str(slot.get("id") or "")
    return str(slot)


def _topic_in_blob(blob: str, topic: str) -> bool:
    topic_l = topic.lower()
    if not topic_l:
        return False
    # Short Latin words only — keep "60+" / phrases as plain substring matches.
    if re.fullmatch(r"[a-z]+", topic_l) and len(topic_l) <= 8:
        return re.search(rf"\b{re.escape(topic_l)}\b", blob) is not None
    return topic_l in blob


def _slot_mentioned(blob: str, slot_id: str) -> bool:
    topics = SLOT_TOPICS.get(slot_id, (slot_id.replace("_", " "),))
    return any(_topic_in_blob(blob, topic) for topic in topics)


def is_multi_slot_prompt(reply: str, missing_slots: list) -> bool:
    """True only for a dump of multiple outstanding profile questions.

    A natural collect turn may use two question marks (ack + ask), or a short
    option hint for the *next* slot. Those must not be treated as dumps.
    """
    if not reply or not missing_slots:
        return False
    ids = [sid for sid in (_slot_id(s) for s in missing_slots) if sid]
    if not ids:
        return False

    questions = reply.count("?") + reply.count("\uff1f")
    numbered_q = len(re.findall(r"(?:^|\n)\s*\d+[).:]\s+", reply))
    blob = reply.lower()
    others = [sid for sid in ids[1:] if _slot_mentioned(blob, sid)]

    # Long form dumps (Journey 1 one-sentence list, Journey 2 numbered quiz).
    if questions >= 4:
        return True
    if len(others) >= 2:
        return True
    if others and questions >= 2:
        return True
    if others and numbered_q >= 3:
        return True
    # Next-slot-only mentions, rhetorical "right?", or 2–3 option bullets: keep.
    return False


def usable_collect_reply(reply: str, language: str | None, missing_slots: list) -> bool:
    """Whether an LLM collect-phase reply can be shown as-is."""
    text = (reply or "").strip()
    if not text:
        return False
    if not reply_matches_language(text, language):
        return False
    if is_multi_slot_prompt(text, missing_slots):
        return False
    return True
