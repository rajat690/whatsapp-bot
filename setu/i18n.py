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
        "English": "Does this look right?",
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
    "main_menu_header": {
        "English": "What would you like to explore today?",
        "Hindi": "आज आप क्या देखना चाहेंगे?",
        "Marathi": "आज तुम्हाला काय पाहायचे आहे?",
        "Kannada": "ಇಂದು ನೀವು ಏನನ್ನು ನೋಡಲು ಬಯಸುತ್ತೀರಿ?",
    },
    "menu_opt_individual": {
        "English": "Individual schemes",
        "Hindi": "व्यक्तिगत योजनाएँ",
        "Marathi": "वैयक्तिक योजना",
        "Kannada": "ವೈಯಕ್ತಿಕ ಯೋಜನೆಗಳು",
    },
    "menu_opt_family": {
        "English": "Family schemes",
        "Hindi": "परिवार योजनाएँ",
        "Marathi": "कुटुंब योजना",
        "Kannada": "ಕುಟುಂಬ ಯೋಜನೆಗಳು",
    },
    "menu_opt_category": {
        "English": "Browse by category",
        "Hindi": "श्रेणी से खोजें",
        "Marathi": "श्रेणीनुसार शोधा",
        "Kannada": "ವರ್ಗದಿಂದ ಹುಡುಕಿ",
    },
    "menu_opt_help": {
        "English": "I need help",
        "Hindi": "सहायता चाहिए",
        "Marathi": "मदत हवी",
        "Kannada": "ಸಹಾಯ ಬೇಕು",
    },
    "main_menu": {
        "English": "What would you like to explore today?",
        "Hindi": "आज आप क्या देखना चाहेंगे?",
        "Marathi": "आज तुम्हाला काय पाहायचे आहे?",
        "Kannada": "ಇಂದು ನೀವು ಏನನ್ನು ನೋಡಲು ಬಯಸುತ್ತೀರಿ?",
    },
    "consent_body": {
        "English": (
            "To suggest matching schemes, I will ask a few questions about you or your household. "
            "Your answers are used *only* to find relevant schemes — not shared for other purposes. "
            "Do you accept?"
        ),
        "Hindi": (
            "मिलती-जुलती योजनाएँ सुझाने के लिए मैं आपके या आपके परिवार के बारे में कुछ सवाल पूछूँगा। "
            "आपके जवाब *केवल* योजना खोजने के लिए इस्तेमाल होंगे — किसी और काम के लिए साझा नहीं किए जाएंगे। "
            "क्या आप सहमत हैं?"
        ),
        "Marathi": (
            "योग्य योजना सुचवण्यासाठी मी तुमच्या किंवा तुमच्या कुटुंबाबद्दल काही प्रश्न विचारेन. "
            "तुमची उत्तरे *फक्त* योजना शोधण्यासाठी वापरली जातील — इतर कारणांसाठी शेअर केली जाणार नाहीत. "
            "तुम्ही सहमत आहात का?"
        ),
        "Kannada": (
            "ಹೊಂದುವ ಯೋಜನೆಗಳನ್ನು ಸೂಚಿಸಲು ನಾನು ನಿಮ್ಮ ಅಥವಾ ನಿಮ್ಮ ಕುಟುಂಬದ ಬಗ್ಗೆ ಕೆಲವು ಪ್ರಶ್ನೆಗಳನ್ನು ಕೇಳುತ್ತೇನೆ. "
            "ನಿಮ್ಮ ಉತ್ತರಗಳನ್ನು *ಯೋಜನೆ ಹುಡುಕಾಟಕ್ಕೆ ಮಾತ್ರ* ಬಳಸಲಾಗುತ್ತದೆ — ಬೇರೆ ಉದ್ದೇಶಕ್ಕೆ ಹಂಚಲಾಗುವುದಿಲ್ಲ. "
            "ನೀವು ಒಪ್ಪುತ್ತೀರಾ?"
        ),
    },
    "consent_accept": {
        "English": "Accept",
        "Hindi": "स्वीकार करें",
        "Marathi": "स्वीकारा",
        "Kannada": "ಒಪ್ಪುತ್ತೇನೆ",
    },
    "consent_decline": {
        "English": "Decline",
        "Hindi": "अस्वीकार करें",
        "Marathi": "नाकारा",
        "Kannada": "ನಿರಾಕರಿಸಿ",
    },
    "consent_declined": {
        "English": "No problem. I will not collect more personal details. You can return to the Main menu anytime.",
        "Hindi": "कोई बात नहीं। मैं और व्यक्तिगत जानकारी नहीं पूछूँगा। आप कभी भी मुख्य मेनू पर लौट सकते हैं।",
        "Marathi": "हरकत नाही. मी आणखी वैयक्तिक माहिती विचारणार नाही. तुम्ही मुख्य मेनूवर परत जाऊ शकता.",
        "Kannada": "ಪರವಾಗಿಲ್ಲ. ನಾನು ಇನ್ನು ವೈಯಕ್ತಿಕ ವಿವರಗಳನ್ನು ಕೇಳುವುದಿಲ್ಲ. ನೀವು ಮುಖ್ಯ ಮೆನುವಿಗೆ ಹಿಂತಿರುಗಬಹುದು.",
    },
    "consent_unclear": {
        "English": "Please tap *Accept* to continue, or *Decline* to stop sharing details.",
        "Hindi": "जारी रखने के लिए *Accept* चुनें, या जानकारी न देने के लिए *Decline*।",
        "Marathi": "पुढे जाण्यासाठी *Accept* निवडा, किंवा थांबण्यासाठी *Decline*.",
        "Kannada": "ಮುಂದುವರಿಸಲು *Accept* ಒತ್ತಿ, ಅಥವಾ ನಿಲ್ಲಿಸಲು *Decline*.",
    },
    "who_intro": {
        "English": "Who should I look up schemes for?",
        "Hindi": "किसके लिए योजनाएँ देखूँ?",
        "Marathi": "कोणासाठी योजना शोधू?",
        "Kannada": "ಯಾರಿಗಾಗಿ ಯೋಜನೆಗಳನ್ನು ಹುಡುಕಲಿ?",
    },
    "who_clarify": {
        "English": "I can help — who is this for?",
        "Hindi": "मैं मदद कर सकता हूँ — यह किसके लिए है?",
        "Marathi": "मी मदत करू शकतो — हे कोणासाठी आहे?",
        "Kannada": "ನಾನು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ — ಇದು ಯಾರಿಗಾಗಿ?",
    },
    "who_ack": {
        "English": "Thanks — I noted {bits}.",
        "Hindi": "धन्यवाद — मैंने यह नोट किया: {bits}।",
        "Marathi": "धन्यवाद — मी नोंदवले: {bits}.",
        "Kannada": "ಧನ್ಯವಾದ — ನಾನು ಇದನ್ನು ಗಮನಿಸಿದೆ: {bits}.",
    },
    "who_me": {
        "English": "Schemes for me",
        "Hindi": "मेरे लिए योजनाएँ",
        "Marathi": "माझ्यासाठी योजना",
        "Kannada": "ನನಗಾಗಿ ಯೋಜನೆಗಳು",
    },
    "who_wife": {
        "English": "Schemes for my wife / spouse",
        "Hindi": "पत्नी / जीवनसाथी के लिए",
        "Marathi": "पत्नी / जोडीदारासाठी",
        "Kannada": "ಪತ್ನಿ / ಸಂಗಾತಿಗಾಗಿ",
    },
    "who_children": {
        "English": "Schemes for my children",
        "Hindi": "बच्चों के लिए योजनाएँ",
        "Marathi": "मुलांसाठी योजना",
        "Kannada": "ಮಕ್ಕಳಿಗಾಗಿ ಯೋಜನೆಗಳು",
    },
    "who_family": {
        "English": "Whole family",
        "Hindi": "पूरा परिवार",
        "Marathi": "संपूर्ण कुटुंब",
        "Kannada": "ಇಡೀ ಕುಟುಂಬ",
    },
    "who_category": {
        "English": "Browse by category",
        "Hindi": "श्रेणी से खोजें",
        "Marathi": "श्रेणीनुसार शोधा",
        "Kannada": "ವರ್ಗದಿಂದ ಹುಡುಕಿ",
    },
    "who_menu": {
        "English": "Main menu",
        "Hindi": "मुख्य मेनू",
        "Marathi": "मुख्य मेनू",
        "Kannada": "ಮುಖ್ಯ ಮೆನು",
    },
    "who_unclear": {
        "English": "Please choose who this is for, or Main menu.",
        "Hindi": "कृपया चुनें यह किसके लिए है, या मुख्य मेनू।",
        "Marathi": "कृपया कोणासाठी ते निवडा, किंवा मुख्य मेनू.",
        "Kannada": "ದಯವಿಟ್ಟು ಇದು ಯಾರಿಗೆಂದು ಆಯ್ಕೆಮಾಡಿ, ಅಥವಾ ಮುಖ್ಯ ಮೆನು.",
    },
    "confirm_proceed": {
        "English": "Proceed",
        "Hindi": "आगे बढ़ें",
        "Marathi": "पुढे जा",
        "Kannada": "ಮುಂದುವರಿಸಿ",
    },
    "confirm_edit": {
        "English": "Edit details",
        "Hindi": "विवरण बदलें",
        "Marathi": "तपशील बदला",
        "Kannada": "ವಿವರ ಬದಲಿಸಿ",
    },
    "end_opt_menu": {
        "English": "Main Menu",
        "Hindi": "मुख्य मेनू",
        "Marathi": "मुख्य मेनू",
        "Kannada": "ಮುಖ್ಯ ಮೆನು",
    },
    "end_opt_end": {
        "English": "End Chat",
        "Hindi": "चैट समाप्त",
        "Marathi": "चॅट संपवा",
        "Kannada": "ಚಾಟ್ ಮುಗಿಸಿ",
    },
    "after_back": {
        "English": "Go Back",
        "Hindi": "वापस जाएँ",
        "Marathi": "मागे जा",
        "Kannada": "ಹಿಂದೆ ಹೋಗಿ",
    },
    "after_other": {
        "English": "Other schemes",
        "Hindi": "अन्य योजनाएँ",
        "Marathi": "इतर योजना",
        "Kannada": "ಇತರೆ ಯೋಜನೆಗಳು",
    },
    "after_categories": {
        "English": "Back to categories",
        "Hindi": "श्रेणियों पर वापस",
        "Marathi": "श्रेणींकडे परत",
        "Kannada": "ವರ್ಗಗಳಿಗೆ ಹಿಂದಿರುಗಿ",
    },
    "interactive_choose": {
        "English": "Choose",
        "Hindi": "चुनें",
        "Marathi": "निवडा",
        "Kannada": "ಆಯ್ಕೆ",
    },
    "menu_unclear": {
        "English": "Please choose 1 Individual, 2 Family, 3 Browse category, or 4 I need help.",
        "Hindi": "कृपया 1 व्यक्तिगत, 2 परिवार, या 3 श्रेणी से खोजें चुनें। सहायता के लिए I need help लिखें।",
        "Marathi": "Please choose 1 Individual, 2 Family, or 3 Browse category. You can also type I need help.",
        "Kannada": "Please choose 1 Individual, 2 Family, or 3 Browse category. You can also type I need help.",
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
    "cat_language_prompt": {
        "English": "Browse by category. Which language should we use?",
        "Hindi": "श्रेणी से खोजें। किस भाषा में बात करें?",
        "Marathi": "Browse by category. Which language should we use?",
        "Kannada": "Browse by category. Which language should we use?",
    },
    "cat_language_unclear": {
        "English": "Please pick a language from the list.",
        "Hindi": "कृपया सूची से भाषा चुनें।",
        "Marathi": "Please pick a language from the list.",
        "Kannada": "Please pick a language from the list.",
    },
    "cat_state_prompt": {
        "English": "Which scheme set should I search?",
        "Hindi": "कौन सी योजनाएँ देखूँ?",
        "Marathi": "Which scheme set should I search?",
        "Kannada": "Which scheme set should I search?",
    },
    "cat_state_plus_prompt": {
        "English": "State + Central — which state?",
        "Hindi": "राज्य + केंद्र — कौन सा राज्य?",
        "Marathi": "State + Central — which state?",
        "Kannada": "State + Central — which state?",
    },
    "cat_hub_prompt": {
        "English": "Pick a topic (1–10). Reply *More* for extra categories.",
        "Hindi": "विषय चुनें (1–10)। और श्रेणियों के लिए *More* लिखें।",
        "Marathi": "Pick a topic (1–10). Reply *More* for extra categories.",
        "Kannada": "Pick a topic (1–10). Reply *More* for extra categories.",
    },
    "cat_hub2_prompt": {
        "English": "More topics — pick a number, or *Back*.",
        "Hindi": "और विषय — संख्या चुनें, या *Back*।",
        "Marathi": "More topics — pick a number, or *Back*.",
        "Kannada": "More topics — pick a number, or *Back*.",
    },
    "cat_who_prompt": {
        "English": "Who is this for? (category path only)",
        "Hindi": "यह किसके लिए है?",
        "Marathi": "Who is this for?",
        "Kannada": "Who is this for?",
    },
    "cat_pick_number": {
        "English": "Please reply with a number from the list.",
        "Hindi": "कृपया सूची में से एक नंबर लिखें।",
        "Marathi": "Please reply with a number from the list.",
        "Kannada": "Please reply with a number from the list.",
    },
    "cat_question_header": {
        "English": "{category} — question {n} of {total}",
        "Hindi": "{category} — प्रश्न {n}/{total}",
        "Marathi": "{category} — question {n} of {total}",
        "Kannada": "{category} — question {n} of {total}",
    },
    "cat_results_intro": {
        "English": "These schemes may be relevant (final eligibility depends on official verification):",
        "Hindi": "ये योजनाएँ काम आ सकती हैं (अंतिम पात्रता आधिकारिक जाँच पर निर्भर है):",
        "Marathi": "These schemes may be relevant (final eligibility depends on official verification):",
        "Kannada": "These schemes may be relevant (final eligibility depends on official verification):",
    },
    "cat_results_footer": {
        "English": "Reply with a number or scheme name. Or *Back to categories* / *Main menu*.",
        "Hindi": "नंबर या योजना का नाम लिखें। या *Back to categories* / *Main menu*।",
        "Marathi": "Reply with a number or scheme name. Or *Back to categories* / *Main menu*.",
        "Kannada": "Reply with a number or scheme name. Or *Back to categories* / *Main menu*.",
    },
    "cat_no_match": {
        "English": "I could not match schemes for this topic with the details given. Try another category, or *Main menu*.",
        "Hindi": "इन विवरणों से इस विषय की योजनाएँ नहीं मिल सकीं। दूसरी श्रेणी आज़माएँ, या *Main menu*।",
        "Marathi": "I could not match schemes for this topic with the details given. Try another category, or *Main menu*.",
        "Kannada": "I could not match schemes for this topic with the details given. Try another category, or *Main menu*.",
    },
    "cat_after_detail": {
        "English": "Reply *Back* for the numbered list, *Back to categories*, *Main menu*, or *help*.",
        "Hindi": "सूची के लिए *Back*, श्रेणियों के लिए *Back to categories*, *Main menu*, या *help* लिखें।",
        "Marathi": "Reply *Back* for the numbered list, *Back to categories*, *Main menu*, or *help*.",
        "Kannada": "Reply *Back* for the numbered list, *Back to categories*, *Main menu*, or *help*.",
    },
    "cat_intent_ack": {
        "English": "Looking at *{category}* schemes.",
        "Hindi": "*{category}* योजनाएँ देख रहे हैं।",
        "Marathi": "*{category}* योजना पाहत आहोत.",
        "Kannada": "Looking at *{category}* schemes.",
    },
    "cat_unknown": {
        "English": "I don't have a topic pack for that yet. You can *3 Browse category*, choose Individual / Family, or type *I need help*.",
        "Hindi": "उस विषय की श्रेणी अभी नहीं है। *3 श्रेणी से खोजें*, व्यक्तिगत / परिवार चुनें, या *I need help* लिखें।",
        "Marathi": "I don't have a topic pack for that yet. You can *3 Browse category*, choose Individual / Family, or type *I need help*.",
        "Kannada": "I don't have a topic pack for that yet. You can *3 Browse category*, choose Individual / Family, or type *I need help*.",
    },
    "named_list_intro": {
        "English": "I found these matching schemes in the SETU library:",
        "Hindi": "SETU सूची में ये योजनाएँ मिलीं:",
        "Marathi": "SETU यादीत या योजना सापडल्या:",
        "Kannada": "SETU ಗ್ರಂಥಾಲಯದಲ್ಲಿ ಈ ಯೋಜನೆಗಳು ಸಿಕ್ಕಿವೆ:",
    },
    "named_list_footer": {
        "English": "Reply with a number, or type another scheme name.",
        "Hindi": "नंबर लिखें, या दूसरी योजना का नाम लिखें।",
        "Marathi": "क्रमांक लिहा, किंवा दुसऱ्या योजनेचे नाव लिहा.",
        "Kannada": "ಸಂಖ್ಯೆ ಬರೆಯಿರಿ, ಅಥವಾ ಇನ್ನೊಂದು ಯೋಜನೆಯ ಹೆಸರು ಬರೆಯಿರಿ.",
    },
    "named_miss": {
        "English": (
            'I could not find a matching scheme named "{query}" in the SETU library '
            "(Central, Karnataka, and Maharashtra). I will not guess or invent details."
        ),
        "Hindi": (
            'SETU सूची (केंद्र, कर्नाटक, महाराष्ट्र) में "{query}" नाम की योजना नहीं मिली। '
            "मैं अनुमान से जानकारी नहीं बनाऊँगा।"
        ),
        "Marathi": (
            'SETU यादीत (केंद्र, कर्नाटक, महाराष्ट्र) "{query}" नावाची योजना सापडली नाही. '
            "मी तपशिल गृहीत धरणार नाही."
        ),
        "Kannada": (
            'SETU ಗ್ರಂಥಾಲಯದಲ್ಲಿ (ಕೇಂದ್ರ, ಕರ್ನಾಟಕ, ಮಹಾರಾಷ್ಟ್ರ) "{query}" ಹೆಸರಿನ ಯೋಜನೆ ಸಿಗಲಿಲ್ಲ. '
            "ನಾನು ಊಹಿಸಿ ವಿವರಗಳನ್ನು ಹೇಳುವುದಿಲ್ಲ."
        ),
    },
    "named_next_intro": {
        "English": "What next?",
        "Hindi": "आगे क्या करना चाहेंगे?",
        "Marathi": "पुढे काय करायचे?",
        "Kannada": "ಮುಂದೆ ಏನು?",
    },
    "named_next_another": {
        "English": "Ask about another scheme",
        "Hindi": "दूसरी योजना पूछें",
        "Marathi": "दुसरी योजना विचारा",
        "Kannada": "ಇನ್ನೊಂದು ಯೋಜನೆ ಕೇಳಿ",
    },
    "named_next_individual": {
        "English": "Individual schemes",
        "Hindi": "व्यक्तिगत योजनाएँ",
        "Marathi": "वैयक्तिक योजना",
        "Kannada": "ವೈಯಕ್ತಿಕ ಯೋಜನೆಗಳು",
    },
    "named_next_family": {
        "English": "Family schemes",
        "Hindi": "परिवार योजनाएँ",
        "Marathi": "कुटुंब योजना",
        "Kannada": "ಕುಟುಂಬ ಯೋಜನೆಗಳು",
    },
    "named_next_category": {
        "English": "Browse by category",
        "Hindi": "श्रेणी से खोजें",
        "Marathi": "श्रेणीनुसार शोधा",
        "Kannada": "ವರ್ಗದಿಂದ ಹುಡುಕಿ",
    },
    "named_next_menu": {
        "English": "Main menu",
        "Hindi": "मुख्य मेनू",
        "Marathi": "मुख्य मेनू",
        "Kannada": "ಮುಖ್ಯ ಮೆನು",
    },
    "named_ask_another": {
        "English": "Which scheme would you like to know about? You can also choose Individual, Family, or Main menu.",
        "Hindi": "किस योजना के बारे में जानना चाहते हैं? Individual, Family, या Main menu भी चुन सकते हैं।",
        "Marathi": "कोणत्या योजनेबद्दल जाणून घ्यायचे आहे? Individual, Family, किंवा Main menu देखील निवडता येईल.",
        "Kannada": "ಯಾವ ಯೋಜನೆಯ ಬಗ್ಗೆ ತಿಳಿಯಬೇಕು? Individual, Family, ಅಥವಾ Main menu ಆಯ್ಕೆ ಮಾಡಬಹುದು.",
    },
    "named_unclear": {
        "English": "Please type a scheme name, or choose a numbered option.",
        "Hindi": "कृपया योजना का नाम लिखें, या सूची से एक विकल्प चुनें।",
        "Marathi": "कृपया योजनेचे नाव लिहा, किंवा क्रमांक निवडा.",
        "Kannada": "ದಯವಿಟ್ಟು ಯೋಜನೆಯ ಹೆಸರು ಬರೆಯಿರಿ, ಅಥವಾ ಸಂಖ್ಯೆಯ ಆಯ್ಕೆ ಆರಿಸಿ.",
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
        "SETU fully supports English, Hindi, Marathi, and Kannada. "
        "Never say you can only speak, help, or reply in one language. "
        "Never refuse a request to use one of these four languages. "
        "If a phrase is missing in the session language, use plain English for that phrase — "
        "do not claim the language is unsupported.\n"
    )


_LANGUAGE_LOCK_RE = re.compile(
    r"("
    r"(?:can|could|will)\s+only\s+(?:help|speak|talk|reply|assist|support|chat|respond)"
    r"|"
    r"only\s+(?:help|speak|talk|reply|assist|support|available|continue|chat|respond)"
    r".{0,48}\b(?:hindi|english|marathi|kannada|हिन्दी|हिंदी|मराठी|ಕನ್ನಡ)\b"
    r"|"
    r"(?:हिन्दी|हिंदी|मराठी|ಕನ್ನಡ).{0,16}में ही"
    r"|"
    r"में ही\s+(?:सहायता|बात|जवाब|मदद)"
    r"|"
    r"(?:केवल|सिर्फ|सिर्फ़)\s+(?:हिन्दी|हिंदी|मराठी|ಕನ್ನಡ|hindi|english|marathi|kannada)"
    r"|"
    r"(?:ಮಾತ್ರ)\s+(?:ಸಹಾಯ|ಮಾತನಾಡ)"
    r")",
    re.I | re.DOTALL,
)


def claims_single_language_lock(reply: str | None) -> bool:
    """True when a reply invents a single-language-only limitation."""
    text = (reply or "").strip()
    if not text:
        return False
    return _LANGUAGE_LOCK_RE.search(text) is not None


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
    if claims_single_language_lock(text):
        return False
    if is_multi_slot_prompt(text, missing_slots):
        return False
    return True
