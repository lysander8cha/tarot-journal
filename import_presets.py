"""
Import presets for automatic card naming during deck imports
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from card_metadata import GERMAN_SUITED, LATIN_SUITED

logger = logging.getLogger(__name__)


# Standard RWS court card archetypes (for mapping)
RWS_COURT_ARCHETYPES = {
    "page": "Page",
    "knight": "Knight",
    "queen": "Queen",
    "king": "King"
}

# Standard Thoth court card archetypes (for mapping)
THOTH_COURT_ARCHETYPES = {
    "page": "Princess",
    "knight": "Prince",
    "queen": "Queen",
    "king": "Knight"
}


# Standard Tarot deck (78 cards)
STANDARD_TAROT = {
    # Major Arcana (0-21)
    "00": "The Fool", "0": "The Fool", "fool": "The Fool",
    "01": "The Magician", "1": "The Magician", "magician": "The Magician",
    "02": "The High Priestess", "2": "The High Priestess", "highpriestess": "The High Priestess", "high_priestess": "The High Priestess",
    "03": "The Empress", "3": "The Empress", "empress": "The Empress",
    "04": "The Emperor", "4": "The Emperor", "emperor": "The Emperor",
    "05": "The Hierophant", "5": "The Hierophant", "hierophant": "The Hierophant",
    "06": "The Lovers", "6": "The Lovers", "lovers": "The Lovers",
    "07": "The Chariot", "7": "The Chariot", "chariot": "The Chariot",
    "08": "Strength", "8": "Strength", "strength": "Strength",
    "09": "The Hermit", "9": "The Hermit", "hermit": "The Hermit",
    "10": "Wheel of Fortune", "wheeloffortune": "Wheel of Fortune", "wheel": "Wheel of Fortune",
    "11": "Justice", "justice": "Justice",
    "12": "The Hanged Man", "hangedman": "The Hanged Man", "hanged": "The Hanged Man",
    "13": "Death", "death": "Death",
    "14": "Temperance", "temperance": "Temperance",
    "15": "The Devil", "devil": "The Devil",
    "16": "The Tower", "tower": "The Tower",
    "17": "The Star", "star": "The Star",
    "18": "The Moon", "moon": "The Moon",
    "19": "The Sun", "sun": "The Sun",
    "20": "Judgement", "judgement": "Judgement", "judgment": "Judgement",
    "21": "The World", "world": "The World",
    
    # Wands
    "aceofwands": "Ace of Wands", "wands01": "Ace of Wands", "wands1": "Ace of Wands", "wandsace": "Ace of Wands",
    "twoofwands": "Two of Wands", "wands02": "Two of Wands", "wands2": "Two of Wands",
    "threeofwands": "Three of Wands", "wands03": "Three of Wands", "wands3": "Three of Wands",
    "fourofwands": "Four of Wands", "wands04": "Four of Wands", "wands4": "Four of Wands",
    "fiveofwands": "Five of Wands", "wands05": "Five of Wands", "wands5": "Five of Wands",
    "sixofwands": "Six of Wands", "wands06": "Six of Wands", "wands6": "Six of Wands",
    "sevenofwands": "Seven of Wands", "wands07": "Seven of Wands", "wands7": "Seven of Wands",
    "eightofwands": "Eight of Wands", "wands08": "Eight of Wands", "wands8": "Eight of Wands",
    "nineofwands": "Nine of Wands", "wands09": "Nine of Wands", "wands9": "Nine of Wands",
    "tenofwands": "Ten of Wands", "wands10": "Ten of Wands",
    "pageofwands": "Page of Wands", "wandspage": "Page of Wands", "wands11": "Page of Wands",
    "knightofwands": "Knight of Wands", "wandsknight": "Knight of Wands", "wands12": "Knight of Wands",
    "queenofwands": "Queen of Wands", "wandsqueen": "Queen of Wands", "wands13": "Queen of Wands",
    "kingofwands": "King of Wands", "wandsking": "King of Wands", "wands14": "King of Wands",
    # Wands single-letter prefix (w01-w14)
    "w01": "Ace of Wands", "w1": "Ace of Wands",
    "w02": "Two of Wands", "w2": "Two of Wands",
    "w03": "Three of Wands", "w3": "Three of Wands",
    "w04": "Four of Wands", "w4": "Four of Wands",
    "w05": "Five of Wands", "w5": "Five of Wands",
    "w06": "Six of Wands", "w6": "Six of Wands",
    "w07": "Seven of Wands", "w7": "Seven of Wands",
    "w08": "Eight of Wands", "w8": "Eight of Wands",
    "w09": "Nine of Wands", "w9": "Nine of Wands",
    "w10": "Ten of Wands",
    "w11": "Page of Wands",
    "w12": "Knight of Wands",
    "w13": "Queen of Wands",
    "w14": "King of Wands",
    
    # Cups
    "aceofcups": "Ace of Cups", "cups01": "Ace of Cups", "cups1": "Ace of Cups", "cupsace": "Ace of Cups",
    "twoofcups": "Two of Cups", "cups02": "Two of Cups", "cups2": "Two of Cups",
    "threeofcups": "Three of Cups", "cups03": "Three of Cups", "cups3": "Three of Cups",
    "fourofcups": "Four of Cups", "cups04": "Four of Cups", "cups4": "Four of Cups",
    "fiveofcups": "Five of Cups", "cups05": "Five of Cups", "cups5": "Five of Cups",
    "sixofcups": "Six of Cups", "cups06": "Six of Cups", "cups6": "Six of Cups",
    "sevenofcups": "Seven of Cups", "cups07": "Seven of Cups", "cups7": "Seven of Cups",
    "eightofcups": "Eight of Cups", "cups08": "Eight of Cups", "cups8": "Eight of Cups",
    "nineofcups": "Nine of Cups", "cups09": "Nine of Cups", "cups9": "Nine of Cups",
    "tenofcups": "Ten of Cups", "cups10": "Ten of Cups",
    "pageofcups": "Page of Cups", "cupspage": "Page of Cups", "cups11": "Page of Cups",
    "knightofcups": "Knight of Cups", "cupsknight": "Knight of Cups", "cups12": "Knight of Cups",
    "queenofcups": "Queen of Cups", "cupsqueen": "Queen of Cups", "cups13": "Queen of Cups",
    "kingofcups": "King of Cups", "cupsking": "King of Cups", "cups14": "King of Cups",
    # Cups single-letter prefix (c01-c14)
    "c01": "Ace of Cups", "c1": "Ace of Cups",
    "c02": "Two of Cups", "c2": "Two of Cups",
    "c03": "Three of Cups", "c3": "Three of Cups",
    "c04": "Four of Cups", "c4": "Four of Cups",
    "c05": "Five of Cups", "c5": "Five of Cups",
    "c06": "Six of Cups", "c6": "Six of Cups",
    "c07": "Seven of Cups", "c7": "Seven of Cups",
    "c08": "Eight of Cups", "c8": "Eight of Cups",
    "c09": "Nine of Cups", "c9": "Nine of Cups",
    "c10": "Ten of Cups",
    "c11": "Page of Cups",
    "c12": "Knight of Cups",
    "c13": "Queen of Cups",
    "c14": "King of Cups",
    
    # Swords
    "aceofswords": "Ace of Swords", "swords01": "Ace of Swords", "swords1": "Ace of Swords", "swordsace": "Ace of Swords",
    "twoofswords": "Two of Swords", "swords02": "Two of Swords", "swords2": "Two of Swords",
    "threeofswords": "Three of Swords", "swords03": "Three of Swords", "swords3": "Three of Swords",
    "fourofswords": "Four of Swords", "swords04": "Four of Swords", "swords4": "Four of Swords",
    "fiveofswords": "Five of Swords", "swords05": "Five of Swords", "swords5": "Five of Swords",
    "sixofswords": "Six of Swords", "swords06": "Six of Swords", "swords6": "Six of Swords",
    "sevenofswords": "Seven of Swords", "swords07": "Seven of Swords", "swords7": "Seven of Swords",
    "eightofswords": "Eight of Swords", "swords08": "Eight of Swords", "swords8": "Eight of Swords",
    "nineofswords": "Nine of Swords", "swords09": "Nine of Swords", "swords9": "Nine of Swords",
    "tenofswords": "Ten of Swords", "swords10": "Ten of Swords",
    "pageofswords": "Page of Swords", "swordspage": "Page of Swords", "swords11": "Page of Swords",
    "knightofswords": "Knight of Swords", "swordsknight": "Knight of Swords", "swords12": "Knight of Swords",
    "queenofswords": "Queen of Swords", "swordsqueen": "Queen of Swords", "swords13": "Queen of Swords",
    "kingofswords": "King of Swords", "swordsking": "King of Swords", "swords14": "King of Swords",
    # Swords single-letter prefix (s01-s14)
    "s01": "Ace of Swords", "s1": "Ace of Swords",
    "s02": "Two of Swords", "s2": "Two of Swords",
    "s03": "Three of Swords", "s3": "Three of Swords",
    "s04": "Four of Swords", "s4": "Four of Swords",
    "s05": "Five of Swords", "s5": "Five of Swords",
    "s06": "Six of Swords", "s6": "Six of Swords",
    "s07": "Seven of Swords", "s7": "Seven of Swords",
    "s08": "Eight of Swords", "s8": "Eight of Swords",
    "s09": "Nine of Swords", "s9": "Nine of Swords",
    "s10": "Ten of Swords",
    "s11": "Page of Swords",
    "s12": "Knight of Swords",
    "s13": "Queen of Swords",
    "s14": "King of Swords",
    
    # Pentacles
    "aceofpentacles": "Ace of Pentacles", "pentacles01": "Ace of Pentacles", "pentacles1": "Ace of Pentacles", "pentaclesace": "Ace of Pentacles",
    "twoofpentacles": "Two of Pentacles", "pentacles02": "Two of Pentacles", "pentacles2": "Two of Pentacles",
    "threeofpentacles": "Three of Pentacles", "pentacles03": "Three of Pentacles", "pentacles3": "Three of Pentacles",
    "fourofpentacles": "Four of Pentacles", "pentacles04": "Four of Pentacles", "pentacles4": "Four of Pentacles",
    "fiveofpentacles": "Five of Pentacles", "pentacles05": "Five of Pentacles", "pentacles5": "Five of Pentacles",
    "sixofpentacles": "Six of Pentacles", "pentacles06": "Six of Pentacles", "pentacles6": "Six of Pentacles",
    "sevenofpentacles": "Seven of Pentacles", "pentacles07": "Seven of Pentacles", "pentacles7": "Seven of Pentacles",
    "eightofpentacles": "Eight of Pentacles", "pentacles08": "Eight of Pentacles", "pentacles8": "Eight of Pentacles",
    "nineofpentacles": "Nine of Pentacles", "pentacles09": "Nine of Pentacles", "pentacles9": "Nine of Pentacles",
    "tenofpentacles": "Ten of Pentacles", "pentacles10": "Ten of Pentacles",
    "pageofpentacles": "Page of Pentacles", "pentaclespage": "Page of Pentacles", "pentacles11": "Page of Pentacles",
    "knightofpentacles": "Knight of Pentacles", "pentaclesknight": "Knight of Pentacles", "pentacles12": "Knight of Pentacles",
    "queenofpentacles": "Queen of Pentacles", "pentaclesqueen": "Queen of Pentacles", "pentacles13": "Queen of Pentacles",
    "kingofpentacles": "King of Pentacles", "pentaclesking": "King of Pentacles", "pentacles14": "King of Pentacles",
    # Pentacles single-letter prefix (p01-p14)
    "p01": "Ace of Pentacles", "p1": "Ace of Pentacles",
    "p02": "Two of Pentacles", "p2": "Two of Pentacles",
    "p03": "Three of Pentacles", "p3": "Three of Pentacles",
    "p04": "Four of Pentacles", "p4": "Four of Pentacles",
    "p05": "Five of Pentacles", "p5": "Five of Pentacles",
    "p06": "Six of Pentacles", "p6": "Six of Pentacles",
    "p07": "Seven of Pentacles", "p7": "Seven of Pentacles",
    "p08": "Eight of Pentacles", "p8": "Eight of Pentacles",
    "p09": "Nine of Pentacles", "p9": "Nine of Pentacles",
    "p10": "Ten of Pentacles",
    "p11": "Page of Pentacles",
    "p12": "Knight of Pentacles",
    "p13": "Queen of Pentacles",
    "p14": "King of Pentacles",
    
    # Coins (alternate for Pentacles)
    "aceofcoins": "Ace of Pentacles", "coins01": "Ace of Pentacles", "coins1": "Ace of Pentacles",
    "twoofcoins": "Two of Pentacles", "coins02": "Two of Pentacles", "coins2": "Two of Pentacles",
    "threeofcoins": "Three of Pentacles", "coins03": "Three of Pentacles", "coins3": "Three of Pentacles",
    "fourofcoins": "Four of Pentacles", "coins04": "Four of Pentacles", "coins4": "Four of Pentacles",
    "fiveofcoins": "Five of Pentacles", "coins05": "Five of Pentacles", "coins5": "Five of Pentacles",
    "sixofcoins": "Six of Pentacles", "coins06": "Six of Pentacles", "coins6": "Six of Pentacles",
    "sevenofcoins": "Seven of Pentacles", "coins07": "Seven of Pentacles", "coins7": "Seven of Pentacles",
    "eightofcoins": "Eight of Pentacles", "coins08": "Eight of Pentacles", "coins8": "Eight of Pentacles",
    "nineofcoins": "Nine of Pentacles", "coins09": "Nine of Pentacles", "coins9": "Nine of Pentacles",
    "tenofcoins": "Ten of Pentacles", "coins10": "Ten of Pentacles",
    "pageofcoins": "Page of Pentacles", "coinspage": "Page of Pentacles", "coins11": "Page of Pentacles",
    "knightofcoins": "Knight of Pentacles", "coinsknight": "Knight of Pentacles", "coins12": "Knight of Pentacles",
    "queenofcoins": "Queen of Pentacles", "coinsqueen": "Queen of Pentacles", "coins13": "Queen of Pentacles",
    "kingofcoins": "King of Pentacles", "coinsking": "King of Pentacles", "coins14": "King of Pentacles",
    
    # Disks (alternate for Pentacles - Thoth)
    "aceofdisks": "Ace of Pentacles", "disks01": "Ace of Pentacles",
    "twoofdisks": "Two of Pentacles", "disks02": "Two of Pentacles",
    "threeofdisks": "Three of Pentacles", "disks03": "Three of Pentacles",
    "fourofdisks": "Four of Pentacles", "disks04": "Four of Pentacles",
    "fiveofdisks": "Five of Pentacles", "disks05": "Five of Pentacles",
    "sixofdisks": "Six of Pentacles", "disks06": "Six of Pentacles",
    "sevenofdisks": "Seven of Pentacles", "disks07": "Seven of Pentacles",
    "eightofdisks": "Eight of Pentacles", "disks08": "Eight of Pentacles",
    "nineofdisks": "Nine of Pentacles", "disks09": "Nine of Pentacles",
    "tenofdisks": "Ten of Pentacles", "disks10": "Ten of Pentacles",
    "princessofdisks": "Page of Pentacles", "disks11": "Page of Pentacles",
    "princeofdisks": "Knight of Pentacles", "disks12": "Knight of Pentacles",
    "queenofdisks": "Queen of Pentacles", "disks13": "Queen of Pentacles",
    "knightofdisks": "King of Pentacles", "disks14": "King of Pentacles",
}

# Standard Lenormand deck (36 cards)
STANDARD_LENORMAND = {
    "01": "Rider", "1": "Rider", "rider": "Rider",
    "02": "Clover", "2": "Clover", "clover": "Clover",
    "03": "Ship", "3": "Ship", "ship": "Ship",
    "04": "House", "4": "House", "house": "House",
    "05": "Tree", "5": "Tree", "tree": "Tree",
    "06": "Clouds", "6": "Clouds", "clouds": "Clouds",
    "07": "Snake", "7": "Snake", "snake": "Snake",
    "08": "Coffin", "8": "Coffin", "coffin": "Coffin",
    "09": "Bouquet", "9": "Bouquet", "bouquet": "Bouquet", "flowers": "Bouquet",
    "10": "Scythe", "scythe": "Scythe",
    "11": "Whip", "whip": "Whip", "broom": "Whip",
    "12": "Birds", "birds": "Birds", "owls": "Birds",
    "13": "Child", "child": "Child",
    "14": "Fox", "fox": "Fox",
    "15": "Bear", "bear": "Bear",
    "16": "Stars", "stars": "Stars",
    "17": "Stork", "stork": "Stork",
    "18": "Dog", "dog": "Dog",
    "19": "Tower", "tower": "Tower",
    "20": "Garden", "garden": "Garden",
    "21": "Mountain", "mountain": "Mountain",
    "22": "Crossroads", "crossroads": "Crossroads", "paths": "Crossroads",
    "23": "Mice", "mice": "Mice",
    "24": "Heart", "heart": "Heart",
    "25": "Ring", "ring": "Ring",
    "26": "Book", "book": "Book",
    "27": "Letter", "letter": "Letter",
    "28": "Man", "man": "Man", "gentleman": "Man",
    "29": "Woman", "woman": "Woman", "lady": "Woman",
    "30": "Lily", "lily": "Lily", "lilies": "Lily",
    "31": "Sun", "sun": "Sun",
    "32": "Moon", "moon": "Moon",
    "33": "Key", "key": "Key",
    "34": "Fish", "fish": "Fish",
    "35": "Anchor", "anchor": "Anchor",
    "36": "Cross", "cross": "Cross",
}

# Standard Kipper deck (36 cards)
STANDARD_KIPPER = {
    "01": "Main Male", "1": "Main Male", "mainmale": "Main Male", "hauptperson": "Main Male",
    "02": "Main Female", "2": "Main Female", "mainfemale": "Main Female",
    "03": "Marriage", "3": "Marriage", "marriage": "Marriage", "union": "Marriage",
    "04": "Meeting", "4": "Meeting", "meeting": "Meeting", "rendezvous": "Meeting",
    "05": "Good Gentleman", "5": "Good Gentleman", "goodgentleman": "Good Gentleman", "goodman": "Good Gentleman",
    "06": "Good Lady", "6": "Good Lady", "goodlady": "Good Lady", "goodwoman": "Good Lady",
    "07": "Pleasant Letter", "7": "Pleasant Letter", "pleasantletter": "Pleasant Letter", "goodnews": "Pleasant Letter",
    "08": "False Person", "8": "False Person", "falseperson": "False Person", "falsity": "False Person",
    "09": "A Change", "9": "A Change", "change": "A Change", "achange": "A Change",
    "10": "A Journey", "journey": "A Journey", "ajourney": "A Journey", "travel": "A Journey",
    "11": "Gain Money", "gainmoney": "Gain Money", "winmoney": "Gain Money", "wealth": "Gain Money",
    "12": "Rich Girl", "richgirl": "Rich Girl", "wealthygirl": "Rich Girl",
    "13": "Rich Man", "richman": "Rich Man", "wealthyman": "Rich Man",
    "14": "Sad News", "sadnews": "Sad News", "badnews": "Sad News", "message": "Sad News",
    "15": "Success in Love", "successinlove": "Success in Love", "loversuccess": "Success in Love",
    "16": "His Thoughts", "histhoughts": "His Thoughts", "herthoughts": "His Thoughts", "thoughts": "His Thoughts",
    "17": "A Gift", "gift": "A Gift", "agift": "A Gift", "present": "A Gift",
    "18": "A Small Child", "smallchild": "A Small Child", "child": "A Small Child", "asmallchild": "A Small Child",
    "19": "A Funeral", "funeral": "A Funeral", "afuneral": "A Funeral", "death": "A Funeral",
    "20": "House", "house": "House", "home": "House",
    "21": "Living Room", "livingroom": "Living Room", "parlor": "Living Room", "room": "Living Room",
    "22": "Official Person", "officialperson": "Official Person", "military": "Official Person", "official": "Official Person",
    "23": "Court House", "courthouse": "Court House", "court": "Court House",
    "24": "Theft", "theft": "Theft", "thief": "Theft", "stealing": "Theft",
    "25": "High Honors", "highhonors": "High Honors", "honor": "High Honors", "achievement": "High Honors",
    "26": "Great Fortune", "greatfortune": "Great Fortune", "fortune": "Great Fortune", "luck": "Great Fortune",
    "27": "Unexpected Money", "unexpectedmoney": "Unexpected Money", "surprise": "Unexpected Money",
    "28": "Expectation", "expectation": "Expectation", "hope": "Expectation", "waiting": "Expectation",
    "29": "Prison", "prison": "Prison", "confinement": "Prison", "jail": "Prison",
    "30": "Court", "30": "Court", "legal": "Court", "judge": "Court", "judiciary": "Court",
    "31": "Short Illness", "shortillness": "Short Illness", "illness": "Short Illness", "sickness": "Short Illness",
    "32": "Grief and Adversity", "grief": "Grief and Adversity", "adversity": "Grief and Adversity", "sorrow": "Grief and Adversity",
    "33": "Gloomy Thoughts", "gloomythoughts": "Gloomy Thoughts", "sadness": "Gloomy Thoughts", "melancholy": "Gloomy Thoughts",
    "34": "Work", "work": "Work", "employment": "Work", "occupation": "Work", "labor": "Work",
    "35": "A Long Way", "longway": "A Long Way", "longroad": "A Long Way", "distance": "A Long Way",
    "36": "Hope, Great Water", "greatwater": "Hope, Great Water", "water": "Hope, Great Water", "ocean": "Hope, Great Water",
}

# Pre-Golden Dawn Tarot (swaps Strength/Justice - 8 and 11)
# In Marseille/Pre-Golden Dawn ordering: 8 = Justice, 11 = Strength (also called Fortitude)
PRE_GOLDEN_DAWN_TAROT = dict(STANDARD_TAROT)
# Override the numbered entries for 8 and 11
PRE_GOLDEN_DAWN_TAROT.update({
    "08": "Justice", "8": "Justice",
    "11": "Strength",
})

# Thoth Tarot - Crowley/Harris deck with different card names and court cards
# Major Arcana: Strength→Lust, Justice→Adjustment, Temperance→Art, Judgement→The Aeon, The World→The Universe
# Court Cards: King→Knight, Queen→Queen, Knight→Prince, Page→Princess
THOTH_TAROT = dict(STANDARD_TAROT)
THOTH_TAROT.update({
    # Major Arcana name changes. Thoth follows pre-Golden-Dawn (Marseille)
    # ordering for slots 8 and 11 — the card printed with VIII is Adjustment,
    # the card printed with XI is Lust. (RWS swapped them; Thoth/Marseille
    # did not.) So a file named purely "08" represents Adjustment, "11"
    # represents Lust. The "strength"/"justice" keys still map to their
    # Thoth-renamed counterparts — those are the conceptual card names.
    "08": "Adjustment", "8": "Adjustment",
    "11": "Lust",
    "strength": "Lust", "lust": "Lust",
    "justice": "Adjustment", "adjustment": "Adjustment",
    "14": "Art", "temperance": "Art", "art": "Art",
    "20": "The Aeon", "judgement": "The Aeon", "judgment": "The Aeon", "aeon": "The Aeon",
    "21": "The Universe", "world": "The Universe", "universe": "The Universe",
    
    # Wands court cards
    "pageofwands": "Princess of Wands", "wandspage": "Princess of Wands", "wands11": "Princess of Wands",
    "knightofwands": "Prince of Wands", "wandsknight": "Prince of Wands", "wands12": "Prince of Wands",
    "queenofwands": "Queen of Wands", "wandsqueen": "Queen of Wands", "wands13": "Queen of Wands",
    "kingofwands": "Knight of Wands", "wandsking": "Knight of Wands", "wands14": "Knight of Wands",
    "w11": "Princess of Wands", "w12": "Prince of Wands", "w13": "Queen of Wands", "w14": "Knight of Wands",
    "princessofwands": "Princess of Wands", "wandsprincess": "Princess of Wands",
    "princeofwands": "Prince of Wands", "wandsprince": "Prince of Wands",
    
    # Cups court cards
    "pageofcups": "Princess of Cups", "cupspage": "Princess of Cups", "cups11": "Princess of Cups",
    "knightofcups": "Prince of Cups", "cupsknight": "Prince of Cups", "cups12": "Prince of Cups",
    "queenofcups": "Queen of Cups", "cupsqueen": "Queen of Cups", "cups13": "Queen of Cups",
    "kingofcups": "Knight of Cups", "cupsking": "Knight of Cups", "cups14": "Knight of Cups",
    "c11": "Princess of Cups", "c12": "Prince of Cups", "c13": "Queen of Cups", "c14": "Knight of Cups",
    "princessofcups": "Princess of Cups", "cupsprincess": "Princess of Cups",
    "princeofcups": "Prince of Cups", "cupsprince": "Prince of Cups",
    
    # Swords court cards
    "pageofswords": "Princess of Swords", "swordspage": "Princess of Swords", "swords11": "Princess of Swords",
    "knightofswords": "Prince of Swords", "swordsknight": "Prince of Swords", "swords12": "Prince of Swords",
    "queenofswords": "Queen of Swords", "swordsqueen": "Queen of Swords", "swords13": "Queen of Swords",
    "kingofswords": "Knight of Swords", "swordsking": "Knight of Swords", "swords14": "Knight of Swords",
    "s11": "Princess of Swords", "s12": "Prince of Swords", "s13": "Queen of Swords", "s14": "Knight of Swords",
    "princessofswords": "Princess of Swords", "swordsprincess": "Princess of Swords",
    "princeofswords": "Prince of Swords", "swordsprince": "Prince of Swords",
    
    # Disks (Pentacles) court cards - Thoth calls them Disks
    "pageofpentacles": "Princess of Disks", "pentaclespage": "Princess of Disks", "pentacles11": "Princess of Disks",
    "knightofpentacles": "Prince of Disks", "pentaclesknight": "Prince of Disks", "pentacles12": "Prince of Disks",
    "queenofpentacles": "Queen of Disks", "pentaclesqueen": "Queen of Disks", "pentacles13": "Queen of Disks",
    "kingofpentacles": "Knight of Disks", "pentaclesking": "Knight of Disks", "pentacles14": "Knight of Disks",
    "p11": "Princess of Disks", "p12": "Prince of Disks", "p13": "Queen of Disks", "p14": "Knight of Disks",
    "princessofpentacles": "Princess of Disks", "pentaclesprincess": "Princess of Disks",
    "princeofpentacles": "Prince of Disks", "pentaclesprince": "Prince of Disks",
    # Disk-specific patterns
    "pageofdisks": "Princess of Disks", "diskspage": "Princess of Disks", "disks11": "Princess of Disks",
    "knightofdisks": "Prince of Disks", "disksknight": "Prince of Disks", "disks12": "Prince of Disks",
    "queenofdisks": "Queen of Disks", "disksqueen": "Queen of Disks", "disks13": "Queen of Disks",
    "kingofdisks": "Knight of Disks", "disksking": "Knight of Disks", "disks14": "Knight of Disks",
    "princessofdisks": "Princess of Disks", "disksprincess": "Princess of Disks",
    "princeofdisks": "Prince of Disks", "disksprince": "Prince of Disks",
    
    # Disks pip cards (Thoth name for Pentacles)
    "aceofdisks": "Ace of Disks", "disks01": "Ace of Disks", "disks1": "Ace of Disks", "disksace": "Ace of Disks",
    "twoofdisks": "Two of Disks", "disks02": "Two of Disks", "disks2": "Two of Disks",
    "threeofdisks": "Three of Disks", "disks03": "Three of Disks", "disks3": "Three of Disks",
    "fourofdisks": "Four of Disks", "disks04": "Four of Disks", "disks4": "Four of Disks",
    "fiveofdisks": "Five of Disks", "disks05": "Five of Disks", "disks5": "Five of Disks",
    "sixofdisks": "Six of Disks", "disks06": "Six of Disks", "disks6": "Six of Disks",
    "sevenofdisks": "Seven of Disks", "disks07": "Seven of Disks", "disks7": "Seven of Disks",
    "eightofdisks": "Eight of Disks", "disks08": "Eight of Disks", "disks8": "Eight of Disks",
    "nineofdisks": "Nine of Disks", "disks09": "Nine of Disks", "disks9": "Nine of Disks",
    "tenofdisks": "Ten of Disks", "disks10": "Ten of Disks",
    # Also map pentacles patterns to Disks for Thoth
    "aceofpentacles": "Ace of Disks", "pentacles01": "Ace of Disks", "pentacles1": "Ace of Disks", "pentaclesace": "Ace of Disks",
    "twoofpentacles": "Two of Disks", "pentacles02": "Two of Disks", "pentacles2": "Two of Disks",
    "threeofpentacles": "Three of Disks", "pentacles03": "Three of Disks", "pentacles3": "Three of Disks",
    "fourofpentacles": "Four of Disks", "pentacles04": "Four of Disks", "pentacles4": "Four of Disks",
    "fiveofpentacles": "Five of Disks", "pentacles05": "Five of Disks", "pentacles5": "Five of Disks",
    "sixofpentacles": "Six of Disks", "pentacles06": "Six of Disks", "pentacles6": "Six of Disks",
    "sevenofpentacles": "Seven of Disks", "pentacles07": "Seven of Disks", "pentacles7": "Seven of Disks",
    "eightofpentacles": "Eight of Disks", "pentacles08": "Eight of Disks", "pentacles8": "Eight of Disks",
    "nineofpentacles": "Nine of Disks", "pentacles09": "Nine of Disks", "pentacles9": "Nine of Disks",
    "tenofpentacles": "Ten of Disks", "pentacles10": "Ten of Disks",
    "p01": "Ace of Disks", "p1": "Ace of Disks",
    "p02": "Two of Disks", "p2": "Two of Disks",
    "p03": "Three of Disks", "p3": "Three of Disks",
    "p04": "Four of Disks", "p4": "Four of Disks",
    "p05": "Five of Disks", "p5": "Five of Disks",
    "p06": "Six of Disks", "p6": "Six of Disks",
    "p07": "Seven of Disks", "p7": "Seven of Disks",
    "p08": "Eight of Disks", "p8": "Eight of Disks",
    "p09": "Nine of Disks", "p9": "Nine of Disks",
    "p10": "Ten of Disks",
})

# Gnostic/Eternal Tarot - Samael Aun Weor / Glorian Publishing system
# 78 Arcana with unique names (no traditional suits for Minor Arcana)
# Major Arcana: 1-22, Minor Arcana: 23-78
GNOSTIC_ETERNAL_TAROT = {
    # Major Arcana (1-22)
    "01": "The Magician", "1": "The Magician",
    "themagician": "The Magician", "magician": "The Magician",
    "02": "The Priestess", "2": "The Priestess",
    "thepriestess": "The Priestess", "priestess": "The Priestess",
    "highpriestess": "The Priestess",
    "03": "The Empress", "3": "The Empress",
    "theempress": "The Empress", "empress": "The Empress",
    "04": "The Emperor", "4": "The Emperor",
    "theemperor": "The Emperor", "emperor": "The Emperor",
    "05": "The Hierarch", "5": "The Hierarch",
    "thehierarch": "The Hierarch", "hierarch": "The Hierarch",
    "hierophant": "The Hierarch",
    "06": "Indecision", "6": "Indecision",
    "indecision": "Indecision", "thelovers": "Indecision", "lovers": "Indecision",
    "07": "Triumph", "7": "Triumph",
    "triumph": "Triumph", "thechariot": "Triumph", "chariot": "Triumph",
    "08": "Justice", "8": "Justice",
    "justice": "Justice",
    "09": "The Hermit", "9": "The Hermit",
    "thehermit": "The Hermit", "hermit": "The Hermit",
    "10": "Retribution",
    "retribution": "Retribution", "wheeloffortune": "Retribution", "wheel": "Retribution",
    "11": "Persuasion",
    "persuasion": "Persuasion", "strength": "Persuasion",
    "12": "The Apostolate",
    "theapostolate": "The Apostolate", "apostolate": "The Apostolate",
    "hangedman": "The Apostolate", "thehangedman": "The Apostolate",
    "13": "Immortality",
    "immortality": "Immortality", "death": "Immortality",
    "14": "Temperance",
    "temperance": "Temperance",
    "15": "Passion",
    "passion": "Passion", "thedevil": "Passion", "devil": "Passion",
    "16": "Fragility",
    "fragility": "Fragility", "thetower": "Fragility", "tower": "Fragility",
    "17": "Hope",
    "hope": "Hope", "thestar": "Hope", "star": "Hope",
    "18": "Twilight",
    "twilight": "Twilight", "themoon": "Twilight", "moon": "Twilight",
    "19": "Inspiration",
    "inspiration": "Inspiration", "thesun": "Inspiration", "sun": "Inspiration",
    "20": "Resurrection",
    "resurrection": "Resurrection", "judgement": "Resurrection", "judgment": "Resurrection",
    "21": "Transmutation",
    "transmutation": "Transmutation", "theworld": "Transmutation", "world": "Transmutation",
    "22": "The Return",
    "thereturn": "The Return", "return": "The Return",
    "thefool": "The Return", "fool": "The Return",
    # Note: In Gnostic system, The Fool is Arcanum 22, not 0

    # Minor Arcana (23-78) - each with unique name
    "23": "The Plower", "theplower": "The Plower", "plower": "The Plower",
    "24": "The Weaver", "theweaver": "The Weaver", "weaver": "The Weaver",
    "25": "The Argonaut", "theargonaut": "The Argonaut", "argonaut": "The Argonaut",
    "26": "The Prodigy", "theprodigy": "The Prodigy", "prodigy": "The Prodigy",
    "27": "The Unexpected", "theunexpected": "The Unexpected", "unexpected": "The Unexpected",
    "28": "Uncertainty", "uncertainty": "Uncertainty",
    "29": "Domesticity", "domesticity": "Domesticity",
    "30": "Exchange", "exchange": "Exchange",
    "31": "Impediments", "impediments": "Impediments",
    "32": "Magnificence", "magnificence": "Magnificence",
    "33": "Alliance", "alliance": "Alliance",
    "34": "Innovation", "innovation": "Innovation",
    "35": "Grief", "grief": "Grief",
    "36": "Initiation", "initiation": "Initiation",
    "37": "Art and Science", "artandscience": "Art and Science",
    "38": "Duplicity", "duplicity": "Duplicity", "biplicity": "Duplicity",
    "39": "Testimony", "testimony": "Testimony",
    "40": "Presentiment", "presentiment": "Presentiment",
    "41": "Uneasiness", "uneasiness": "Uneasiness",
    "42": "Preeminence", "preeminence": "Preeminence",
    "43": "Hallucination", "hallucination": "Hallucination", "imagination": "Hallucination",
    "44": "Thinking", "thinking": "Thinking", "thought": "Thinking",
    "45": "Regeneration", "regeneration": "Regeneration",
    "46": "Patrimony", "patrimony": "Patrimony",
    "47": "Conjecturing", "conjecturing": "Conjecturing", "deduction": "Conjecturing",
    "48": "Consummation", "consummation": "Consummation",
    "49": "Versatility", "versatility": "Versatility",
    "50": "Affinity", "affinity": "Affinity",
    "51": "Counseling", "counseling": "Counseling",
    "52": "Premeditation", "premeditation": "Premeditation",
    "53": "Resentment", "resentment": "Resentment",
    "54": "Examination", "examination": "Examination",
    "55": "Contrition", "contrition": "Contrition",
    "56": "Pilgrimage", "pilgrimage": "Pilgrimage",
    "57": "Rivalry", "rivalry": "Rivalry",
    "58": "Requalification", "requalification": "Requalification",
    "59": "Revelation", "revelation": "Revelation",
    "60": "Evolution", "evolution": "Evolution",
    "61": "Solitude", "solitude": "Solitude",
    "62": "Proscription", "proscription": "Proscription",
    "63": "Communion", "communion": "Communion",
    "64": "Vehemence", "vehemence": "Vehemence", "zeal": "Vehemence",
    "65": "Learning", "learning": "Learning",
    "66": "Perplexity", "perplexity": "Perplexity",
    "67": "Friendship", "friendship": "Friendship",
    "68": "Speculation", "speculation": "Speculation",
    "69": "Chance", "chance": "Chance",
    "70": "Cooperation", "cooperation": "Cooperation",
    "71": "Avarice", "avarice": "Avarice",
    "72": "Purification", "purification": "Purification",
    "73": "Love and Desire", "loveanddesire": "Love and Desire",
    "74": "Offering", "offering": "Offering",
    "75": "Generosity", "generosity": "Generosity",
    "76": "The Dispenser", "thedispenser": "The Dispenser", "dispenser": "The Dispenser",
    "77": "Disorientation", "disorientation": "Disorientation",
    "78": "Renaissance", "renaissance": "Renaissance",
}

# Standard Playing Cards (52 cards)
PLAYING_CARDS_52 = {
    # Hearts
    "aceofhearts": "Ace of Hearts", "hearts01": "Ace of Hearts", "hearts1": "Ace of Hearts", "heartsace": "Ace of Hearts",
    "ah": "Ace of Hearts", "ha": "Ace of Hearts", "h1": "Ace of Hearts", "h01": "Ace of Hearts",
    "twoofhearts": "Two of Hearts", "hearts02": "Two of Hearts", "hearts2": "Two of Hearts",
    "2h": "Two of Hearts", "h2": "Two of Hearts", "h02": "Two of Hearts",
    "threeofhearts": "Three of Hearts", "hearts03": "Three of Hearts", "hearts3": "Three of Hearts",
    "3h": "Three of Hearts", "h3": "Three of Hearts", "h03": "Three of Hearts",
    "fourofhearts": "Four of Hearts", "hearts04": "Four of Hearts", "hearts4": "Four of Hearts",
    "4h": "Four of Hearts", "h4": "Four of Hearts", "h04": "Four of Hearts",
    "fiveofhearts": "Five of Hearts", "hearts05": "Five of Hearts", "hearts5": "Five of Hearts",
    "5h": "Five of Hearts", "h5": "Five of Hearts", "h05": "Five of Hearts",
    "sixofhearts": "Six of Hearts", "hearts06": "Six of Hearts", "hearts6": "Six of Hearts",
    "6h": "Six of Hearts", "h6": "Six of Hearts", "h06": "Six of Hearts",
    "sevenofhearts": "Seven of Hearts", "hearts07": "Seven of Hearts", "hearts7": "Seven of Hearts",
    "7h": "Seven of Hearts", "h7": "Seven of Hearts", "h07": "Seven of Hearts",
    "eightofhearts": "Eight of Hearts", "hearts08": "Eight of Hearts", "hearts8": "Eight of Hearts",
    "8h": "Eight of Hearts", "h8": "Eight of Hearts", "h08": "Eight of Hearts",
    "nineofhearts": "Nine of Hearts", "hearts09": "Nine of Hearts", "hearts9": "Nine of Hearts",
    "9h": "Nine of Hearts", "h9": "Nine of Hearts", "h09": "Nine of Hearts",
    "tenofhearts": "Ten of Hearts", "hearts10": "Ten of Hearts",
    "10h": "Ten of Hearts", "h10": "Ten of Hearts", "th": "Ten of Hearts",
    "jackofhearts": "Jack of Hearts", "heartsjack": "Jack of Hearts", "hearts11": "Jack of Hearts",
    "jh": "Jack of Hearts", "hj": "Jack of Hearts", "h11": "Jack of Hearts",
    "queenofhearts": "Queen of Hearts", "heartsqueen": "Queen of Hearts", "hearts12": "Queen of Hearts",
    "qh": "Queen of Hearts", "hq": "Queen of Hearts", "h12": "Queen of Hearts",
    "kingofhearts": "King of Hearts", "heartsking": "King of Hearts", "hearts13": "King of Hearts",
    "kh": "King of Hearts", "hk": "King of Hearts", "h13": "King of Hearts",

    # Diamonds
    "aceofdiamonds": "Ace of Diamonds", "diamonds01": "Ace of Diamonds", "diamonds1": "Ace of Diamonds", "diamondsace": "Ace of Diamonds",
    "ad": "Ace of Diamonds", "da": "Ace of Diamonds", "d1": "Ace of Diamonds", "d01": "Ace of Diamonds",
    "twoofdiamonds": "Two of Diamonds", "diamonds02": "Two of Diamonds", "diamonds2": "Two of Diamonds",
    "2d": "Two of Diamonds", "d2": "Two of Diamonds", "d02": "Two of Diamonds",
    "threeofdiamonds": "Three of Diamonds", "diamonds03": "Three of Diamonds", "diamonds3": "Three of Diamonds",
    "3d": "Three of Diamonds", "d3": "Three of Diamonds", "d03": "Three of Diamonds",
    "fourofdiamonds": "Four of Diamonds", "diamonds04": "Four of Diamonds", "diamonds4": "Four of Diamonds",
    "4d": "Four of Diamonds", "d4": "Four of Diamonds", "d04": "Four of Diamonds",
    "fiveofdiamonds": "Five of Diamonds", "diamonds05": "Five of Diamonds", "diamonds5": "Five of Diamonds",
    "5d": "Five of Diamonds", "d5": "Five of Diamonds", "d05": "Five of Diamonds",
    "sixofdiamonds": "Six of Diamonds", "diamonds06": "Six of Diamonds", "diamonds6": "Six of Diamonds",
    "6d": "Six of Diamonds", "d6": "Six of Diamonds", "d06": "Six of Diamonds",
    "sevenofdiamonds": "Seven of Diamonds", "diamonds07": "Seven of Diamonds", "diamonds7": "Seven of Diamonds",
    "7d": "Seven of Diamonds", "d7": "Seven of Diamonds", "d07": "Seven of Diamonds",
    "eightofdiamonds": "Eight of Diamonds", "diamonds08": "Eight of Diamonds", "diamonds8": "Eight of Diamonds",
    "8d": "Eight of Diamonds", "d8": "Eight of Diamonds", "d08": "Eight of Diamonds",
    "nineofdiamonds": "Nine of Diamonds", "diamonds09": "Nine of Diamonds", "diamonds9": "Nine of Diamonds",
    "9d": "Nine of Diamonds", "d9": "Nine of Diamonds", "d09": "Nine of Diamonds",
    "tenofdiamonds": "Ten of Diamonds", "diamonds10": "Ten of Diamonds",
    "10d": "Ten of Diamonds", "d10": "Ten of Diamonds", "td": "Ten of Diamonds",
    "jackofdiamonds": "Jack of Diamonds", "diamondsjack": "Jack of Diamonds", "diamonds11": "Jack of Diamonds",
    "jd": "Jack of Diamonds", "dj": "Jack of Diamonds", "d11": "Jack of Diamonds",
    "queenofdiamonds": "Queen of Diamonds", "diamondsqueen": "Queen of Diamonds", "diamonds12": "Queen of Diamonds",
    "qd": "Queen of Diamonds", "dq": "Queen of Diamonds", "d12": "Queen of Diamonds",
    "kingofdiamonds": "King of Diamonds", "diamondsking": "King of Diamonds", "diamonds13": "King of Diamonds",
    "kd": "King of Diamonds", "dk": "King of Diamonds", "d13": "King of Diamonds",

    # Clubs
    "aceofclubs": "Ace of Clubs", "clubs01": "Ace of Clubs", "clubs1": "Ace of Clubs", "clubsace": "Ace of Clubs",
    "ac": "Ace of Clubs", "ca": "Ace of Clubs", "c1": "Ace of Clubs", "c01": "Ace of Clubs",
    "twoofclubs": "Two of Clubs", "clubs02": "Two of Clubs", "clubs2": "Two of Clubs",
    "2c": "Two of Clubs", "c2": "Two of Clubs", "c02": "Two of Clubs",
    "threeofclubs": "Three of Clubs", "clubs03": "Three of Clubs", "clubs3": "Three of Clubs",
    "3c": "Three of Clubs", "c3": "Three of Clubs", "c03": "Three of Clubs",
    "fourofclubs": "Four of Clubs", "clubs04": "Four of Clubs", "clubs4": "Four of Clubs",
    "4c": "Four of Clubs", "c4": "Four of Clubs", "c04": "Four of Clubs",
    "fiveofclubs": "Five of Clubs", "clubs05": "Five of Clubs", "clubs5": "Five of Clubs",
    "5c": "Five of Clubs", "c5": "Five of Clubs", "c05": "Five of Clubs",
    "sixofclubs": "Six of Clubs", "clubs06": "Six of Clubs", "clubs6": "Six of Clubs",
    "6c": "Six of Clubs", "c6": "Six of Clubs", "c06": "Six of Clubs",
    "sevenofclubs": "Seven of Clubs", "clubs07": "Seven of Clubs", "clubs7": "Seven of Clubs",
    "7c": "Seven of Clubs", "c7": "Seven of Clubs", "c07": "Seven of Clubs",
    "eightofclubs": "Eight of Clubs", "clubs08": "Eight of Clubs", "clubs8": "Eight of Clubs",
    "8c": "Eight of Clubs", "c8": "Eight of Clubs", "c08": "Eight of Clubs",
    "nineofclubs": "Nine of Clubs", "clubs09": "Nine of Clubs", "clubs9": "Nine of Clubs",
    "9c": "Nine of Clubs", "c9": "Nine of Clubs", "c09": "Nine of Clubs",
    "tenofclubs": "Ten of Clubs", "clubs10": "Ten of Clubs",
    "10c": "Ten of Clubs", "c10": "Ten of Clubs", "tc": "Ten of Clubs",
    "jackofclubs": "Jack of Clubs", "clubsjack": "Jack of Clubs", "clubs11": "Jack of Clubs",
    "jc": "Jack of Clubs", "cj": "Jack of Clubs", "c11": "Jack of Clubs",
    "queenofclubs": "Queen of Clubs", "clubsqueen": "Queen of Clubs", "clubs12": "Queen of Clubs",
    "qc": "Queen of Clubs", "cq": "Queen of Clubs", "c12": "Queen of Clubs",
    "kingofclubs": "King of Clubs", "clubsking": "King of Clubs", "clubs13": "King of Clubs",
    "kc": "King of Clubs", "ck": "King of Clubs", "c13": "King of Clubs",

    # Spades
    "aceofspades": "Ace of Spades", "spades01": "Ace of Spades", "spades1": "Ace of Spades", "spadesace": "Ace of Spades",
    "as": "Ace of Spades", "sa": "Ace of Spades", "s1": "Ace of Spades", "s01": "Ace of Spades",
    "twoofspades": "Two of Spades", "spades02": "Two of Spades", "spades2": "Two of Spades",
    "2s": "Two of Spades", "s2": "Two of Spades", "s02": "Two of Spades",
    "threeofspades": "Three of Spades", "spades03": "Three of Spades", "spades3": "Three of Spades",
    "3s": "Three of Spades", "s3": "Three of Spades", "s03": "Three of Spades",
    "fourofspades": "Four of Spades", "spades04": "Four of Spades", "spades4": "Four of Spades",
    "4s": "Four of Spades", "s4": "Four of Spades", "s04": "Four of Spades",
    "fiveofspades": "Five of Spades", "spades05": "Five of Spades", "spades5": "Five of Spades",
    "5s": "Five of Spades", "s5": "Five of Spades", "s05": "Five of Spades",
    "sixofspades": "Six of Spades", "spades06": "Six of Spades", "spades6": "Six of Spades",
    "6s": "Six of Spades", "s6": "Six of Spades", "s06": "Six of Spades",
    "sevenofspades": "Seven of Spades", "spades07": "Seven of Spades", "spades7": "Seven of Spades",
    "7s": "Seven of Spades", "s7": "Seven of Spades", "s07": "Seven of Spades",
    "eightofspades": "Eight of Spades", "spades08": "Eight of Spades", "spades8": "Eight of Spades",
    "8s": "Eight of Spades", "s8": "Eight of Spades", "s08": "Eight of Spades",
    "nineofspades": "Nine of Spades", "spades09": "Nine of Spades", "spades9": "Nine of Spades",
    "9s": "Nine of Spades", "s9": "Nine of Spades", "s09": "Nine of Spades",
    "tenofspades": "Ten of Spades", "spades10": "Ten of Spades",
    "10s": "Ten of Spades", "s10": "Ten of Spades", "ts": "Ten of Spades",
    "jackofspades": "Jack of Spades", "spadesjack": "Jack of Spades", "spades11": "Jack of Spades",
    "js": "Jack of Spades", "sj": "Jack of Spades", "s11": "Jack of Spades",
    "queenofspades": "Queen of Spades", "spadesqueen": "Queen of Spades", "spades12": "Queen of Spades",
    "qs": "Queen of Spades", "sq": "Queen of Spades", "s12": "Queen of Spades",
    "kingofspades": "King of Spades", "spadesking": "King of Spades", "spades13": "King of Spades",
    "ks": "King of Spades", "sk": "King of Spades", "s13": "King of Spades",
}

# Playing Cards with Jokers (54 cards)
PLAYING_CARDS_54 = dict(PLAYING_CARDS_52)
PLAYING_CARDS_54.update({
    "joker": "Joker", "joker1": "Red Joker", "joker01": "Red Joker", "redjoker": "Red Joker",
    "joker2": "Black Joker", "joker02": "Black Joker", "blackjoker": "Black Joker",
    "jr": "Red Joker", "jb": "Black Joker",
})

# I Ching - 64 Hexagrams
# Format: position -> English name (metadata provides Chinese, pinyin, etc.)
I_CHING_HEXAGRAMS = {
    "01": "The Creative", "1": "The Creative",
    "02": "The Receptive", "2": "The Receptive",
    "03": "Difficulty at the Beginning", "3": "Difficulty at the Beginning",
    "04": "Youthful Folly", "4": "Youthful Folly",
    "05": "Waiting", "5": "Waiting",
    "06": "Conflict", "6": "Conflict",
    "07": "The Army", "7": "The Army",
    "08": "Holding Together", "8": "Holding Together",
    "09": "Small Taming", "9": "Small Taming",
    "10": "Treading",
    "11": "Peace",
    "12": "Standstill",
    "13": "Fellowship",
    "14": "Great Possession",
    "15": "Modesty",
    "16": "Enthusiasm",
    "17": "Following",
    "18": "Work on the Decayed",
    "19": "Approach",
    "20": "Contemplation",
    "21": "Biting Through",
    "22": "Grace",
    "23": "Splitting Apart",
    "24": "Return",
    "25": "Innocence",
    "26": "Great Taming",
    "27": "Nourishment",
    "28": "Great Excess",
    "29": "The Abysmal",
    "30": "The Clinging",
    "31": "Influence",
    "32": "Duration",
    "33": "Retreat",
    "34": "Great Power",
    "35": "Progress",
    "36": "Darkening of the Light",
    "37": "The Family",
    "38": "Opposition",
    "39": "Obstruction",
    "40": "Deliverance",
    "41": "Decrease",
    "42": "Increase",
    "43": "Breakthrough",
    "44": "Coming to Meet",
    "45": "Gathering Together",
    "46": "Pushing Upward",
    "47": "Oppression",
    "48": "The Well",
    "49": "Revolution",
    "50": "The Cauldron",
    "51": "The Arousing",
    "52": "Keeping Still",
    "53": "Development",
    "54": "The Marrying Maiden",
    "55": "Abundance",
    "56": "The Wanderer",
    "57": "The Gentle",
    "58": "The Joyous",
    "59": "Dispersion",
    "60": "Limitation",
    "61": "Inner Truth",
    "62": "Small Excess",
    "63": "After Completion",
    "64": "Before Completion",
    # Trigrams: filenames starting with "t" (e.g. t1.jpg, t01.jpg)
    "t1": "Heaven (Qián)", "t01": "Heaven (Qián)",
    "t2": "Earth (Kūn)", "t02": "Earth (Kūn)",
    "t3": "Thunder (Zhèn)", "t03": "Thunder (Zhèn)",
    "t4": "Water (Kǎn)", "t04": "Water (Kǎn)",
    "t5": "Mountain (Gèn)", "t05": "Mountain (Gèn)",
    "t6": "Wind (Xùn)", "t06": "Wind (Xùn)",
    "t7": "Fire (Lí)", "t07": "Fire (Lí)",
    "t8": "Lake (Duì)", "t08": "Lake (Duì)",
}

# Canonical card-list constants, hoisted so both the preset-mapping
# builders and the per-type metadata helpers share one source of truth.
BELLINE_NAMES = [
    'Destiny', "The Man's Star", "The Woman's Star", 'Nativity',
    'Success', 'Elevation', 'Honours',
    'Thought, Friendship', 'Countryside, Health', 'Gifts',
    'Betrayal', 'Departure', 'Inconstancy', 'Discovery', 'Water',
    'The Home', 'Disease', 'Change', 'Money', 'Intelligence',
    'Theft, Loss', 'Undertakings', 'Trading', 'News', 'Pleasures',
    'Peace', 'Union', 'Family', 'Love', 'The Table',
    'Passions', 'Wickedness', 'Proceedings', 'Despotism',
    'Enemies', 'Negotiations', 'Fire', 'Accident', 'Support',
    'Beauty', 'Inheritance', 'Wisdom', 'Fame', 'Chance',
    'Happiness', 'Misfortune', 'Sterility', 'Fate', 'Gracefulness',
    'Ruin', 'Delay', 'Cloister', 'Blue Card',
]

SIBILLA_SUITS = [
    ('h', 'Hearts'),
    ('c', 'Clubs'),
    ('d', 'Diamonds'),
    ('s', 'Spades'),
]
SIBILLA_RANK_WORDS = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                      'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King']
SIBILLA_BY_SUIT = {
    'Hearts': [
        'Conversation', 'House', 'Viewpoint', 'Love',
        'Gladness of Heart', 'Money', 'Scholar', 'Hope',
        'Loyalty', 'Constancy', 'Lover', 'Beloved', 'Gentleman',
    ],
    'Clubs': [
        'Marriage', 'Pride', 'Journey', 'Friend', 'Fortune',
        'Comforting Surprise', 'Great Consolation', 'Reunion',
        'Merriment', 'Levity', 'Servant', 'Young Woman', 'Doctor',
    ],
    'Diamonds': [
        'Room', 'Letter', 'Gift of Jewelry', 'Falsehood', 'Melancholy',
        'Thoughts', 'Child', 'Maid', 'Madmen', 'Thief',
        'Messenger', 'Lady', 'Merchant',
    ],
    'Spades': [
        'Sorrow', 'Old Lady', 'Widower', 'Sickness', 'Death',
        'Sighs', 'Misfortune', 'Despair', 'Prison', 'Soldier',
        'Enemy', 'Rival', 'Priest',
    ],
}

# Regional suited packs (Latin: Spanish/Italian/Portuguese; German).
# Each pack keeps its native card names ("Sota de Copas", "Fante di
# Coppe", "Herz Ober") and links to its family's shared English
# archetypes ("Knave of Cups"). Suits: (native, English, filename
# prefixes); ranks: (native, English, printed numbers). Files are
# named prefix + printed number ("c10", "d08") or by global position.
_SP_SUITS = [('Oros', 'Coins', 'o'), ('Copas', 'Cups', 'c'),
             ('Espadas', 'Swords', 'e'), ('Bastos', 'Batons', 'b')]
_SP_PIPS = [('As', 'Ace', (1,)), ('Dos', 'Two', (2,)), ('Tres', 'Three', (3,)),
            ('Cuatro', 'Four', (4,)), ('Cinco', 'Five', (5,)), ('Seis', 'Six', (6,)),
            ('Siete', 'Seven', (7,))]
_SP_COURTS = [('Sota', 'Knave', (10,)), ('Caballo', 'Knight', (11,)), ('Rey', 'King', (12,))]
_IT_SUITS = [('Denari', 'Coins', 'd'), ('Coppe', 'Cups', 'c'),
             ('Spade', 'Swords', 's'), ('Bastoni', 'Batons', 'b')]
_IT_RANKS = [('Asso', 'Ace', (1,)), ('Due', 'Two', (2,)), ('Tre', 'Three', (3,)),
             ('Quattro', 'Four', (4,)), ('Cinque', 'Five', (5,)), ('Sei', 'Six', (6,)),
             ('Sette', 'Seven', (7,)), ('Fante', 'Knave', (8,)),
             ('Cavallo', 'Knight', (9,)), ('Re', 'King', (10,))]
_DE_SUITS = [('Herz', 'Hearts', 'h'), ('Schellen', 'Bells', 's'),
             ('Laub', 'Leaves', ('l', 'g')), ('Eichel', 'Acorns', 'e')]
_DE_RANKS = [('Sieben', 'Seven', (7,)), ('Acht', 'Eight', (8,)), ('Neun', 'Nine', (9,)),
             ('Zehn', 'Ten', (10,)), ('Unter', 'Unter', (11,)), ('Ober', 'Ober', (12,)),
             ('König', 'King', (13,)), ('Ass', 'Ace', (1, 14))]

REGIONAL_PATTERNS = {
    'Spanish Playing Cards (50 cards)': {
        'type': LATIN_SUITED,
        'name': '{rank} de {suit}', 'suits': _SP_SUITS,
        'ranks': _SP_PIPS + [('Ocho', 'Eight', (8,)), ('Nueve', 'Nine', (9,))] + _SP_COURTS,
        'extras': [('Comodín', 'Joker', None, ('j', 'joker', 'comodin', 'comodín'), 2)],
    },
    'Spanish Playing Cards (40 cards)': {
        'type': LATIN_SUITED,
        'name': '{rank} de {suit}', 'suits': _SP_SUITS, 'ranks': _SP_PIPS + _SP_COURTS,
        'extras': [],
    },
    'Italian Playing Cards (40 cards)': {
        'type': LATIN_SUITED,
        'name': '{rank} di {suit}', 'suits': _IT_SUITS, 'ranks': _IT_RANKS, 'extras': [],
    },
    'German Playing Cards (32 cards)': {
        'type': GERMAN_SUITED,
        'name': '{suit} {rank}', 'suits': _DE_SUITS, 'ranks': _DE_RANKS,
        'extras': [('Weli', 'Weli', 'Bells', ('w', 'weli'), 1)],
    },
    'German Playing Cards (36 cards)': {
        'type': GERMAN_SUITED,
        'name': '{suit} {rank}', 'suits': _DE_SUITS,
        'ranks': [('Sechs', 'Six', (6,))] + _DE_RANKS,
        'extras': [('Weli', 'Weli', 'Bells', ('w', 'weli'), 1)],
    },
}


def _build_regional(pattern: dict):
    """(filename mappings, native name -> metadata) for one pack."""
    mappings: dict[str, str] = {}
    meta: dict[str, dict] = {}
    pos = 1

    def add(card, keys, archetype, rank, suit):
        nonlocal pos
        for k in (*keys, f'{pos:02d}', str(pos), card.lower().replace(' ', '')):
            mappings.setdefault(k, card)
        meta[card] = {'archetype': archetype, 'rank': rank, 'suit': suit, 'sort_order': pos}
        pos += 1

    for native_suit, suit, prefixes in pattern['suits']:
        for native_rank, rank, numbers in pattern['ranks']:
            card = pattern['name'].format(rank=native_rank, suit=native_suit)
            keys = [f'{pre}{n:02d}' for pre in (*prefixes, native_suit.lower()) for n in numbers]
            keys += [f'{pre}{n}' for pre in (*prefixes, native_suit.lower()) for n in numbers]
            add(card, keys, f'{rank} of {suit}', rank, suit)
    for card, archetype, suit, key_words, copies in pattern['extras']:
        for i in range(1, copies + 1):
            keys = [f'{w}{i}' for w in key_words] + ([*key_words] if copies == 1 else [])
            add(card, keys, archetype, archetype, suit)
        # Physical copies share one archetype; every copy sorts as the first.
        meta[card]['sort_order'] = pos - copies
    return mappings, meta


REGIONAL_PACKS = {name: _build_regional(p) for name, p in REGIONAL_PATTERNS.items()}


# Oracle Belline (53 cards). Positional 01-53 + ascii-fold name keys.
def _build_oracle_belline() -> dict:
    import re as _re
    mappings: dict[str, str] = {}
    for i, name in enumerate(BELLINE_NAMES, start=1):
        mappings[f'{i:02d}'] = name
        mappings[str(i)] = name
        # Fold to lowercase, strip punctuation/spaces — so "Thought,
        # Friendship" lookups via "thoughtfriendship".
        key = _re.sub(r"[^a-z0-9]", "", name.lower())
        mappings[key] = name
        # Also accept the leading-article form without "The" prefix.
        if name.startswith('The '):
            mappings[_re.sub(r"[^a-z0-9]", "", name[4:].lower())] = name
    return mappings


ORACLE_BELLINE = _build_oracle_belline()


# Vera Sibilla Italiana / Sibilla della Zingara (52 cards). Standard playing-card filename
# conventions (h01-h13 / c01-c13 / d01-d13 / s01-s13) plus divinatory
# name keys. Each card is one of 4 suits × 13 ranks; the name is the
# divinatory term ("Conversation" for Ace of Hearts, etc.).
def _build_sibilla_italiana() -> dict:
    import re as _re
    mappings: dict[str, str] = {}
    pos = 1
    for suit_letter, suit_name in SIBILLA_SUITS:
        for rank_idx, name in enumerate(SIBILLA_BY_SUIT[suit_name]):
            rank_num = rank_idx + 1
            rank_word = SIBILLA_RANK_WORDS[rank_idx]
            # Playing-card filename conventions
            mappings[f'{suit_letter}{rank_num:02d}'] = name
            mappings[f'{suit_letter}{rank_num}'] = name
            mappings[f'{suit_name.lower()}{rank_num:02d}'] = name
            mappings[f'{suit_name.lower()}{rank_num}'] = name
            mappings[f'{rank_word.lower()}of{suit_name.lower()}'] = name
            mappings[f'{rank_word.lower()}{suit_name.lower()}'] = name
            # Divinatory name key (ascii-fold)
            mappings[_re.sub(r"[^a-z0-9]", "", name.lower())] = name
            # Global positional 01-52
            mappings[f'{pos:02d}'] = name
            mappings[str(pos)] = name
            pos += 1
    return mappings


SIBILLA_ITALIANA = _build_sibilla_italiana()


# Fast canonical-name -> (archetype, rank, suit, sort_order) lookups
# used by the per-type metadata helpers below.
def _build_belline_lookup() -> dict:
    return {name: i for i, name in enumerate(BELLINE_NAMES, start=1)}


BELLINE_NAME_TO_POS = _build_belline_lookup()


def _build_sibilla_lookup() -> dict:
    out: dict[str, tuple] = {}
    pos = 1
    for _suit_letter, suit_name in SIBILLA_SUITS:
        for rank_idx, name in enumerate(SIBILLA_BY_SUIT[suit_name]):
            out[name] = (SIBILLA_RANK_WORDS[rank_idx], suit_name, pos)
            pos += 1
    return out


SIBILLA_NAME_TO_RSP = _build_sibilla_lookup()


# =========================================================================
# Sibylle des Salons / Sibilla Indovina (52 cards). Same playing-card
# structure as the Vera Sibilla but a different set of divinatory names
# and a different card ordering: suits go Clubs → Diamonds → Hearts →
# Spades, each suit runs King → Ace (not Ace → King), so global
# positions 1-52 line up with (Clubs K…A, Diamonds K…A, Hearts K…A,
# Spades K…A).
# =========================================================================

SIBYLLE_SALONS_SUITS = [
    ('c', 'Clubs'),
    ('d', 'Diamonds'),
    ('h', 'Hearts'),
    ('s', 'Spades'),
]

SIBYLLE_SALONS_BY_SUIT = {
    # Index 0 = King, index 12 = Ace within each suit.
    'Clubs': [
        'Protector', 'A Sincere Friend', 'Flatterer', 'Success', 'Presents',
        'Anger', 'Some Money/Small Gains', 'Enemy', 'Victory',
        'Trip To The Country', 'Hope', 'Faithfulness, Affection',
        'A Lot Of Money',
    ],
    'Diamonds': [
        'Soldier', 'Angry Woman', 'Thief', 'Journey', 'Contrariety, Displeasure',
        'Impediment', 'Chattering', 'Absence', 'Reconciliation',
        'Important Revelation', 'Consultant (M)', 'Pleasure, Pastime',
        'A Letter',
    ],
    'Hearts': [
        'Pensioner', 'Tenderness', 'Visit', 'Waiting', 'Surprise',
        'A Blonde Woman', 'Thought/Reverie', 'Love', 'Wedding',
        'City House', 'Consultant (F)', 'Country House', 'Sweet Card',
    ],
    'Spades': [
        'Lawyer', 'A Widow/Solitude', 'Dark-Haired Man', 'Infantilism/Sorrow',
        'Fright/Death', 'Weakness', 'Quarrel', 'Inconstancy',
        'Loss of Money', 'Dark-Haired Woman', 'Trap', 'Gamblers', 'Delay',
    ],
}

# Rank word for each within-suit position (0=King → 12=Ace) so both
# _NAME_TO_RSP and the by-position dispatcher can back out (rank, suit)
# from the archetype's position in its suit's list.
SIBYLLE_SALONS_RANK_WORDS = [
    'King', 'Queen', 'Jack', 'Ten', 'Nine', 'Eight', 'Seven',
    'Six', 'Five', 'Four', 'Three', 'Two', 'Ace',
]
# Numeric rank for standard filename conventions (01 = Ace, 13 = King)
# — DOES NOT track the Sibylle's own internal ordering. Used to build
# `c01` / `hearts01` / `aceofhearts` variants of the mapping keys so
# users who name their files with the standard playing-card scheme
# can still import cleanly.
SIBYLLE_SALONS_STANDARD_RANK_NUMS = [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
# Short-form ranks matching the user's own naming scheme (KC / QC /
# JC / 10C / … / 2C / AC).
SIBYLLE_SALONS_SHORT_RANKS = [
    'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2', 'A',
]


def _build_sibylle_salons() -> dict:
    """Filename → archetype-name lookup for Sibylle des Salons /
    Sibilla Indovina. Recognises three filename conventions plus name
    folds:
      1. Positional 01-52 (following the Sibylle's own ordering).
      2. Standard playing-card `h01`/`hearts01`/`aceofhearts` scheme.
      3. Short-form `kc`/`qc`/`10c`/`ac` (the user's own scheme).
    """
    import re as _re
    mappings: dict[str, str] = {}
    pos = 1
    for suit_letter, suit_name in SIBYLLE_SALONS_SUITS:
        for within_idx, name in enumerate(SIBYLLE_SALONS_BY_SUIT[suit_name]):
            std_rank_num = SIBYLLE_SALONS_STANDARD_RANK_NUMS[within_idx]
            short_rank = SIBYLLE_SALONS_SHORT_RANKS[within_idx]
            rank_word = SIBYLLE_SALONS_RANK_WORDS[within_idx]

            # Standard filename convention (01 = Ace, 13 = King).
            mappings[f'{suit_letter}{std_rank_num:02d}'] = name
            mappings[f'{suit_letter}{std_rank_num}'] = name
            mappings[f'{suit_name.lower()}{std_rank_num:02d}'] = name
            mappings[f'{suit_name.lower()}{std_rank_num}'] = name
            mappings[f'{rank_word.lower()}of{suit_name.lower()}'] = name
            mappings[f'{rank_word.lower()}{suit_name.lower()}'] = name

            # User's short-form scheme: `kc`, `qc`, `10c`, `ac`, `2c`, etc.
            # Preserved lowercase since the loader lowercases keys.
            mappings[f'{short_rank.lower()}{suit_letter}'] = name
            mappings[f'{suit_letter}{short_rank.lower()}'] = name

            # Divinatory name key (ascii-fold, punctuation stripped).
            mappings[_re.sub(r"[^a-z0-9]", "", name.lower())] = name

            # Global positional 01-52 (Sibylle's own K→A ordering).
            mappings[f'{pos:02d}'] = name
            mappings[str(pos)] = name
            pos += 1
    return mappings


SIBYLLE_SALONS = _build_sibylle_salons()


def _build_sibylle_salons_lookup() -> dict:
    """archetype name → (rank_word, suit_name, position) — used by the
    metadata helpers below to answer "which playing card is this
    divinatory name?"."""
    out: dict[str, tuple] = {}
    pos = 1
    for _suit_letter, suit_name in SIBYLLE_SALONS_SUITS:
        for within_idx, name in enumerate(SIBYLLE_SALONS_BY_SUIT[suit_name]):
            out[name] = (
                SIBYLLE_SALONS_RANK_WORDS[within_idx],
                suit_name,
                pos,
            )
            pos += 1
    return out


SIBYLLE_SALONS_NAME_TO_RSP = _build_sibylle_salons_lookup()


# Grand Etteilla Tarot (78 cards). Card 1-78 ordering matches the
# deck's LWB. Each minor card carries its position-derived rank +
# suit so existing tarot UI affordances (suit grouping, court vs
# pip) still work.
ETTEILLA_TRUMPS = [
    'Chaos', "Hiram's Freemasonry", 'The Order of the Mopses',
    'The Swimming Pool', 'The Gospel', 'The Sky', 'The Snake',
    'Eve', 'Solomon', 'The Angel of the Apocalypse', 'David',
    'Moses', 'The High Priest', 'The Evil Force', 'Aaron',
    'The Last Judgement', 'Death', 'Judas', 'The Capitol',
    'Nebuchadnezzar', 'Rehoboam', 'The Monarch',
]

# (pos, name, rank, suit) — kept in lock-step with the seeder in
# database/core.py. Suits use "Sticks/Cups/Swords/Coins" per the LWB.
ETTEILLA_MINORS = [
    (23, 'The Queen',            'Queen',  'Sticks'),
    (24, 'The Knight on Patrol', 'Knight', 'Sticks'),
    (25, 'The Messenger',        'Knave',  'Sticks'),
    (26, 'The Ten Sticks',       'Ten',    'Sticks'),
    (27, 'The Nine Sticks',      'Nine',   'Sticks'),
    (28, 'The Eight Sticks',     'Eight',  'Sticks'),
    (29, 'The Seven Sticks',     'Seven',  'Sticks'),
    (30, 'The Six Sticks',       'Six',    'Sticks'),
    (31, 'The Five Sticks',      'Five',   'Sticks'),
    (32, 'The Four Sticks',      'Four',   'Sticks'),
    (33, 'The Three Sticks',     'Three',  'Sticks'),
    (34, 'The Two Sticks',       'Two',    'Sticks'),
    (35, 'The One Stick',        'Ace',    'Sticks'),
    (36, 'The Pope',             'King',   'Sticks'),
    (37, 'The Woman Pope',       'Queen',  'Cups'),
    (38, 'The Roman Knight',     'Knight', 'Cups'),
    (39, 'The Chamberlain',      'Knave',  'Cups'),
    (40, 'The Ten Cups',         'Ten',    'Cups'),
    (41, 'The Nine Cups',        'Nine',   'Cups'),
    (42, 'The Eight Cups',       'Eight',  'Cups'),
    (43, 'The Seven Cups',       'Seven',  'Cups'),
    (44, 'The Six Cups',         'Six',    'Cups'),
    (45, 'The Five Cups',        'Five',   'Cups'),
    (46, 'The Four Cups',        'Four',   'Cups'),
    (47, 'The Three Cups',       'Three',  'Cups'),
    (48, 'The Two Cups',         'Two',    'Cups'),
    (49, 'The One Cup',          'Ace',    'Cups'),
    (50, 'The Emperor',          'King',   'Cups'),
    (51, 'The Empress',          'Queen',  'Swords'),
    (52, 'The Equerry',          'Knight', 'Swords'),
    (53, 'The Soldier',          'Knave',  'Swords'),
    (54, 'The Ten Swords',       'Ten',    'Swords'),
    (55, 'The Nine Swords',      'Nine',   'Swords'),
    (56, 'The Eight Swords',     'Eight',  'Swords'),
    (57, 'The Seven Swords',     'Seven',  'Swords'),
    (58, 'The Six Swords',       'Six',    'Swords'),
    (59, 'The Five Swords',      'Five',   'Swords'),
    (60, 'The Four Swords',      'Four',   'Swords'),
    (61, 'The Three Swords',     'Three',  'Swords'),
    (62, 'The Two Swords',       'Two',    'Swords'),
    (63, 'The One Sword',        'Ace',    'Swords'),
    (64, 'The Egyptian Sultan',  'King',   'Swords'),
    (65, 'The Queen of Sheba',   'Queen',  'Coins'),
    (66, 'The Tartar Horseman',  'Knight', 'Coins'),
    (67, 'The Beggar',           'Knave',  'Coins'),
    (68, 'The Ten Shields',      'Ten',    'Coins'),
    (69, 'The Nine Sequins',     'Nine',   'Coins'),
    (70, 'The Eight Ducats',     'Eight',  'Coins'),
    (71, 'The Seven Florins',    'Seven',  'Coins'),
    (72, 'The Six Guineas',      'Six',    'Coins'),
    (73, 'The Five Ounces',      'Five',   'Coins'),
    (74, 'The Four Shields',     'Four',   'Coins'),
    (75, 'The Three Shields',    'Three',  'Coins'),
    (76, 'The Two Denarius',     'Two',    'Coins'),
    (77, 'The Golden Sun',       'Ace',    'Coins'),
    (78, 'The Alchemist',        'King',   'Coins'),
]


def _build_etteilla_position_lookup():
    """(name → (pos, rank, suit)) for both trumps and minors."""
    out: dict[str, tuple] = {}
    for i, name in enumerate(ETTEILLA_TRUMPS, start=1):
        out[name] = (i, str(i), 'Major Arcana')
    for pos, name, rank, suit in ETTEILLA_MINORS:
        out[name] = (pos, rank, suit)
    return out


ETTEILLA_NAME_TO_PRS = _build_etteilla_position_lookup()


def _build_grand_etteilla() -> dict:
    """Filename → archetype name. Card names come from the LWB; the
    filename convention follows the standard tarot decks in the app:

    - Majors: `00.jpg`-`21.jpg` (file index = trump number - 1).
      `00` is Chaos, `21` is The Monarch.
    - Minors: single-letter suit prefix (w/c/s/p) + 01-14 for Ace
      through King. The `11` slot is the Knave since the Etteilla
      doesn't have a Page.

    Folded archetype-name keys (e.g. `chaos`, `alchemist`) are also
    included as a name-based fallback.
    """
    import re as _re
    mappings: dict[str, str] = {}

    # Majors: 00 → trump 1 (Chaos), 21 → trump 22 (The Monarch).
    for trump_num, name in enumerate(ETTEILLA_TRUMPS, start=1):
        file_idx = trump_num - 1
        mappings[f'{file_idx:02d}'] = name
        mappings[str(file_idx)] = name
        mappings[_re.sub(r"[^a-z0-9]", "", name.lower())] = name
        if name.startswith('The '):
            mappings[_re.sub(r"[^a-z0-9]", "", name[4:].lower())] = name

    # Minors: look up by (rank_word, suit). w/c/s/p prefix follows
    # the existing Tarot presets in this file.
    rank_to_index = {
        'Ace': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5,
        'Six': 6, 'Seven': 7, 'Eight': 8, 'Nine': 9, 'Ten': 10,
        'Knave': 11, 'Knight': 12, 'Queen': 13, 'King': 14,
    }
    suit_prefix = {'Sticks': 'w', 'Cups': 'c', 'Swords': 's', 'Coins': 'p'}
    for _pos, name, rank, suit in ETTEILLA_MINORS:
        idx = rank_to_index[rank]
        prefix = suit_prefix[suit]
        mappings[f'{prefix}{idx:02d}'] = name
        mappings[f'{prefix}{idx}'] = name
        mappings[_re.sub(r"[^a-z0-9]", "", name.lower())] = name
        if name.startswith('The '):
            mappings[_re.sub(r"[^a-z0-9]", "", name[4:].lower())] = name

    return mappings


GRAND_ETTEILLA = _build_grand_etteilla()




# Built-in presets
# Default card back filename patterns (matched case-insensitively, without extension)
DEFAULT_CARD_BACK_PATTERNS = [
    "cardback", "card_back", "card-back",
    "back", "deckback", "deck_back", "deck-back",
    "cover", "reverse", "verso",
    "00_back", "00-back", "00back",
    "back_00", "back-00", "back00",
]

# Grand Jeu de Mlle Lenormand (54 cards)
# Also called the Astro-Mythological Lenormand.
# 52 playing-card-based cards + 2 Consultant cards (Man/Woman).
# Each card depicts a Greek mythological scene and belongs to one of five
# thematic groups: The Golden Fleece, The Trojan War, The Hermetic Science,
# The Order of Time (Zodiac), and The Unforeseen.
GRAND_LENORMAND = {
    # --- Clubs ---
    # Ace of Clubs — Golden Fleece: Jason fights for the Golden Fleece
    "aceofclubs": "Ace of Clubs", "clubsace": "Ace of Clubs", "clubs01": "Ace of Clubs",
    "clubs1": "Ace of Clubs", "ac": "Ace of Clubs", "c01": "Ace of Clubs", "c1": "Ace of Clubs",
    # 2 of Clubs — Unforeseen: Goddesses with gold pots by a river
    "2ofclubs": "2 of Clubs", "clubs02": "2 of Clubs", "clubs2": "2 of Clubs",
    "c02": "2 of Clubs", "c2": "2 of Clubs",
    # 3 of Clubs — Hermetic Science: Alchemist observing dissolving matter
    "3ofclubs": "3 of Clubs", "clubs03": "3 of Clubs", "clubs3": "3 of Clubs",
    "c03": "3 of Clubs", "c3": "3 of Clubs",
    # 4 of Clubs — Hermetic Science: Alchemist between containers
    "4ofclubs": "4 of Clubs", "clubs04": "4 of Clubs", "clubs4": "4 of Clubs",
    "c04": "4 of Clubs", "c4": "4 of Clubs",
    # 5 of Clubs — Trojan War: Paris abducting Helen
    "5ofclubs": "5 of Clubs", "clubs05": "5 of Clubs", "clubs5": "5 of Clubs",
    "c05": "5 of Clubs", "c5": "5 of Clubs",
    # 6 of Clubs — Trojan War: Paris and Menelaus in combat
    "6ofclubs": "6 of Clubs", "clubs06": "6 of Clubs", "clubs6": "6 of Clubs",
    "c06": "6 of Clubs", "c6": "6 of Clubs",
    # 7 of Clubs — Zodiac/Capricorn: God Pan transforms into Capricorn
    "7ofclubs": "7 of Clubs", "clubs07": "7 of Clubs", "clubs7": "7 of Clubs",
    "c07": "7 of Clubs", "c7": "7 of Clubs",
    # 8 of Clubs — Hermetic Science: Alchemist between two containers
    "8ofclubs": "8 of Clubs", "clubs08": "8 of Clubs", "clubs8": "8 of Clubs",
    "c08": "8 of Clubs", "c8": "8 of Clubs",
    # 9 of Clubs — Golden Fleece/Zodiac: Hercules fighting the Lernaean Hydra
    "9ofclubs": "9 of Clubs", "clubs09": "9 of Clubs", "clubs9": "9 of Clubs",
    "c09": "9 of Clubs", "c9": "9 of Clubs",
    # 10 of Clubs — Trojan War: Ulysses and Diomedes stealing Rhesus's horses
    "10ofclubs": "10 of Clubs", "clubs10": "10 of Clubs",
    "c10": "10 of Clubs",
    # Jack of Clubs — Unforeseen: Hippomenes dropping golden apples before Atalanta
    "jackofclubs": "Jack of Clubs", "clubsjack": "Jack of Clubs", "clubs11": "Jack of Clubs",
    "jc": "Jack of Clubs", "c11": "Jack of Clubs",
    # Queen of Clubs — Unforeseen: Three Hesperides guarding the golden apple tree
    "queenofclubs": "Queen of Clubs", "clubsqueen": "Queen of Clubs", "clubs12": "Queen of Clubs",
    "qc": "Queen of Clubs", "c12": "Queen of Clubs",
    # King of Clubs — Golden Fleece: Phineas directing the Argonauts
    "kingofclubs": "King of Clubs", "clubsking": "King of Clubs", "clubs13": "King of Clubs",
    "kc": "King of Clubs", "c13": "King of Clubs",

    # --- Diamonds ---
    # Ace of Diamonds — Unforeseen: Harpocrates handing Mercury a letter
    "aceofdiamonds": "Ace of Diamonds", "diamondsace": "Ace of Diamonds", "diamonds01": "Ace of Diamonds",
    "diamonds1": "Ace of Diamonds", "ad": "Ace of Diamonds", "d01": "Ace of Diamonds", "d1": "Ace of Diamonds",
    # 2 of Diamonds — Unforeseen: Child riding a goat (Zeus/Amalthea)
    "2ofdiamonds": "2 of Diamonds", "diamonds02": "2 of Diamonds", "diamonds2": "2 of Diamonds",
    "d02": "2 of Diamonds", "d2": "2 of Diamonds",
    # 3 of Diamonds — Zodiac/Gemini: Castor and Pollux holding hands
    "3ofdiamonds": "3 of Diamonds", "diamonds03": "3 of Diamonds", "diamonds3": "3 of Diamonds",
    "d03": "3 of Diamonds", "d3": "3 of Diamonds",
    # 4 of Diamonds — Golden Fleece: Medea giving Jason a package
    "4ofdiamonds": "4 of Diamonds", "diamonds04": "4 of Diamonds", "diamonds4": "4 of Diamonds",
    "d04": "4 of Diamonds", "d4": "4 of Diamonds",
    # 5 of Diamonds — Zodiac/Scorpio: Phaeton dropping reins of the sun chariot
    "5ofdiamonds": "5 of Diamonds", "diamonds05": "5 of Diamonds", "diamonds5": "5 of Diamonds",
    "d05": "5 of Diamonds", "d5": "5 of Diamonds",
    # 6 of Diamonds — Unforeseen: Mongoose in crocodile's jaws
    "6ofdiamonds": "6 of Diamonds", "diamonds06": "6 of Diamonds", "diamonds6": "6 of Diamonds",
    "d06": "6 of Diamonds", "d6": "6 of Diamonds",
    # 7 of Diamonds — Unforeseen: Pandora opening the forbidden box
    "7ofdiamonds": "7 of Diamonds", "diamonds07": "7 of Diamonds", "diamonds7": "7 of Diamonds",
    "d07": "7 of Diamonds", "d7": "7 of Diamonds",
    # 8 of Diamonds — Zodiac/Aquarius: Ganymede presenting ambrosia to the gods
    "8ofdiamonds": "8 of Diamonds", "diamonds08": "8 of Diamonds", "diamonds8": "8 of Diamonds",
    "d08": "8 of Diamonds", "d8": "8 of Diamonds",
    # 9 of Diamonds — Golden Fleece: Argonauts embarking on the ship Argo
    "9ofdiamonds": "9 of Diamonds", "diamonds09": "9 of Diamonds", "diamonds9": "9 of Diamonds",
    "d09": "9 of Diamonds", "d9": "9 of Diamonds",
    # 10 of Diamonds — Golden Fleece: Pelias giving Jason advice in his palace
    "10ofdiamonds": "10 of Diamonds", "diamonds10": "10 of Diamonds",
    "d10": "10 of Diamonds",
    # Jack of Diamonds — Trojan War: Ulysses disguised seeking Achilles
    "jackofdiamonds": "Jack of Diamonds", "diamondsjack": "Jack of Diamonds", "diamonds11": "Jack of Diamonds",
    "jd": "Jack of Diamonds", "d11": "Jack of Diamonds",
    # Queen of Diamonds — Trojan War: Wedding of Peleus and Thetis; Eris throws discord apple
    "queenofdiamonds": "Queen of Diamonds", "diamondsqueen": "Queen of Diamonds", "diamonds12": "Queen of Diamonds",
    "qd": "Queen of Diamonds", "d12": "Queen of Diamonds",
    # King of Diamonds — Unforeseen: Minerva receiving Hermes about Rhodes snake invasion
    "kingofdiamonds": "King of Diamonds", "diamondsking": "King of Diamonds", "diamonds13": "King of Diamonds",
    "kd": "King of Diamonds", "d13": "King of Diamonds",

    # --- Spades ---
    # Ace of Spades — Zodiac/Taurus: Jupiter as bull carrying Europa across the sea
    "aceofspades": "Ace of Spades", "spadesace": "Ace of Spades", "spades01": "Ace of Spades",
    "spades1": "Ace of Spades", "as": "Ace of Spades", "s01": "Ace of Spades", "s1": "Ace of Spades",
    # 2 of Spades — Trojan War: Greek princes consulting prophet Calchas
    "2ofspades": "2 of Spades", "spades02": "2 of Spades", "spades2": "2 of Spades",
    "s02": "2 of Spades", "s2": "2 of Spades",
    # 3 of Spades — Unforeseen: The Three Fates (Clotho, Lachesis, Atropos)
    "3ofspades": "3 of Spades", "spades03": "3 of Spades", "spades3": "3 of Spades",
    "s03": "3 of Spades", "s3": "3 of Spades",
    # 4 of Spades — Unforeseen: Juno disguised as old woman deceiving Semele
    "4ofspades": "4 of Spades", "spades04": "4 of Spades", "spades4": "4 of Spades",
    "s04": "4 of Spades", "s4": "4 of Spades",
    # 5 of Spades — Zodiac/Sagittarius: Centaur Chiron transformed into Sagittarius
    "5ofspades": "5 of Spades", "spades05": "5 of Spades", "spades5": "5 of Spades",
    "s05": "5 of Spades", "s5": "5 of Spades",
    # 6 of Spades — Trojan War: Wooden horse entering Troy
    "6ofspades": "6 of Spades", "spades06": "6 of Spades", "spades6": "6 of Spades",
    "s06": "6 of Spades", "s6": "6 of Spades",
    # 7 of Spades — Hermetic Science: Alchemist introducing raw materials
    "7ofspades": "7 of Spades", "spades07": "7 of Spades", "spades7": "7 of Spades",
    "s07": "7 of Spades", "s7": "7 of Spades",
    # 8 of Spades — Trojan War: Achilles dragging Hector's corpse
    "8ofspades": "8 of Spades", "spades08": "8 of Spades", "spades8": "8 of Spades",
    "s08": "8 of Spades", "s8": "8 of Spades",
    # 9 of Spades — Trojan War: Iris bringing news to Helen
    "9ofspades": "9 of Spades", "spades09": "9 of Spades", "spades9": "9 of Spades",
    "s09": "9 of Spades", "s9": "9 of Spades",
    # 10 of Spades — Unforeseen: Laverna (goddess of thieves) with wolves
    "10ofspades": "10 of Spades", "spades10": "10 of Spades",
    "s10": "10 of Spades",
    # Jack of Spades — Zodiac/Libra: Philosopher with balance weighing materials
    "jackofspades": "Jack of Spades", "spadesjack": "Jack of Spades", "spades11": "Jack of Spades",
    "js": "Jack of Spades", "s11": "Jack of Spades",
    # Queen of Spades — Unforeseen: Isis discovering dead Osiris
    "queenofspades": "Queen of Spades", "spadesqueen": "Queen of Spades", "spades12": "Queen of Spades",
    "qs": "Queen of Spades", "s12": "Queen of Spades",
    # King of Spades — Unforeseen: Menes presiding over a legal plea
    "kingofspades": "King of Spades", "spadesking": "King of Spades", "spades13": "King of Spades",
    "ks": "King of Spades", "s13": "King of Spades",

    # --- Hearts ---
    # Ace of Hearts — Unforeseen: Danaus surrounded by his fifty daughters
    "aceofhearts": "Ace of Hearts", "heartsace": "Ace of Hearts", "hearts01": "Ace of Hearts",
    "hearts1": "Ace of Hearts", "ah": "Ace of Hearts", "h01": "Ace of Hearts", "h1": "Ace of Hearts",
    # 2 of Hearts — Unforeseen: Covey of partridges stopped by a dog
    "2ofhearts": "2 of Hearts", "hearts02": "2 of Hearts", "hearts2": "2 of Hearts",
    "h02": "2 of Hearts", "h2": "2 of Hearts",
    # 3 of Hearts — Unforeseen: Baboon holding a roll of paper
    "3ofhearts": "3 of Hearts", "hearts03": "3 of Hearts", "hearts3": "3 of Hearts",
    "h03": "3 of Hearts", "h3": "3 of Hearts",
    # 4 of Hearts — Zodiac/Pisces: Venus and Cupid on dolphin backs
    "4ofhearts": "4 of Hearts", "hearts04": "4 of Hearts", "hearts4": "4 of Hearts",
    "h04": "4 of Hearts", "h4": "4 of Hearts",
    # 5 of Hearts — Unforeseen: Two gentlemen received by a king
    "5ofhearts": "5 of Hearts", "hearts05": "5 of Hearts", "hearts5": "5 of Hearts",
    "h05": "5 of Hearts", "h5": "5 of Hearts",
    # 6 of Hearts — Hermetic Science: Alchemist observing gold transformation
    "6ofhearts": "6 of Hearts", "hearts06": "6 of Hearts", "hearts6": "6 of Hearts",
    "h06": "6 of Hearts", "h6": "6 of Hearts",
    # 7 of Hearts — Hermetic Science: Alchemist with solvent and philosopher's lamp
    "7ofhearts": "7 of Hearts", "hearts07": "7 of Hearts", "hearts7": "7 of Hearts",
    "h07": "7 of Hearts", "h7": "7 of Hearts",
    # 8 of Hearts — Unforeseen: Eagle taking a toad over a pond
    "8ofhearts": "8 of Hearts", "hearts08": "8 of Hearts", "hearts8": "8 of Hearts",
    "h08": "8 of Hearts", "h8": "8 of Hearts",
    # 9 of Hearts — Zodiac/Leo: Hercules subduing the Nemean lion
    "9ofhearts": "9 of Hearts", "hearts09": "9 of Hearts", "hearts9": "9 of Hearts",
    "h09": "9 of Hearts", "h9": "9 of Hearts",
    # 10 of Hearts — Hermetic Science: Alchemist contemplating whitened matter
    "10ofhearts": "10 of Hearts", "hearts10": "10 of Hearts",
    "h10": "10 of Hearts",
    # Jack of Hearts — Zodiac/Aries: Jupiter (ram-headed) shows Bacchus a spring
    "jackofhearts": "Jack of Hearts", "heartsjack": "Jack of Hearts", "hearts11": "Jack of Hearts",
    "jh": "Jack of Hearts", "h11": "Jack of Hearts",
    # Queen of Hearts — Zodiac/Virgo: Jupiter pointing out Astraea's place in heaven
    "queenofhearts": "Queen of Hearts", "heartsqueen": "Queen of Hearts", "hearts12": "Queen of Hearts",
    "qh": "Queen of Hearts", "h12": "Queen of Hearts",
    # King of Hearts — Unforeseen: King with harp
    "kingofhearts": "King of Hearts", "heartsking": "King of Hearts", "hearts13": "King of Hearts",
    "kh": "King of Hearts", "h13": "King of Hearts",

    # --- Consultant cards ---
    # Male Consultant
    "man": "Man (Consultant)", "male": "Man (Consultant)", "consultant": "Man (Consultant)",
    "consultantman": "Man (Consultant)", "maleconsultant": "Man (Consultant)",
    "53": "Man (Consultant)",
    # Female Consultant
    "woman": "Woman (Consultant)", "female": "Woman (Consultant)",
    "consultantwoman": "Woman (Consultant)", "femaleconsultant": "Woman (Consultant)",
    "54": "Woman (Consultant)",
}


BUILTIN_PRESETS = {
    "Tarot (RWS Ordering)": {
        "type": "Tarot",
        "mappings": STANDARD_TAROT,
        "description": "Rider-Waite-Smith ordering: 8=Strength, 11=Justice. Standard 78-card tarot deck.",
        "suit_names": {"wands": "Wands", "cups": "Cups", "swords": "Swords", "pentacles": "Pentacles"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Tarot (Pre-Golden Dawn Ordering)": {
        "type": "Tarot",
        "mappings": PRE_GOLDEN_DAWN_TAROT,
        "description": "Marseille/Pre-Golden Dawn ordering: 8=Justice, 11=Strength. Standard 78-card tarot deck.",
        "suit_names": {"wands": "Wands", "cups": "Cups", "swords": "Swords", "pentacles": "Pentacles"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Tarot (Thoth)": {
        "type": "Tarot",
        "mappings": THOTH_TAROT,
        "description": "Crowley/Harris Thoth deck: Lust, Adjustment, The Aeon, The Universe. Knight/Queen/Prince/Princess courts. Disks instead of Pentacles.",
        "suit_names": {"wands": "Wands", "cups": "Cups", "swords": "Swords", "pentacles": "Disks"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Tarot (Gnostic/Eternal)": {
        "type": "Tarot",
        "mappings": GNOSTIC_ETERNAL_TAROT,
        "description": "Gnostic/Samael Aun Weor system (Glorian Publishing). 78 Arcana with unique names. No traditional suits - Minor Arcana are Arcanum 23-78.",
        "suit_names": {},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Lenormand (36 cards)": {
        "type": "Petit Lenormand",
        "mappings": STANDARD_LENORMAND,
        "description": "Standard 36-card Lenormand deck",
        "suit_names": {"hearts": "Hearts", "diamonds": "Diamonds", "clubs": "Clubs", "spades": "Spades"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Grand Lenormand (54 cards)": {
        "type": "Petit Lenormand",
        "mappings": GRAND_LENORMAND,
        "description": "Grand Jeu de Mlle Lenormand (Astro-Mythological). 52 playing-card-based cards with Greek mythology scenes + 2 Consultant cards. Five groups: Golden Fleece, Trojan War, Hermetic Science, Zodiac, The Unforeseen.",
        "suit_names": {"hearts": "Hearts", "diamonds": "Diamonds", "clubs": "Clubs", "spades": "Spades"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Kipper (36 cards)": {
        "type": "Kipper",
        "mappings": STANDARD_KIPPER,
        "description": "Traditional German 36-card Kipper fortune-telling deck",
        "suit_names": {},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    **{
        name: {
            "type": pattern['type'],
            "mappings": REGIONAL_PACKS[name][0],
            "description": (
                f"{len(REGIONAL_PACKS[name][1])} cards in "
                + ", ".join(n for n, _e, _p in pattern['suits'])
                + "; native card names, linked to the shared "
                + f"{pattern['type']} archetypes. Files: suit letter + printed number "
                + "(" + ", ".join(f"{p[0]}=" + n for n, _e, p in pattern['suits']) + ") or 01, 02…"),
            "suit_names": {e.lower(): n for n, e, _p in pattern['suits']},
            "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS,
        }
        for name, pattern in REGIONAL_PATTERNS.items()
    },
    "Oracle Belline (53 cards)": {
        "type": "Oracle Belline",
        "mappings": ORACLE_BELLINE,
        "description": "Edmond Billaudot's 53-card Oracle Belline.",
        "suit_names": {},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Vera Sibilla Italiana (52 cards)": {
        "type": "Vera Sibilla Italiana / Sibilla della Zingara",
        "mappings": SIBILLA_ITALIANA,
        "description": "52-card Vera Sibilla Italiana — playing-card structure (4 suits × 13 ranks) with each card bearing a divinatory name (Conversation for Ace of Hearts, Death for Five of Spades, etc.). Imported cards are tagged with their underlying playing-card rank + suit. Shares the same archetypes as the Sibilla della Zingara preset.",
        "suit_names": {"hearts": "Hearts", "diamonds": "Diamonds", "clubs": "Clubs", "spades": "Spades"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Sibilla della Zingara (52 cards)": {
        "type": "Vera Sibilla Italiana / Sibilla della Zingara",
        "mappings": SIBILLA_ITALIANA,
        "description": "52-card Sibilla della Zingara — same divinatory names as the Vera Sibilla, but imported cards are NOT tagged with the underlying playing-card rank + suit (the Zingara art doesn't surface the playing-card inset, so the imported cards stay pure oracle-style).",
        "suit_names": {},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Sibylle des Salons / Sibilla Indovina (52 cards)": {
        "type": "Sibylle des Salons / Sibilla Indovina",
        "mappings": SIBYLLE_SALONS,
        "description": "52-card Sibylle des Salons / Sibilla Indovina — playing-card structure (4 suits × 13 ranks) with each card bearing a divinatory name (Protector for King of Clubs, Delay for Ace of Spades, etc.). Suits run Clubs → Diamonds → Hearts → Spades, each suit ordered King → Ace, so positional filenames 01-52 line up with the LWB. Imported cards are tagged with their underlying playing-card rank + suit.",
        "suit_names": {"hearts": "Hearts", "diamonds": "Diamonds", "clubs": "Clubs", "spades": "Spades"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Grand Etteilla Tarot (78 cards)": {
        "type": "Tarot",
        "mappings": GRAND_ETTEILLA,
        "description": "78-card Grand Etteilla. Card names come from the deck's LWB — trumps use the biblical / esoteric titles (Chaos, Hiram's Freemasonry, …, The Monarch), and each minor suit's King is the deck's named figure (Pope, Emperor, Egyptian Sultan, Alchemist), with coin number cards using distinct currency names. Filenames follow the standard tarot convention: majors 00.jpg-21.jpg, sticks w01.jpg-w14.jpg, cups c01.jpg-c14.jpg, swords s01.jpg-s14.jpg, coins p01.jpg-p14.jpg. The `11` slot in each suit is the Knave since the Etteilla has no Page.",
        "suit_names": {"wands": "Sticks", "cups": "Cups", "swords": "Swords", "pentacles": "Coins"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Playing Cards (52 cards)": {
        "type": "Playing Cards",
        "mappings": PLAYING_CARDS_52,
        "description": "Standard 52-card playing card deck (Hearts, Diamonds, Clubs, Spades)",
        "suit_names": {"hearts": "Hearts", "diamonds": "Diamonds", "clubs": "Clubs", "spades": "Spades"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "Playing Cards with Jokers (54 cards)": {
        "type": "Playing Cards",
        "mappings": PLAYING_CARDS_54,
        "description": "Playing card deck with 2 jokers (52 cards + Red Joker + Black Joker)",
        "suit_names": {"hearts": "Hearts", "diamonds": "Diamonds", "clubs": "Clubs", "spades": "Spades"},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    },
    "I Ching (64 Hexagrams)": {
        "type": "I Ching",
        "mappings": I_CHING_HEXAGRAMS,
        "description": "64 I Ching Hexagrams with Chinese characters, pinyin, and English translations",
        "suit_names": {},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS,
        "custom_fields": [
            {"name": "Hexagram", "type": "text"},
            {"name": "Pinyin", "type": "text"},
            {"name": "Simplified Chinese", "type": "text"},
            {"name": "Traditional Chinese", "type": "text"},
        ]
    },
    "Oracle (filename only)": {
        "type": "Oracle",
        "mappings": {},
        "description": "Uses cleaned filename as card name (for custom oracle decks)",
        "suit_names": {},
        "card_back_patterns": DEFAULT_CARD_BACK_PATTERNS
    }
}


class ImportPresets:
    """Manages import presets for automatic card naming"""
    
    def __init__(self, presets_file: str = None):
        if presets_file is None:
            self.presets_file = Path(os.path.dirname(os.path.abspath(__file__))) / 'import_presets.json'
        else:
            self.presets_file = Path(presets_file)
        
        self.custom_presets = {}
        self._load_presets()
    
    def _load_presets(self):
        """Load custom presets from file"""
        if self.presets_file.exists():
            try:
                with open(self.presets_file, 'r') as f:
                    self.custom_presets = json.load(f)
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"Failed to load custom presets: {e}")
                self.custom_presets = {}
    
    def _save_presets(self):
        """Save custom presets to file"""
        try:
            with open(self.presets_file, 'w') as f:
                json.dump(self.custom_presets, f, indent=2)
        except (IOError, OSError) as e:
            logger.error(f"Error saving presets: {e}")
    
    def get_all_presets(self) -> Dict:
        """Get all presets (builtin + custom, with custom overriding builtin if same name)"""
        all_presets = dict(BUILTIN_PRESETS)
        for name, preset in self.custom_presets.items():
            # If custom preset has same name as builtin, it overrides the builtin
            if name in BUILTIN_PRESETS:
                all_presets[name] = preset  # Override builtin
            else:
                all_presets[f"Custom: {name}"] = preset
        return all_presets
    
    def is_preset_customized(self, name: str) -> bool:
        """Check if a builtin preset has been customized"""
        clean_name = name.replace("Custom: ", "")
        return clean_name in self.custom_presets and clean_name in BUILTIN_PRESETS
    
    def get_preset_names(self) -> List[str]:
        """Get list of all preset names"""
        return list(self.get_all_presets().keys())
    
    def get_preset(self, name: str) -> Optional[Dict]:
        """Get a specific preset by name"""
        # Check if it's a builtin that has been customized
        if name in BUILTIN_PRESETS and name in self.custom_presets:
            return self.custom_presets[name]
        
        if name in BUILTIN_PRESETS:
            return BUILTIN_PRESETS[name]
        
        clean_name = name.replace("Custom: ", "")
        if clean_name in self.custom_presets:
            return self.custom_presets[clean_name]
        
        return None
    
    def add_custom_preset(self, name: str, cartomancy_type: str, 
                         mappings: Dict[str, str], description: str = "",
                         suit_names: Dict[str, str] = None):
        """Add or update a custom preset"""
        self.custom_presets[name] = {
            "type": cartomancy_type,
            "mappings": mappings,
            "description": description
        }
        if suit_names:
            self.custom_presets[name]["suit_names"] = suit_names
        self._save_presets()
    
    def delete_custom_preset(self, name: str):
        """Delete a custom preset"""
        clean_name = name.replace("Custom: ", "")
        if clean_name in self.custom_presets:
            del self.custom_presets[clean_name]
            self._save_presets()
    
    def map_filename_to_card(self, filename: str, preset_name: str = None,
                              custom_suit_names: dict = None) -> str:
        """
        Map a filename to a card name using the specified preset.
        Returns the mapped name or a cleaned version of the filename.
        custom_suit_names: dict with keys 'wands', 'cups', 'swords', 'pentacles'
        """
        # Get just the filename without extension
        stem = Path(filename).stem

        # Create normalized key (lowercase, no spaces/separators)
        normalized = re.sub(r'[\s_\-\.]', '', stem.lower())

        # Try to find in preset
        if preset_name:
            preset = self.get_preset(preset_name)
            if preset and preset.get('mappings'):
                mappings = preset['mappings']

                # Direct match
                if normalized in mappings:
                    card_name = mappings[normalized]
                    return self._apply_custom_suit_names(card_name, custom_suit_names)

                # Try with original stem
                if stem.lower() in mappings:
                    card_name = mappings[stem.lower()]
                    return self._apply_custom_suit_names(card_name, custom_suit_names)

                # Try stripping leading numbers (e.g., "22_ace_of_wands" -> "aceofwands")
                # This handles filenames like "22_ace_of_wands.jpg" where the number is a sort prefix
                stripped_normalized = re.sub(r'^\d+', '', normalized)
                if stripped_normalized and stripped_normalized in mappings:
                    card_name = mappings[stripped_normalized]
                    return self._apply_custom_suit_names(card_name, custom_suit_names)

                # Try extracting just numbers from filename (for patterns like "PLen-A-01")
                number_match = re.search(r'(\d+)(?=\D*$)', stem)
                if number_match:
                    number_only = number_match.group(1)
                    if number_only in mappings:
                        card_name = mappings[number_only]
                        return self._apply_custom_suit_names(card_name, custom_suit_names)

        # Fall back to cleaned filename
        return self._clean_filename(stem)
    
    def _apply_custom_suit_names(self, card_name: str, custom_suit_names: dict = None) -> str:
        """Replace default suit names with custom ones"""
        if not custom_suit_names:
            return card_name
        
        # Map of default names to their keys
        default_suits = {
            'Wands': 'wands',
            'Cups': 'cups',
            'Swords': 'swords',
            'Pentacles': 'pentacles',
        }
        
        for default_name, key in default_suits.items():
            if f'of {default_name}' in card_name:
                custom_name = custom_suit_names.get(key, default_name)
                return card_name.replace(f'of {default_name}', f'of {custom_name}')
        
        return card_name
    
    def _clean_filename(self, filename: str) -> str:
        """Clean a filename into a readable card name"""
        # Replace separators with spaces
        name = re.sub(r'[\s_\-\.]+', ' ', filename)
        # Title case
        name = name.title()
        # Clean up spacing
        name = ' '.join(name.split())
        return name
    
    def find_card_back_image(self, folder: str, preset_name: str = None) -> Optional[str]:
        """
        Find a card back image in the folder based on preset patterns.
        Returns the full path to the card back image, or None if not found.
        """
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        folder_path = Path(folder)

        if not folder_path.exists():
            return None

        # Get patterns from preset, or use defaults
        patterns = DEFAULT_CARD_BACK_PATTERNS
        if preset_name:
            preset = self.get_preset(preset_name)
            if preset and preset.get('card_back_patterns'):
                patterns = preset['card_back_patterns']

        # Search for matching files
        for filepath in folder_path.iterdir():
            if filepath.suffix.lower() in valid_extensions:
                stem_lower = filepath.stem.lower()
                # Check for exact match with any pattern
                for pattern in patterns:
                    if stem_lower == pattern.lower():
                        return str(filepath)

        return None

    def is_card_back_file(self, filename: str, preset_name: str = None) -> bool:
        """
        Check if a filename matches card back patterns.
        """
        stem_lower = Path(filename).stem.lower()

        # Get patterns from preset, or use defaults
        patterns = DEFAULT_CARD_BACK_PATTERNS
        if preset_name:
            preset = self.get_preset(preset_name)
            if preset and preset.get('card_back_patterns'):
                patterns = preset['card_back_patterns']

        for pattern in patterns:
            if stem_lower == pattern.lower():
                return True
        return False

    def preview_import_with_metadata(self, folder: str, preset_name: str,
                                      custom_suit_names: dict = None,
                                      custom_court_names: dict = None,
                                      archetype_mapping: str = None) -> List[dict]:
        """
        Preview what cards would be imported from a folder, including full metadata.
        Returns list of dicts with: filename, name, sort_order, archetype, rank, suit
        Excludes card back images from the list.

        custom_court_names: dict with keys 'page', 'knight', 'queen', 'king'
        archetype_mapping: 'Map to RWS archetypes', 'Map to Thoth archetypes', or 'Create new archetypes'
        """
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        results = []

        folder_path = Path(folder)
        if not folder_path.exists():
            return results

        for filepath in sorted(folder_path.iterdir()):
            if filepath.suffix.lower() in valid_extensions:
                # Skip card back images
                if self.is_card_back_file(filepath.name, preset_name):
                    continue
                mapped_name = self.map_filename_to_card(filepath.name, preset_name, custom_suit_names)
                # Apply court card name customization
                if custom_court_names:
                    mapped_name = self._apply_custom_court_names(mapped_name, custom_court_names, preset_name)

                # Get metadata from the mapped name
                preset = self.get_preset(preset_name)
                preset_type = preset.get('type') if preset else None

                # For I Ching, extract sort_order from filename since mapped name loses the number
                # (e.g., "01" -> "The Creative", but we need sort_order=1)
                if preset_type == 'I Ching':
                    sort_order = self._get_card_sort_order(filepath.stem, custom_suit_names,
                                                           preset_name, custom_court_names)
                    if sort_order != 999:
                        metadata = self._get_iching_metadata_by_position(sort_order)
                    else:
                        metadata = self.get_card_metadata(mapped_name, preset_name, custom_suit_names,
                                                          custom_court_names, archetype_mapping)
                        sort_order = metadata.get('sort_order', 999)
                else:
                    # For Gnostic/Eternal Tarot, use filename stem for sort order (like I Ching)
                    # since card names don't contain numeric prefixes
                    is_gnostic = preset_name and 'gnostic' in preset_name.lower()
                    if is_gnostic:
                        sort_order = self._get_card_sort_order(filepath.stem, custom_suit_names,
                                                               preset_name, custom_court_names)
                        if sort_order != 999:
                            metadata = self._get_gnostic_tarot_metadata(mapped_name, sort_order)
                        else:
                            metadata = self.get_card_metadata(mapped_name, preset_name, custom_suit_names,
                                                              custom_court_names, archetype_mapping)
                            sort_order = metadata.get('sort_order', 999)
                    else:
                        # For all other presets (Tarot, Lenormand, etc.), use mapped name for metadata
                        # This ensures proper sort order (0-21 for Major, 1xx-4xx for Minor suits)
                        metadata = self.get_card_metadata(mapped_name, preset_name, custom_suit_names,
                                                          custom_court_names, archetype_mapping)
                        sort_order = metadata.get('sort_order', 999)

                results.append({
                    'filename': filepath.name,
                    'name': mapped_name,
                    'sort_order': sort_order,
                    'archetype': metadata.get('archetype'),
                    'rank': metadata.get('rank'),
                    'suit': metadata.get('suit'),
                    'custom_fields': metadata.get('custom_fields'),
                })

        # Sort by sort order
        results.sort(key=lambda x: x['sort_order'])

        return results
    
    def get_card_metadata(self, card_name: str, preset_name: str, custom_suit_names: dict = None,
                          custom_court_names: dict = None, archetype_mapping: str = None) -> dict:
        """
        Get full metadata for a card based on its name and the preset.
        Returns dict with: archetype, rank, suit, sort_order

        custom_court_names: dict with keys 'page', 'knight', 'queen', 'king'
        archetype_mapping: 'Map to RWS archetypes', 'Map to Thoth archetypes', or 'Create new archetypes'
        """
        preset = self.get_preset(preset_name)
        preset_type = preset.get('type', 'Oracle') if preset else 'Oracle'

        sort_order = self._get_card_sort_order(card_name, custom_suit_names, preset_name, custom_court_names)

        if preset_type == 'Tarot':
            return self._get_tarot_metadata(card_name, sort_order, custom_suit_names, preset_name,
                                            custom_court_names, archetype_mapping)
        elif preset_type == 'Petit Lenormand':
            is_grand = preset_name and 'grand' in preset_name.lower()
            if is_grand:
                return self._get_grand_lenormand_metadata(card_name, sort_order)
            return self._get_lenormand_metadata(card_name, sort_order)
        elif preset_type == 'Kipper':
            return self._get_kipper_metadata(card_name, sort_order)
        elif preset_type == 'Playing Cards':
            return self._get_playing_card_metadata(card_name, sort_order)
        elif preset_type == 'I Ching':
            return self._get_iching_metadata(card_name, sort_order)
        elif preset_type in (LATIN_SUITED, GERMAN_SUITED):
            return self._get_regional_metadata(card_name, sort_order, preset_name)
        elif preset_type == 'Oracle Belline':
            return self._get_belline_metadata(card_name, sort_order)
        elif preset_type == 'Vera Sibilla Italiana / Sibilla della Zingara':
            # The Zingara preset shares the archetype list but skips
            # the playing-card rank/suit tags (the Zingara art doesn't
            # surface the inset). Detect via preset name; same pattern
            # the Tarot+Gnostic and Lenormand+Grand branches use above.
            is_zingara = preset_name and 'zingara' in preset_name.lower()
            if is_zingara:
                return self._get_sibilla_zingara_metadata(card_name, sort_order)
            return self._get_sibilla_metadata(card_name, sort_order)
        elif preset_type == 'Sibylle des Salons / Sibilla Indovina':
            return self._get_sibylle_salons_metadata(card_name, sort_order)
        else:
            # Oracle
            return self._get_oracle_metadata(card_name, sort_order)

    def get_card_metadata_by_sort_order(self, sort_order: int, preset_name: str) -> dict:
        """
        Get metadata for a card based purely on its sort order position (1, 2, 3...).
        This is useful when cards don't have parseable names but are in the correct order.
        Returns dict with: archetype, rank, suit, sort_order
        """
        preset = self.get_preset(preset_name)
        preset_type = preset.get('type', 'Oracle') if preset else 'Oracle'

        # Use a placeholder card name - the metadata functions will use sort_order
        placeholder_name = f"Card {sort_order}"

        if preset_type == 'Tarot':
            # Check if it's Gnostic - it uses sort_order directly
            is_gnostic = preset_name and 'gnostic' in preset_name.lower()
            if is_gnostic:
                return self._get_gnostic_tarot_metadata(placeholder_name, sort_order)
            # Grand Etteilla — Tarot variant with its own LWB 1-78
            # ordering. Same discriminator style as Gnostic.
            is_etteilla = preset_name and 'etteilla' in preset_name.lower()
            if is_etteilla:
                return self._get_etteilla_metadata_by_position(sort_order)
            # Standard RWS / Thoth / Pre-Golden Dawn Tarot.
            return self._get_tarot_metadata_by_position(sort_order, preset_name)
        elif preset_type == 'Petit Lenormand':
            is_grand = preset_name and 'grand' in preset_name.lower()
            if is_grand:
                return self._get_grand_lenormand_metadata(placeholder_name, sort_order)
            return self._get_lenormand_metadata_by_position(sort_order)
        elif preset_type == 'Kipper':
            return self._get_kipper_metadata_by_position(sort_order)
        elif preset_type == 'Playing Cards':
            return self._get_playing_card_metadata_by_position(sort_order)
        elif preset_type == 'I Ching':
            return self._get_iching_metadata_by_position(sort_order)
        elif preset_type in (LATIN_SUITED, GERMAN_SUITED):
            return self._get_regional_metadata_by_position(sort_order, preset_name)
        elif preset_type == 'Oracle Belline':
            return self._get_belline_metadata_by_position(sort_order)
        elif preset_type == 'Vera Sibilla Italiana / Sibilla della Zingara':
            is_zingara = preset_name and 'zingara' in preset_name.lower()
            if is_zingara:
                return self._get_sibilla_zingara_metadata_by_position(sort_order)
            return self._get_sibilla_metadata_by_position(sort_order)
        elif preset_type == 'Sibylle des Salons / Sibilla Indovina':
            return self._get_sibylle_salons_metadata_by_position(sort_order)
        else:
            # Oracle - just return basic info
            return {
                'archetype': placeholder_name,
                'rank': str(sort_order),
                'suit': None,
                'sort_order': sort_order
            }

    def _get_tarot_metadata_by_position(self, position: int, preset_name: str) -> dict:
        """Get Tarot metadata by numeric position (1-78)."""
        is_thoth = preset_name and 'thoth' in preset_name.lower()
        is_pre_golden_dawn = preset_name and 'pre-golden' in preset_name.lower()
        use_thoth_ordering = is_thoth or is_pre_golden_dawn

        # Major Arcana: positions 1-22 (or 0-21 depending on system)
        # We'll use 1-22 for Major, 23-78 for Minor (matching sort_order convention)
        if position <= 0 or position > 78:
            return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

        if position <= 22:
            # Major Arcana
            major_by_position = {
                1: ('The Fool', '0'),
                2: ('The Magician', 'I'),
                3: ('The High Priestess', 'II'),
                4: ('The Empress', 'III'),
                5: ('The Emperor', 'IV'),
                6: ('The Hierophant', 'V'),
                7: ('The Lovers', 'VI'),
                8: ('The Chariot', 'VII'),
            }
            # Canonical RWS archetype names (see note in _get_tarot_metadata).
            if use_thoth_ordering:
                major_by_position.update({
                    9: ('Justice', 'VIII'),
                    10: ('The Hermit', 'IX'),
                    11: ('Wheel of Fortune', 'X'),
                    12: ('Strength', 'XI'),
                })
            else:
                major_by_position.update({
                    9: ('Strength', 'VIII'),
                    10: ('The Hermit', 'IX'),
                    11: ('Wheel of Fortune', 'X'),
                    12: ('Justice', 'XI'),
                })
            major_by_position.update({
                13: ('The Hanged Man', 'XII'),
                14: ('Death', 'XIII'),
                15: ('Temperance', 'XIV'),
                16: ('The Devil', 'XV'),
                17: ('The Tower', 'XVI'),
                18: ('The Star', 'XVII'),
                19: ('The Moon', 'XVIII'),
                20: ('The Sun', 'XIX'),
                21: ('Judgement', 'XX'),
                22: ('The World', 'XXI'),
            })
            if position in major_by_position:
                name, rank = major_by_position[position]
                return {
                    'archetype': name,
                    'rank': rank,
                    'suit': 'Major Arcana',
                    'sort_order': position
                }

        # Minor Arcana: positions 23-78
        # 14 cards per suit: Ace-10 + Page/Knight/Queen/King
        minor_position = position - 22  # 1-56
        suit_index = (minor_position - 1) // 14  # 0-3
        card_in_suit = ((minor_position - 1) % 14) + 1  # 1-14

        suits = ['Wands', 'Cups', 'Swords', 'Pentacles']
        if is_thoth:
            suits[3] = 'Disks'

        if suit_index < 4:
            suit = suits[suit_index]
            if card_in_suit <= 10:
                # Pip cards
                ranks = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten']
                rank_name = ranks[card_in_suit - 1]
                return {
                    'archetype': f"{rank_name} of {suit}",
                    'rank': str(card_in_suit),
                    'suit': suit,
                    'sort_order': position
                }
            else:
                # Court cards (11-14)
                if is_thoth:
                    court_names = ['Princess', 'Prince', 'Queen', 'Knight']
                    verbose_ranks = [
                        'Page / Knave / Princess / Court Card 1',
                        'Knight / Prince / Court Card 2',
                        'Queen / Court Card 3',
                        'King / Knight (Thoth) / Court Card 4'
                    ]
                else:
                    court_names = ['Page', 'Knight', 'Queen', 'King']
                    verbose_ranks = [
                        'Page / Knave / Princess / Court Card 1',
                        'Knight / Prince / Court Card 2',
                        'Queen / Court Card 3',
                        'King / Court Card 4'
                    ]
                court_idx = card_in_suit - 11  # 0-3
                return {
                    'archetype': f"{court_names[court_idx]} of {suit}",
                    'rank': verbose_ranks[court_idx],
                    'suit': suit,
                    'sort_order': position
                }

        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_lenormand_metadata_by_position(self, position: int) -> dict:
        """Get Lenormand metadata by numeric position (1-36).

        Each Lenormand card has an associated playing card rank and suit.
        """
        # Format: (archetype, playing_card_rank, playing_card_suit)
        lenormand_cards = [
            ('Rider', '9', 'Hearts'),
            ('Clover', '6', 'Diamonds'),
            ('Ship', '10', 'Spades'),
            ('House', 'King', 'Hearts'),
            ('Tree', '7', 'Hearts'),
            ('Clouds', 'King', 'Clubs'),
            ('Snake', 'Queen', 'Clubs'),
            ('Coffin', '9', 'Diamonds'),
            ('Bouquet', 'Queen', 'Spades'),
            ('Scythe', 'Jack', 'Diamonds'),
            ('Whip', 'Jack', 'Clubs'),
            ('Birds', '7', 'Diamonds'),
            ('Child', 'Jack', 'Spades'),
            ('Fox', '9', 'Clubs'),
            ('Bear', '10', 'Clubs'),
            ('Stars', '6', 'Hearts'),
            ('Stork', 'Queen', 'Hearts'),
            ('Dog', '10', 'Hearts'),
            ('Tower', '6', 'Spades'),
            ('Garden', '8', 'Spades'),
            ('Mountain', '8', 'Clubs'),
            ('Crossroads', 'Queen', 'Diamonds'),
            ('Mice', '7', 'Clubs'),
            ('Heart', 'Jack', 'Hearts'),
            ('Ring', 'Ace', 'Clubs'),
            ('Book', '10', 'Diamonds'),
            ('Letter', '7', 'Spades'),
            ('Man', 'Ace', 'Hearts'),
            ('Woman', 'Ace', 'Spades'),
            ('Lily', 'King', 'Spades'),
            ('Sun', 'Ace', 'Diamonds'),
            ('Moon', '8', 'Hearts'),
            ('Key', '8', 'Diamonds'),
            ('Fish', 'King', 'Diamonds'),
            ('Anchor', '9', 'Spades'),
            ('Cross', '6', 'Clubs'),
        ]
        if 1 <= position <= 36:
            archetype, rank, suit = lenormand_cards[position - 1]
            return {
                'archetype': archetype,
                'rank': rank,
                'suit': suit,
                'sort_order': position
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_kipper_metadata_by_position(self, position: int) -> dict:
        """Get Kipper metadata by numeric position (1-36)."""
        kipper_cards = [
            'Main Male', 'Main Female', 'Marriage', 'Rendezvous', 'Good Gentleman',
            'Good Lady', 'Pleasant Letter', 'False Person', 'A Change', 'A Journey',
            'Lots of Money', 'Rich Girl', 'Rich Good Gentleman', 'Sad News',
            'Success in Love', 'His Thoughts', 'A Gift', 'A Small Child', 'A Funeral',
            'House', 'Living Room', 'Military Person', 'Court House', 'Theft',
            'High Honours', 'Great Fortune', 'Unexpected Money', 'Expectations',
            'Prison', 'Judiciary', 'Illness', 'Grief and Adversity', 'Gloomy Thoughts',
            'Occupation', 'A Long Way', 'Hope, Great Water'
        ]
        if 1 <= position <= 36:
            card_name = kipper_cards[position - 1]
            return {
                'archetype': card_name,
                'rank': str(position),
                'suit': None,
                'sort_order': position
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_playing_card_metadata_by_position(self, position: int) -> dict:
        """Get Playing Card metadata by numeric position (1-54)."""
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King']

        if 1 <= position <= 52:
            suit_idx = (position - 1) // 13
            rank_idx = (position - 1) % 13
            suit = suits[suit_idx]
            rank = ranks[rank_idx]
            return {
                'archetype': f"{rank} of {suit}",
                'rank': str(rank_idx + 1),
                'suit': suit,
                'sort_order': position
            }
        elif position == 53:
            return {'archetype': 'Red Joker', 'rank': '53', 'suit': 'Joker', 'sort_order': 53}
        elif position == 54:
            return {'archetype': 'Black Joker', 'rank': '54', 'suit': 'Joker', 'sort_order': 54}

        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_iching_metadata_by_position(self, position: int) -> dict:
        """Get I Ching hexagram metadata by numeric position (1-64).

        Returns metadata with:
        - archetype: English name (e.g., "The Creative")
        - rank: Hexagram number
        - suit: None (not used for I Ching)
        - custom_fields: dict with 'Hexagram', 'Pinyin', 'Simplified Chinese', 'Traditional Chinese'
        """
        # All 64 hexagrams: (unicode, simplified, traditional_if_different, pinyin, English)
        # Traditional is empty string if same as simplified
        hexagrams = [
            ('䷀', '乾', '', 'Qián', 'The Creative'),
            ('䷁', '坤', '', 'Kūn', 'The Receptive'),
            ('䷂', '屯', '', 'Zhūn', 'Difficulty at the Beginning'),
            ('䷃', '蒙', '', 'Méng', 'Youthful Folly'),
            ('䷄', '需', '', 'Xū', 'Waiting'),
            ('䷅', '讼', '訟', 'Sòng', 'Conflict'),
            ('䷆', '师', '師', 'Shī', 'The Army'),
            ('䷇', '比', '', 'Bǐ', 'Holding Together'),
            ('䷈', '小畜', '', 'Xiǎo Chù', 'Small Taming'),
            ('䷉', '履', '', 'Lǚ', 'Treading'),
            ('䷊', '泰', '', 'Tài', 'Peace'),
            ('䷋', '否', '', 'Pǐ', 'Standstill'),
            ('䷌', '同人', '', 'Tóng Rén', 'Fellowship'),
            ('䷍', '大有', '', 'Dà Yǒu', 'Great Possession'),
            ('䷎', '谦', '謙', 'Qiān', 'Modesty'),
            ('䷏', '豫', '', 'Yù', 'Enthusiasm'),
            ('䷐', '随', '隨', 'Suí', 'Following'),
            ('䷑', '蛊', '蠱', 'Gǔ', 'Work on the Decayed'),
            ('䷒', '临', '臨', 'Lín', 'Approach'),
            ('䷓', '观', '觀', 'Guān', 'Contemplation'),
            ('䷔', '噬嗑', '', 'Shì Kè', 'Biting Through'),
            ('䷕', '贲', '賁', 'Bì', 'Grace'),
            ('䷖', '剥', '剝', 'Bō', 'Splitting Apart'),
            ('䷗', '复', '復', 'Fù', 'Return'),
            ('䷘', '无妄', '無妄', 'Wú Wàng', 'Innocence'),
            ('䷙', '大畜', '', 'Dà Chù', 'Great Taming'),
            ('䷚', '颐', '頤', 'Yí', 'Nourishment'),
            ('䷛', '大过', '大過', 'Dà Guò', 'Great Excess'),
            ('䷜', '坎', '', 'Kǎn', 'The Abysmal'),
            ('䷝', '离', '離', 'Lí', 'The Clinging'),
            ('䷞', '咸', '', 'Xián', 'Influence'),
            ('䷟', '恒', '恆', 'Héng', 'Duration'),
            ('䷠', '遁', '遯', 'Dùn', 'Retreat'),
            ('䷡', '大壮', '大壯', 'Dà Zhuàng', 'Great Power'),
            ('䷢', '晋', '晉', 'Jìn', 'Progress'),
            ('䷣', '明夷', '', 'Míng Yí', 'Darkening of the Light'),
            ('䷤', '家人', '', 'Jiā Rén', 'The Family'),
            ('䷥', '睽', '', 'Kuí', 'Opposition'),
            ('䷦', '蹇', '', 'Jiǎn', 'Obstruction'),
            ('䷧', '解', '', 'Xiè', 'Deliverance'),
            ('䷨', '损', '損', 'Sǔn', 'Decrease'),
            ('䷩', '益', '', 'Yì', 'Increase'),
            ('䷪', '夬', '', 'Guài', 'Breakthrough'),
            ('䷫', '姤', '', 'Gòu', 'Coming to Meet'),
            ('䷬', '萃', '', 'Cuì', 'Gathering Together'),
            ('䷭', '升', '', 'Shēng', 'Pushing Upward'),
            ('䷮', '困', '', 'Kùn', 'Oppression'),
            ('䷯', '井', '', 'Jǐng', 'The Well'),
            ('䷰', '革', '', 'Gé', 'Revolution'),
            ('䷱', '鼎', '', 'Dǐng', 'The Cauldron'),
            ('䷲', '震', '', 'Zhèn', 'The Arousing'),
            ('䷳', '艮', '', 'Gèn', 'Keeping Still'),
            ('䷴', '渐', '漸', 'Jiàn', 'Development'),
            ('䷵', '归妹', '歸妹', 'Guī Mèi', 'The Marrying Maiden'),
            ('䷶', '丰', '豐', 'Fēng', 'Abundance'),
            ('䷷', '旅', '', 'Lǚ', 'The Wanderer'),
            ('䷸', '巽', '', 'Xùn', 'The Gentle'),
            ('䷹', '兑', '兌', 'Duì', 'The Joyous'),
            ('䷺', '涣', '渙', 'Huàn', 'Dispersion'),
            ('䷻', '节', '節', 'Jié', 'Limitation'),
            ('䷼', '中孚', '', 'Zhōng Fú', 'Inner Truth'),
            ('䷽', '小过', '小過', 'Xiǎo Guò', 'Small Excess'),
            ('䷾', '既济', '既濟', 'Jì Jì', 'After Completion'),
            ('䷿', '未济', '未濟', 'Wèi Jì', 'Before Completion'),
        ]
        if 1 <= position <= 64:
            unicode_char, simplified, traditional, pinyin, english = hexagrams[position - 1]
            return {
                'archetype': english,
                'rank': str(position),
                'suit': None,
                'sort_order': position,
                'custom_fields': {
                    'Hexagram': unicode_char,
                    'Pinyin': pinyin,
                    'Simplified Chinese': simplified,
                    'Traditional Chinese': traditional,
                }
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_tarot_metadata(self, card_name: str, sort_order: int, custom_suit_names: dict = None,
                            preset_name: str = None, custom_court_names: dict = None,
                            archetype_mapping: str = None) -> dict:
        """Get metadata for a Tarot card, respecting preset ordering and court customization.

        custom_court_names: dict with keys 'page', 'knight', 'queen', 'king' -> custom display names
        archetype_mapping: 'Map to RWS archetypes', 'Map to Thoth archetypes', or 'Create new archetypes'
        """
        name_lower = card_name.lower()

        # Handle Gnostic/Eternal Tarot - unique system with 78 numbered Arcana
        is_gnostic = preset_name and 'gnostic' in preset_name.lower()
        if is_gnostic:
            return self._get_gnostic_tarot_metadata(card_name, sort_order)

        # Grand Etteilla — a Tarot variant with the deck's own trump
        # names (Chaos, Hiram's Freemasonry, …, The Monarch), its own
        # suit naming (Sticks/Cups/Swords/Coins), and a King/Ace
        # ordering that differs from RWS. Same shape as the Gnostic
        # branch above: detect by preset name and route to the
        # Etteilla helper so the imported cards get the deck's
        # specific archetype + rank + suit metadata.
        is_etteilla = preset_name and 'etteilla' in preset_name.lower()
        if is_etteilla:
            return self._get_etteilla_metadata(card_name, sort_order)

        # Determine ordering based on preset
        # RWS ordering: Strength=VIII, Justice=XI
        # Pre-Golden Dawn / Thoth ordering: Justice/Adjustment=VIII, Strength/Lust=XI
        is_thoth = preset_name and 'thoth' in preset_name.lower()
        is_pre_golden_dawn = preset_name and 'pre-golden' in preset_name.lower()
        use_thoth_ordering = is_thoth or is_pre_golden_dawn

        # Major Arcana - combined RWS/Thoth archetypes where they differ
        # Format: (archetype, rank, suit)
        # Ranks for Strength/Lust and Justice/Adjustment depend on ordering
        if use_thoth_ordering:
            strength_rank = 'XI'
            justice_rank = 'VIII'
        else:
            strength_rank = 'VIII'
            justice_rank = 'XI'

        # Canonical RWS archetype names — the card_archetypes table stores the
        # RWS form ("The Magician", "Strength") even for cards displayed under
        # Thoth names. Display renaming happens at render time via the system's
        # naming_style.
        major_arcana_names = {
            'the fool': ('The Fool', '0', 'Major Arcana'),
            'fool': ('The Fool', '0', 'Major Arcana'),
            'the magician': ('The Magician', 'I', 'Major Arcana'),
            'magician': ('The Magician', 'I', 'Major Arcana'),
            'the magus': ('The Magician', 'I', 'Major Arcana'),
            'magus': ('The Magician', 'I', 'Major Arcana'),
            'the high priestess': ('The High Priestess', 'II', 'Major Arcana'),
            'high priestess': ('The High Priestess', 'II', 'Major Arcana'),
            'the priestess': ('The High Priestess', 'II', 'Major Arcana'),
            'priestess': ('The High Priestess', 'II', 'Major Arcana'),
            'the empress': ('The Empress', 'III', 'Major Arcana'),
            'empress': ('The Empress', 'III', 'Major Arcana'),
            'the emperor': ('The Emperor', 'IV', 'Major Arcana'),
            'emperor': ('The Emperor', 'IV', 'Major Arcana'),
            'the hierophant': ('The Hierophant', 'V', 'Major Arcana'),
            'hierophant': ('The Hierophant', 'V', 'Major Arcana'),
            'the lovers': ('The Lovers', 'VI', 'Major Arcana'),
            'lovers': ('The Lovers', 'VI', 'Major Arcana'),
            'the chariot': ('The Chariot', 'VII', 'Major Arcana'),
            'chariot': ('The Chariot', 'VII', 'Major Arcana'),
            'strength': ('Strength', strength_rank, 'Major Arcana'),
            'lust': ('Strength', strength_rank, 'Major Arcana'),
            'the hermit': ('The Hermit', 'IX', 'Major Arcana'),
            'hermit': ('The Hermit', 'IX', 'Major Arcana'),
            'wheel of fortune': ('Wheel of Fortune', 'X', 'Major Arcana'),
            'fortune': ('Wheel of Fortune', 'X', 'Major Arcana'),
            'the wheel': ('Wheel of Fortune', 'X', 'Major Arcana'),
            'wheel': ('Wheel of Fortune', 'X', 'Major Arcana'),
            'justice': ('Justice', justice_rank, 'Major Arcana'),
            'adjustment': ('Justice', justice_rank, 'Major Arcana'),
            'the hanged man': ('The Hanged Man', 'XII', 'Major Arcana'),
            'hanged man': ('The Hanged Man', 'XII', 'Major Arcana'),
            'death': ('Death', 'XIII', 'Major Arcana'),
            'temperance': ('Temperance', 'XIV', 'Major Arcana'),
            'art': ('Temperance', 'XIV', 'Major Arcana'),
            'the devil': ('The Devil', 'XV', 'Major Arcana'),
            'devil': ('The Devil', 'XV', 'Major Arcana'),
            'the tower': ('The Tower', 'XVI', 'Major Arcana'),
            'tower': ('The Tower', 'XVI', 'Major Arcana'),
            'the star': ('The Star', 'XVII', 'Major Arcana'),
            'star': ('The Star', 'XVII', 'Major Arcana'),
            'the moon': ('The Moon', 'XVIII', 'Major Arcana'),
            'moon': ('The Moon', 'XVIII', 'Major Arcana'),
            'the sun': ('The Sun', 'XIX', 'Major Arcana'),
            'sun': ('The Sun', 'XIX', 'Major Arcana'),
            'judgement': ('Judgement', 'XX', 'Major Arcana'),
            'judgment': ('Judgement', 'XX', 'Major Arcana'),
            'the aeon': ('Judgement', 'XX', 'Major Arcana'),
            'aeon': ('Judgement', 'XX', 'Major Arcana'),
            'the world': ('The World', 'XXI', 'Major Arcana'),
            'world': ('The World', 'XXI', 'Major Arcana'),
            'the universe': ('The World', 'XXI', 'Major Arcana'),
            'universe': ('The World', 'XXI', 'Major Arcana'),
        }

        if name_lower in major_arcana_names:
            archetype, rank, suit = major_arcana_names[name_lower]
            return {
                'archetype': archetype,
                'rank': rank,
                'suit': suit,
                'sort_order': sort_order
            }

        # Minor Arcana - parse "Rank of Suit" pattern
        # Build list of all court card names to recognize (standard + custom)
        # Map from display name (lowercase) -> (position, rank_name, sort_offset)
        # Position is for archetype mapping, rank_name is what goes in metadata,
        # sort_offset is added to suit base (11, 12, 13, 14)

        # Standard rank names for each court position (based on sort offset)
        # These encompass all common names for each position
        court_rank_by_position = {
            11: 'Page / Knave / Princess / Court Card 1',
            12: 'Knight / Prince / Court Card 2',
            13: 'Queen / Court Card 3',
            14: 'King / Knight (Thoth) / Court Card 4',
        }

        # For Thoth: Princess=11, Prince=12, Queen=13, Knight=14
        # For RWS/standard: Page=11, Knight=12, Queen=13, King=14
        if is_thoth:
            # Thoth court cards - these are their own archetypes
            # Also include RWS names mapped to Thoth equivalents for compatibility
            court_card_info = {
                'princess': ('princess', 11),
                'prince': ('prince', 12),
                'queen': ('queen', 13),
                'knight': ('knight', 14),  # Thoth Knight = King position
                # RWS names mapped to Thoth positions
                'page': ('princess', 11),      # Page -> Princess position
                'knave': ('princess', 11),
                'valet': ('princess', 11),
                'king': ('knight', 14),        # King -> Knight (Thoth) position
                'cavalier': ('prince', 12),    # Cavalier -> Prince position
            }
        else:
            # Standard/RWS court cards
            court_card_info = {
                'page': ('page', 11),
                'princess': ('page', 11),  # Maps to Page archetype
                'valet': ('page', 11),
                'knave': ('page', 11),
                'knight': ('knight', 12),
                'prince': ('knight', 12),  # Maps to Knight archetype
                'cavalier': ('knight', 12),
                'queen': ('queen', 13),
                'king': ('king', 14),
            }

        # Add custom court names if provided. The position values must match
        # the vocabulary used to initialize court_card_info above — Thoth uses
        # princess/prince/queen/knight as position keys, RWS uses page/knight/
        # queen/king. Mixing them corrupts the slot lookup downstream (e.g.
        # "Prince of Cups" would resolve to position='knight' and produce a
        # "Knight of Cups (Thoth)" archetype).
        if custom_court_names:
            if is_thoth:
                slot_positions = ('princess', 'prince', 'queen', 'knight')
            else:
                slot_positions = ('page', 'knight', 'queen', 'king')
            court_card_info[custom_court_names.get('page', '').lower()] = (slot_positions[0], 11)
            court_card_info[custom_court_names.get('knight', '').lower()] = (slot_positions[1], 12)
            court_card_info[custom_court_names.get('queen', '').lower()] = (slot_positions[2], 13)
            court_card_info[custom_court_names.get('king', '').lower()] = (slot_positions[3], 14)
            # Remove empty string key if any custom name was empty
            court_card_info.pop('', None)

        # Pip card ranks
        rank_names = {
            'ace': 'Ace', 'two': 'Two', 'three': 'Three', 'four': 'Four', 'five': 'Five',
            'six': 'Six', 'seven': 'Seven', 'eight': 'Eight', 'nine': 'Nine', 'ten': 'Ten',
        }

        suit_names = ['wands', 'cups', 'swords', 'pentacles', 'coins', 'disks']
        if custom_suit_names:
            suit_names.extend([v.lower() for v in custom_suit_names.values()])

        # Build reverse mapping from custom suit names to standard archetypes
        # e.g., 'earth' -> 'Pentacles', 'fire' -> 'Wands'
        # Disks/Coins always map to Pentacles for archetype consistency
        suit_to_archetype = {
            'wands': 'Wands', 'cups': 'Cups', 'swords': 'Swords', 'pentacles': 'Pentacles',
            'coins': 'Pentacles', 'disks': 'Pentacles',
        }
        if custom_suit_names:
            # Map custom names back to their standard archetype suits
            if 'wands' in custom_suit_names:
                suit_to_archetype[custom_suit_names['wands'].lower()] = 'Wands'
            if 'cups' in custom_suit_names:
                suit_to_archetype[custom_suit_names['cups'].lower()] = 'Cups'
            if 'swords' in custom_suit_names:
                suit_to_archetype[custom_suit_names['swords'].lower()] = 'Swords'
            if 'pentacles' in custom_suit_names:
                suit_to_archetype[custom_suit_names['pentacles'].lower()] = 'Pentacles'

        # Check for court cards first
        # Sort by court name length (descending) to match longer names first
        for court_name in sorted(court_card_info.keys(), key=len, reverse=True):
            position, sort_offset = court_card_info[court_name]
            for suit_name in suit_names:
                if f'{court_name} of {suit_name}' in name_lower:
                    # Map to standard archetype suit
                    archetype_suit = suit_to_archetype.get(suit_name, suit_name.title())

                    # Get the standard rank name based on sort position
                    rank_name = court_rank_by_position.get(sort_offset, court_name.title())

                    # Build archetype. For all decks (including Thoth) we emit
                    # the canonical RWS archetype name for the slot — that's
                    # what the seeded card_archetypes table contains, and it
                    # lets notes/correspondences attached to e.g. "Knight of
                    # Wands" automatically apply to a Thoth deck's slot-12
                    # card too. The card's display name (set elsewhere via
                    # _apply_custom_court_names) keeps the deck-specific
                    # label like "Prince of Wands".
                    if is_thoth:
                        rws_rank_for_thoth_position = {
                            'princess': 'Page',
                            'prince': 'Knight',
                            'queen': 'Queen',
                            'knight': 'King',
                        }
                        archetype_rank = rws_rank_for_thoth_position.get(
                            position, court_name.title()
                        )
                        archetype = f"{archetype_rank} of {archetype_suit}"
                    else:
                        archetype = self._get_court_archetype(
                            position, archetype_suit, court_name.title(), archetype_mapping
                        )

                    return {
                        'archetype': archetype,
                        'rank': rank_name,
                        'suit': archetype_suit,
                        'sort_order': sort_order
                    }

        # Check for pip cards
        for rank_key, rank_val in rank_names.items():
            for suit_name in suit_names:
                if f'{rank_key} of {suit_name}' in name_lower:
                    # Map to standard archetype suit
                    archetype_suit = suit_to_archetype.get(suit_name, suit_name.title())

                    archetype = f"{rank_val} of {archetype_suit}"

                    return {
                        'archetype': archetype,
                        'rank': rank_val,
                        'suit': archetype_suit,
                        'sort_order': sort_order
                    }

        # Unknown card
        return {
            'archetype': None,
            'rank': None,
            'suit': None,
            'sort_order': sort_order
        }

    def _get_court_archetype(self, base_position: str, suit: str, display_rank: str,
                             archetype_mapping: str = None) -> str:
        """Determine the archetype for a court card based on mapping option.

        base_position: 'page', 'knight', 'queen', or 'king'
        suit: The normalized suit name (e.g., 'Wands')
        display_rank: The actual rank name displayed on the card (e.g., 'Princess')
        archetype_mapping: 'Map to RWS archetypes', 'Map to Thoth archetypes', or 'Create new archetypes'
        """
        if archetype_mapping == 'Map to RWS archetypes':
            # Map to standard RWS names: Page, Knight, Queen, King
            archetype_rank = RWS_COURT_ARCHETYPES.get(base_position, display_rank)
        elif archetype_mapping == 'Map to Thoth archetypes':
            # Map to Thoth names: Princess, Prince, Queen, Knight
            archetype_rank = THOTH_COURT_ARCHETYPES.get(base_position, display_rank)
        else:
            # Create new archetypes - use the display name as-is
            archetype_rank = display_rank

        return f"{archetype_rank} of {suit}"

    def _apply_custom_court_names(self, card_name: str, custom_court_names: dict,
                                   preset_name: str = None) -> str:
        """Replace standard court card names with custom ones in a card name.

        custom_court_names: dict with keys 'page', 'knight', 'queen', 'king'
        preset_name: needed because the same word ("Knight") means different slots
            depending on the source vocabulary — slot 12 in RWS, slot 14 in Thoth.
        """
        if not custom_court_names:
            return card_name

        is_thoth = preset_name and 'thoth' in preset_name.lower()

        # The input card name uses one of three court-rank vocabularies. Each
        # vocabulary maps its rank words to slot keys differently — most
        # importantly, "Knight" is slot 12 in RWS but slot 14 in Thoth.
        if is_thoth:
            standard_to_position = {
                'Princess': 'page',
                'Prince': 'knight',
                'Queen': 'queen',
                'Knight': 'king',
            }
        else:
            standard_to_position = {
                'Page': 'page', 'Princess': 'page', 'Valet': 'page',
                'Knight': 'knight', 'Prince': 'knight', 'Cavalier': 'knight',
                'Queen': 'queen',
                'King': 'king',
            }

        for standard_name, position in standard_to_position.items():
            if f'{standard_name} of ' in card_name:
                custom_name = custom_court_names.get(position)
                if custom_name and custom_name != standard_name:
                    return card_name.replace(f'{standard_name} of ', f'{custom_name} of ')

        return card_name

    def _get_gnostic_tarot_metadata(self, card_name: str, sort_order: int) -> dict:
        """Get metadata for a Gnostic/Eternal Tarot card.

        The Gnostic system has 78 Arcana numbered 1-78, each with a unique name.
        - Arcana 1-22: Major Arcana equivalent
        - Arcana 23-78: Minor Arcana equivalent (no suits, unique names)

        Metadata is assigned by sort_order (1-78).
        """
        # All 78 Arcana with their names
        gnostic_arcana = {
            1: "The Magician",
            2: "The Priestess",
            3: "The Empress",
            4: "The Emperor",
            5: "The Hierarch",
            6: "Indecision",
            7: "Triumph",
            8: "Justice",
            9: "The Hermit",
            10: "Retribution",
            11: "Persuasion",
            12: "The Apostolate",
            13: "Immortality",
            14: "Temperance",
            15: "Passion",
            16: "Fragility",
            17: "Hope",
            18: "Twilight",
            19: "Inspiration",
            20: "Resurrection",
            21: "Transmutation",
            22: "The Return",
            23: "The Plower",
            24: "The Weaver",
            25: "The Argonaut",
            26: "The Prodigy",
            27: "The Unexpected",
            28: "Uncertainty",
            29: "Domesticity",
            30: "Exchange",
            31: "Impediments",
            32: "Magnificence",
            33: "Alliance",
            34: "Innovation",
            35: "Grief",
            36: "Initiation",
            37: "Art and Science",
            38: "Duplicity",
            39: "Testimony",
            40: "Presentiment",
            41: "Uneasiness",
            42: "Preeminence",
            43: "Hallucination",
            44: "Thinking",
            45: "Regeneration",
            46: "Patrimony",
            47: "Conjecturing",
            48: "Consummation",
            49: "Versatility",
            50: "Affinity",
            51: "Counseling",
            52: "Premeditation",
            53: "Resentment",
            54: "Examination",
            55: "Contrition",
            56: "Pilgrimage",
            57: "Rivalry",
            58: "Requalification",
            59: "Revelation",
            60: "Evolution",
            61: "Solitude",
            62: "Proscription",
            63: "Communion",
            64: "Vehemence",
            65: "Learning",
            66: "Perplexity",
            67: "Friendship",
            68: "Speculation",
            69: "Chance",
            70: "Cooperation",
            71: "Avarice",
            72: "Purification",
            73: "Love and Desire",
            74: "Offering",
            75: "Generosity",
            76: "The Dispenser",
            77: "Disorientation",
            78: "Renaissance",
        }

        # Try to determine arcanum number from sort_order or card name
        arcanum_num = None

        # If sort_order is valid (1-78), use it
        if 1 <= sort_order <= 78:
            arcanum_num = sort_order
        else:
            # Try to extract number from card name (e.g., "Arcanum 23: The Plower" or just "23")
            import re
            match = re.search(r'(?:arcanum\s*)?(\d+)', card_name.lower())
            if match:
                num = int(match.group(1))
                if 1 <= num <= 78:
                    arcanum_num = num

        if arcanum_num and arcanum_num in gnostic_arcana:
            archetype = gnostic_arcana[arcanum_num]
            # Determine card type
            if arcanum_num <= 22:
                card_type = "Major Arcana"
            else:
                card_type = "Minor Arcana"

            return {
                'archetype': archetype,
                'rank': str(arcanum_num),
                'suit': card_type,
                'sort_order': arcanum_num
            }

        # Fallback - return basic info
        return {
            'archetype': card_name,
            'rank': str(sort_order) if sort_order else None,
            'suit': None,
            'sort_order': sort_order
        }

    def _get_grand_lenormand_metadata(self, card_name: str, sort_order: int) -> dict:
        """Get metadata for a Grand Lenormand (54-card) card.

        Sort order follows suit order: Clubs 1-13, Diamonds 14-26, Spades 27-39,
        Hearts 40-52, Man Consultant 53, Woman Consultant 54.
        """
        # Grand Lenormand cards: (archetype, sort_order, rank, suit)
        grand_lenormand_cards = {
            # Clubs (1-13)
            'ace of clubs': ('Ace of Clubs', 1, 'Ace', 'Clubs'),
            '2 of clubs': ('2 of Clubs', 2, '2', 'Clubs'),
            '3 of clubs': ('3 of Clubs', 3, '3', 'Clubs'),
            '4 of clubs': ('4 of Clubs', 4, '4', 'Clubs'),
            '5 of clubs': ('5 of Clubs', 5, '5', 'Clubs'),
            '6 of clubs': ('6 of Clubs', 6, '6', 'Clubs'),
            '7 of clubs': ('7 of Clubs', 7, '7', 'Clubs'),
            '8 of clubs': ('8 of Clubs', 8, '8', 'Clubs'),
            '9 of clubs': ('9 of Clubs', 9, '9', 'Clubs'),
            '10 of clubs': ('10 of Clubs', 10, '10', 'Clubs'),
            'jack of clubs': ('Jack of Clubs', 11, 'Jack', 'Clubs'),
            'queen of clubs': ('Queen of Clubs', 12, 'Queen', 'Clubs'),
            'king of clubs': ('King of Clubs', 13, 'King', 'Clubs'),
            # Diamonds (14-26)
            'ace of diamonds': ('Ace of Diamonds', 14, 'Ace', 'Diamonds'),
            '2 of diamonds': ('2 of Diamonds', 15, '2', 'Diamonds'),
            '3 of diamonds': ('3 of Diamonds', 16, '3', 'Diamonds'),
            '4 of diamonds': ('4 of Diamonds', 17, '4', 'Diamonds'),
            '5 of diamonds': ('5 of Diamonds', 18, '5', 'Diamonds'),
            '6 of diamonds': ('6 of Diamonds', 19, '6', 'Diamonds'),
            '7 of diamonds': ('7 of Diamonds', 20, '7', 'Diamonds'),
            '8 of diamonds': ('8 of Diamonds', 21, '8', 'Diamonds'),
            '9 of diamonds': ('9 of Diamonds', 22, '9', 'Diamonds'),
            '10 of diamonds': ('10 of Diamonds', 23, '10', 'Diamonds'),
            'jack of diamonds': ('Jack of Diamonds', 24, 'Jack', 'Diamonds'),
            'queen of diamonds': ('Queen of Diamonds', 25, 'Queen', 'Diamonds'),
            'king of diamonds': ('King of Diamonds', 26, 'King', 'Diamonds'),
            # Spades (27-39)
            'ace of spades': ('Ace of Spades', 27, 'Ace', 'Spades'),
            '2 of spades': ('2 of Spades', 28, '2', 'Spades'),
            '3 of spades': ('3 of Spades', 29, '3', 'Spades'),
            '4 of spades': ('4 of Spades', 30, '4', 'Spades'),
            '5 of spades': ('5 of Spades', 31, '5', 'Spades'),
            '6 of spades': ('6 of Spades', 32, '6', 'Spades'),
            '7 of spades': ('7 of Spades', 33, '7', 'Spades'),
            '8 of spades': ('8 of Spades', 34, '8', 'Spades'),
            '9 of spades': ('9 of Spades', 35, '9', 'Spades'),
            '10 of spades': ('10 of Spades', 36, '10', 'Spades'),
            'jack of spades': ('Jack of Spades', 37, 'Jack', 'Spades'),
            'queen of spades': ('Queen of Spades', 38, 'Queen', 'Spades'),
            'king of spades': ('King of Spades', 39, 'King', 'Spades'),
            # Hearts (40-52)
            'ace of hearts': ('Ace of Hearts', 40, 'Ace', 'Hearts'),
            '2 of hearts': ('2 of Hearts', 41, '2', 'Hearts'),
            '3 of hearts': ('3 of Hearts', 42, '3', 'Hearts'),
            '4 of hearts': ('4 of Hearts', 43, '4', 'Hearts'),
            '5 of hearts': ('5 of Hearts', 44, '5', 'Hearts'),
            '6 of hearts': ('6 of Hearts', 45, '6', 'Hearts'),
            '7 of hearts': ('7 of Hearts', 46, '7', 'Hearts'),
            '8 of hearts': ('8 of Hearts', 47, '8', 'Hearts'),
            '9 of hearts': ('9 of Hearts', 48, '9', 'Hearts'),
            '10 of hearts': ('10 of Hearts', 49, '10', 'Hearts'),
            'jack of hearts': ('Jack of Hearts', 50, 'Jack', 'Hearts'),
            'queen of hearts': ('Queen of Hearts', 51, 'Queen', 'Hearts'),
            'king of hearts': ('King of Hearts', 52, 'King', 'Hearts'),
            # Consultants (53-54)
            'man (consultant)': ('Man (Consultant)', 53, 'Consultant', None),
            'woman (consultant)': ('Woman (Consultant)', 54, 'Consultant', None),
        }

        name_lower = card_name.lower()
        # Sort by key length descending so "woman (consultant)" matches before "man (consultant)"
        sorted_items = sorted(grand_lenormand_cards.items(), key=lambda x: len(x[0]), reverse=True)
        for key, (archetype, card_number, rank, suit) in sorted_items:
            if key in name_lower:
                return {
                    'archetype': archetype,
                    'rank': rank,
                    'suit': suit,
                    'sort_order': card_number
                }

        return {
            'archetype': None,
            'rank': None,
            'suit': None,
            'sort_order': sort_order
        }

    def _get_lenormand_metadata(self, card_name: str, sort_order: int) -> dict:
        """Get metadata for a Lenormand card.

        Each Lenormand card has:
        - archetype: the card name (Rider, Clover, etc.)
        - card_number: 1-36, used for sort_order
        - rank: the playing card rank (6, 7, 8, 9, 10, Jack, Queen, King, Ace)
        - suit: the playing card suit (Hearts, Diamonds, Clubs, Spades)
        """
        # Lenormand cards with their number, playing card rank, and suit
        # Format: 'keyword': (archetype, card_number, rank, suit)
        lenormand_cards = {
            'rider': ('Rider', 1, '9', 'Hearts'),
            'clover': ('Clover', 2, '6', 'Diamonds'),
            'ship': ('Ship', 3, '10', 'Spades'),
            'house': ('House', 4, 'King', 'Hearts'),
            'tree': ('Tree', 5, '7', 'Hearts'),
            'clouds': ('Clouds', 6, 'King', 'Clubs'),
            'snake': ('Snake', 7, 'Queen', 'Clubs'),
            'coffin': ('Coffin', 8, '9', 'Diamonds'),
            'bouquet': ('Bouquet', 9, 'Queen', 'Spades'),
            'flowers': ('Bouquet', 9, 'Queen', 'Spades'),
            'scythe': ('Scythe', 10, 'Jack', 'Diamonds'),
            'whip': ('Whip', 11, 'Jack', 'Clubs'),
            'broom': ('Whip', 11, 'Jack', 'Clubs'),
            'birds': ('Birds', 12, '7', 'Diamonds'),
            'owls': ('Birds', 12, '7', 'Diamonds'),
            'child': ('Child', 13, 'Jack', 'Spades'),
            'fox': ('Fox', 14, '9', 'Clubs'),
            'bear': ('Bear', 15, '10', 'Clubs'),
            'stars': ('Stars', 16, '6', 'Hearts'),
            'stork': ('Stork', 17, 'Queen', 'Hearts'),
            'dog': ('Dog', 18, '10', 'Hearts'),
            'tower': ('Tower', 19, '6', 'Spades'),
            'garden': ('Garden', 20, '8', 'Spades'),
            'mountain': ('Mountain', 21, '8', 'Clubs'),
            'crossroads': ('Crossroads', 22, 'Queen', 'Diamonds'),
            'paths': ('Crossroads', 22, 'Queen', 'Diamonds'),
            'mice': ('Mice', 23, '7', 'Clubs'),
            'heart': ('Heart', 24, 'Jack', 'Hearts'),
            'ring': ('Ring', 25, 'Ace', 'Clubs'),
            'book': ('Book', 26, '10', 'Diamonds'),
            'letter': ('Letter', 27, '7', 'Spades'),
            'man': ('Man', 28, 'Ace', 'Hearts'),
            'gentleman': ('Man', 28, 'Ace', 'Hearts'),
            'woman': ('Woman', 29, 'Ace', 'Spades'),
            'lady': ('Woman', 29, 'Ace', 'Spades'),
            'lily': ('Lily', 30, 'King', 'Spades'),
            'lilies': ('Lily', 30, 'King', 'Spades'),
            'sun': ('Sun', 31, 'Ace', 'Diamonds'),
            'moon': ('Moon', 32, '8', 'Hearts'),
            'key': ('Key', 33, '8', 'Diamonds'),
            'fish': ('Fish', 34, 'King', 'Diamonds'),
            'anchor': ('Anchor', 35, '9', 'Spades'),
            'cross': ('Cross', 36, '6', 'Clubs'),
        }

        name_lower = card_name.lower()
        # Sort by key length descending to match longer/more specific keys first
        # (e.g., 'woman' before 'man', 'gentleman' before 'man')
        sorted_items = sorted(lenormand_cards.items(), key=lambda x: len(x[0]), reverse=True)
        for key, (archetype, card_number, rank, suit) in sorted_items:
            if key in name_lower:
                return {
                    'archetype': archetype,
                    'rank': rank,
                    'suit': suit,
                    'sort_order': card_number
                }

        return {
            'archetype': None,
            'rank': None,
            'suit': None,
            'sort_order': sort_order
        }

    def _get_kipper_metadata(self, card_name: str, sort_order: int) -> dict:
        """Get metadata for a Kipper card.

        Kipper cards have numbers 1-36 but no playing card associations.
        The card number is used for sort_order, not rank.
        """
        # Format: 'keyword': (archetype, card_number)
        kipper_cards = {
            'main male': ('Main Male', 1), 'hauptperson': ('Main Male', 1),
            'main female': ('Main Female', 2),
            'marriage': ('Marriage', 3), 'union': ('Marriage', 3),
            'meeting': ('Meeting', 4), 'rendezvous': ('Meeting', 4),
            'good gentleman': ('Good Gentleman', 5), 'good man': ('Good Gentleman', 5),
            'good lady': ('Good Lady', 6), 'good woman': ('Good Lady', 6),
            'pleasant letter': ('Pleasant Letter', 7), 'good news': ('Pleasant Letter', 7),
            'false person': ('False Person', 8), 'falsity': ('False Person', 8),
            'a change': ('A Change', 9), 'change': ('A Change', 9),
            'a journey': ('A Journey', 10), 'journey': ('A Journey', 10), 'travel': ('A Journey', 10),
            'gain money': ('Gain Money', 11), 'win money': ('Gain Money', 11), 'wealth': ('Gain Money', 11),
            'rich girl': ('Rich Girl', 12), 'wealthy girl': ('Rich Girl', 12),
            'rich man': ('Rich Man', 13), 'wealthy man': ('Rich Man', 13),
            'sad news': ('Sad News', 14), 'bad news': ('Sad News', 14),
            'success in love': ('Success in Love', 15), 'love success': ('Success in Love', 15),
            'his thoughts': ('His Thoughts', 16), 'her thoughts': ('His Thoughts', 16), 'thoughts': ('His Thoughts', 16),
            'a gift': ('A Gift', 17), 'gift': ('A Gift', 17), 'present': ('A Gift', 17),
            'a small child': ('A Small Child', 18), 'small child': ('A Small Child', 18), 'child': ('A Small Child', 18),
            'a funeral': ('A Funeral', 19), 'funeral': ('A Funeral', 19), 'death': ('A Funeral', 19),
            'house': ('House', 20), 'home': ('House', 20),
            'living room': ('Living Room', 21), 'parlor': ('Living Room', 21), 'room': ('Living Room', 21),
            'official person': ('Official Person', 22), 'military': ('Official Person', 22), 'official': ('Official Person', 22),
            'court house': ('Court House', 23), 'courthouse': ('Court House', 23),
            'theft': ('Theft', 24), 'thief': ('Theft', 24), 'stealing': ('Theft', 24),
            'high honors': ('High Honors', 25), 'honor': ('High Honors', 25), 'achievement': ('High Honors', 25),
            'great fortune': ('Great Fortune', 26), 'fortune': ('Great Fortune', 26), 'luck': ('Great Fortune', 26),
            'unexpected money': ('Unexpected Money', 27), 'surprise': ('Unexpected Money', 27),
            'expectation': ('Expectation', 28), 'hope': ('Expectation', 28), 'waiting': ('Expectation', 28),
            'prison': ('Prison', 29), 'confinement': ('Prison', 29), 'jail': ('Prison', 29),
            'court': ('Court', 30), 'legal': ('Court', 30), 'judge': ('Court', 30), 'judiciary': ('Court', 30),
            'short illness': ('Short Illness', 31), 'illness': ('Short Illness', 31), 'sickness': ('Short Illness', 31),
            'grief and adversity': ('Grief and Adversity', 32), 'grief': ('Grief and Adversity', 32), 'adversity': ('Grief and Adversity', 32), 'sorrow': ('Grief and Adversity', 32),
            'gloomy thoughts': ('Gloomy Thoughts', 33), 'sadness': ('Gloomy Thoughts', 33), 'melancholy': ('Gloomy Thoughts', 33),
            'work': ('Work', 34), 'employment': ('Work', 34), 'occupation': ('Work', 34), 'labor': ('Work', 34),
            'a long way': ('A Long Way', 35), 'long way': ('A Long Way', 35), 'long road': ('A Long Way', 35), 'distance': ('A Long Way', 35),
            'hope, great water': ('Hope, Great Water', 36), 'great water': ('Hope, Great Water', 36), 'water': ('Hope, Great Water', 36), 'ocean': ('Hope, Great Water', 36),
        }

        name_lower = card_name.lower()
        # Sort by key length descending to match longer/more specific keys first
        sorted_items = sorted(kipper_cards.items(), key=lambda x: len(x[0]), reverse=True)
        for key, (archetype, card_number) in sorted_items:
            if key in name_lower:
                return {
                    'archetype': archetype,
                    'rank': None,
                    'suit': None,
                    'sort_order': card_number
                }

        return {
            'archetype': None,
            'rank': None,
            'suit': None,
            'sort_order': sort_order
        }

    def _get_playing_card_metadata(self, card_name: str, sort_order: int) -> dict:
        """Get metadata for a Playing Card"""
        name_lower = card_name.lower()

        # Jokers
        if 'joker' in name_lower:
            if 'red' in name_lower:
                return {'archetype': 'Red Joker', 'rank': 'Joker', 'suit': None, 'sort_order': sort_order}
            elif 'black' in name_lower:
                return {'archetype': 'Black Joker', 'rank': 'Joker', 'suit': None, 'sort_order': sort_order}
            else:
                return {'archetype': 'Joker', 'rank': 'Joker', 'suit': None, 'sort_order': sort_order}

        # Rank names - both word and numeric forms
        rank_names = {
            'ace': 'Ace', 'a': 'Ace',
            'two': 'Two', '2': 'Two',
            'three': 'Three', '3': 'Three',
            'four': 'Four', '4': 'Four',
            'five': 'Five', '5': 'Five',
            'six': 'Six', '6': 'Six',
            'seven': 'Seven', '7': 'Seven',
            'eight': 'Eight', '8': 'Eight',
            'nine': 'Nine', '9': 'Nine',
            'ten': 'Ten', '10': 'Ten',
            'jack': 'Jack', 'j': 'Jack',
            'queen': 'Queen', 'q': 'Queen',
            'king': 'King', 'k': 'King',
        }

        suit_names = ['hearts', 'diamonds', 'clubs', 'spades']

        for rank_key, rank_val in rank_names.items():
            for suit_name in suit_names:
                if f'{rank_key} of {suit_name}' in name_lower:
                    archetype = f"{rank_val} of {suit_name.title()}"
                    return {
                        'archetype': archetype,
                        'rank': rank_val,
                        'suit': suit_name.title(),
                        'sort_order': sort_order
                    }

        return {
            'archetype': None,
            'rank': None,
            'suit': None,
            'sort_order': sort_order
        }

    # Trigram data: (unicode, simplified, pinyin, english)
    _TRIGRAMS = [
        ('☰', '乾', 'Qián', 'Heaven'),
        ('☷', '坤', 'Kūn', 'Earth'),
        ('☳', '震', 'Zhèn', 'Thunder'),
        ('☵', '坎', 'Kǎn', 'Water'),
        ('☶', '艮', 'Gèn', 'Mountain'),
        ('☴', '巽', 'Xùn', 'Wind'),
        ('☲', '离', 'Lí', 'Fire'),
        ('☱', '兑', 'Duì', 'Lake'),
    ]

    def _get_trigram_metadata(self, trigram_num: int) -> dict:
        """Get metadata for a trigram (1-8). Sort order is 65-72 (after hexagrams)."""
        if 1 <= trigram_num <= 8:
            unicode_char, simplified, pinyin, english = self._TRIGRAMS[trigram_num - 1]
            return {
                'archetype': f"{english} ({pinyin})",
                'rank': str(trigram_num),
                'suit': 'Trigram',
                'sort_order': 64 + trigram_num,
                'custom_fields': {
                    'Trigram': unicode_char,
                    'Pinyin': pinyin,
                    'Simplified Chinese': simplified,
                    'Traditional Chinese': simplified,
                }
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': 999}

    def _get_iching_metadata(self, card_name: str, sort_order: int) -> dict:
        """Get metadata for an I Ching hexagram or trigram.

        Tries to parse hexagram/trigram number from card name, falls back to sort_order.
        """
        name_lower = card_name.lower().strip()

        # Check for trigram names (mapped from t1-t8 filenames)
        trigram_keywords = {
            'heaven (qián)': 1, 'earth (kūn)': 2, 'thunder (zhèn)': 3,
            'water (kǎn)': 4, 'mountain (gèn)': 5, 'wind (xùn)': 6,
            'fire (lí)': 7, 'lake (duì)': 8,
        }
        for keyword, tri_num in trigram_keywords.items():
            if keyword in name_lower:
                return self._get_trigram_metadata(tri_num)

        # Try to extract hexagram number from the card name
        # Match patterns like "Hexagram 1", "1.", "01", "01_the_creative", etc.
        # First try at the start of the name
        match = re.match(r'^(?:hexagram\s*)?(\d+)', name_lower)
        if match:
            hex_num = int(match.group(1))
            if 1 <= hex_num <= 64:
                return self._get_iching_metadata_by_position(hex_num)

        # Try to find any number in the name (e.g., from filename like "hexagram_01.jpg")
        all_numbers = re.findall(r'(\d+)', name_lower)
        for num_str in all_numbers:
            hex_num = int(num_str)
            if 1 <= hex_num <= 64:
                return self._get_iching_metadata_by_position(hex_num)

        # Fall back to position-based
        return self._get_iching_metadata_by_position(sort_order)

    def _get_oracle_metadata(self, card_name: str, sort_order: int) -> dict:
        """Get metadata for an Oracle card.

        If the card name starts with a number, use that as the sort order.
        Oracle cards don't have standard archetypes, ranks, or suits.
        """
        # Try to extract a leading number from the card name for sort order
        match = re.match(r'^(\d+)', card_name.strip())
        if match:
            sort_order = int(match.group(1))

        return {
            'archetype': None,
            'rank': None,
            'suit': None,
            'sort_order': sort_order
        }

    def _get_regional_metadata(self, card_name: str, sort_order: int,
                               preset_name: str = None) -> dict:
        """Metadata for a Latin- or German-suited pack card ("Sota de
        Copas" -> Knave of Cups). Custom presets of these types fall
        back to any built-in pack that knows the name."""
        packs = ([REGIONAL_PACKS[preset_name]] if preset_name in REGIONAL_PACKS
                 else REGIONAL_PACKS.values())
        for _mappings, meta in packs:
            if card_name in meta:
                return dict(meta[card_name])
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': sort_order}

    def _get_belline_metadata(self, card_name: str, sort_order: int) -> dict:
        """Metadata for an Oracle Belline card. Position (1-53) is the
        rank since the deck isn't suited."""
        pos = BELLINE_NAME_TO_POS.get(card_name, sort_order)
        return {
            'archetype': card_name,
            'rank': str(pos),
            'suit': None,
            'sort_order': pos,
        }

    def _get_sibilla_metadata(self, card_name: str, sort_order: int) -> dict:
        """Metadata for a Vera Sibilla Italiana card. Each divinatory
        name resolves to a (rank, suit) on the underlying playing-card
        position — used when the deck's art surfaces the playing-card
        inset (Vera Sibilla). The Zingara variant uses
        _get_sibilla_zingara_metadata below to skip the rank/suit."""
        rsp = SIBILLA_NAME_TO_RSP.get(card_name)
        if rsp:
            rank, suit, pos = rsp
            return {
                'archetype': card_name,
                'rank': rank,
                'suit': suit,
                'sort_order': pos,
            }
        return {'archetype': card_name, 'rank': None, 'suit': None, 'sort_order': sort_order}

    def _get_sibilla_zingara_metadata(self, card_name: str, sort_order: int) -> dict:
        """Sibilla della Zingara variant — same archetype names, same
        sort order, but the imported card row gets no playing-card
        rank/suit. The shared archetype's own rank/suit (seeded on
        card_archetypes) is unaffected; this only controls what
        lands on the card row in the cards table."""
        rsp = SIBILLA_NAME_TO_RSP.get(card_name)
        if rsp:
            _rank, _suit, pos = rsp
            return {
                'archetype': card_name,
                'rank': None,
                'suit': None,
                'sort_order': pos,
            }
        return {'archetype': card_name, 'rank': None, 'suit': None, 'sort_order': sort_order}

    def _get_regional_metadata_by_position(self, position: int, preset_name: str) -> dict:
        _mappings, meta = REGIONAL_PACKS.get(
            preset_name, REGIONAL_PACKS['Spanish Playing Cards (50 cards)'])
        for m in meta.values():
            if m['sort_order'] == position:
                return dict(m)
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_belline_metadata_by_position(self, position: int) -> dict:
        if 1 <= position <= len(BELLINE_NAMES):
            name = BELLINE_NAMES[position - 1]
            return {
                'archetype': name,
                'rank': str(position),
                'suit': None,
                'sort_order': position,
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_sibilla_metadata_by_position(self, position: int) -> dict:
        if 1 <= position <= 52:
            suit_idx = (position - 1) // 13
            rank_idx = (position - 1) % 13
            _suit_letter, suit_name = SIBILLA_SUITS[suit_idx]
            name = SIBILLA_BY_SUIT[suit_name][rank_idx]
            rank_word = SIBILLA_RANK_WORDS[rank_idx]
            return {
                'archetype': name,
                'rank': rank_word,
                'suit': suit_name,
                'sort_order': position,
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_sibilla_zingara_metadata_by_position(self, position: int) -> dict:
        """Same lookup as `_get_sibilla_metadata_by_position` for the
        archetype name, but drops the rank/suit tags."""
        if 1 <= position <= 52:
            suit_idx = (position - 1) // 13
            rank_idx = (position - 1) % 13
            _suit_letter, suit_name = SIBILLA_SUITS[suit_idx]
            name = SIBILLA_BY_SUIT[suit_name][rank_idx]
            return {
                'archetype': name,
                'rank': None,
                'suit': None,
                'sort_order': position,
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_sibylle_salons_metadata(self, card_name: str, sort_order: int) -> dict:
        """Metadata for a Sibylle des Salons / Sibilla Indovina card.
        Each divinatory name resolves to a (rank, suit) on the
        underlying playing card. Suits go Clubs → Diamonds → Hearts →
        Spades, each suit ordered King → Ace, so the deck's global
        1-52 positions match position 1 = King of Clubs =
        "Protector" through position 52 = Ace of Spades = "Delay"."""
        rsp = SIBYLLE_SALONS_NAME_TO_RSP.get(card_name)
        if rsp:
            rank, suit, pos = rsp
            return {
                'archetype': card_name,
                'rank': rank,
                'suit': suit,
                'sort_order': pos,
            }
        return {'archetype': card_name, 'rank': None, 'suit': None, 'sort_order': sort_order}

    def _get_sibylle_salons_metadata_by_position(self, position: int) -> dict:
        """Position 1-52 → archetype based on the Sibylle des Salons'
        K→A ordering. Position 1 is King of Clubs ("Protector"),
        position 14 is King of Diamonds ("Soldier"), etc."""
        if 1 <= position <= 52:
            suit_idx = (position - 1) // 13
            within_idx = (position - 1) % 13
            _suit_letter, suit_name = SIBYLLE_SALONS_SUITS[suit_idx]
            name = SIBYLLE_SALONS_BY_SUIT[suit_name][within_idx]
            rank_word = SIBYLLE_SALONS_RANK_WORDS[within_idx]
            return {
                'archetype': name,
                'rank': rank_word,
                'suit': suit_name,
                'sort_order': position,
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_etteilla_metadata(self, card_name: str, sort_order: int) -> dict:
        """Metadata for a Grand Etteilla card. The LWB position 1-78
        is the sort order; rank is the trump number (1-22) for trumps
        and the suit-rank (Queen/Knight/Knave/Ten/.../Ace/King) for
        minors. Suit is 'Major Arcana' for trumps and Sticks/Cups/
        Swords/Coins for minors."""
        prs = ETTEILLA_NAME_TO_PRS.get(card_name)
        if prs:
            pos, rank, suit = prs
            return {
                'archetype': card_name,
                'rank': rank,
                'suit': suit,
                'sort_order': pos,
            }
        return {'archetype': card_name, 'rank': None, 'suit': None, 'sort_order': sort_order}

    def _get_etteilla_metadata_by_position(self, position: int) -> dict:
        if 1 <= position <= 22:
            name = ETTEILLA_TRUMPS[position - 1]
            return {
                'archetype': name,
                'rank': str(position),
                'suit': 'Major Arcana',
                'sort_order': position,
            }
        if 23 <= position <= 78:
            pos, name, rank, suit = ETTEILLA_MINORS[position - 23]
            return {
                'archetype': name,
                'rank': rank,
                'suit': suit,
                'sort_order': pos,
            }
        return {'archetype': None, 'rank': None, 'suit': None, 'sort_order': position}

    def _get_card_sort_order(self, card_name: str, custom_suit_names: dict = None,
                             preset_name: str = None, custom_court_names: dict = None) -> int:
        """Get sort order: Major Arcana (0-21), then Wands, Cups, Swords, Pentacles for Tarot.
        For Playing Cards: Jokers (1-2), then Spades=1xx, Hearts=2xx, Clubs=3xx, Diamonds=4xx.
        For I Ching: Hexagram number (1-64).
        Respects preset ordering for Strength/Justice swap.

        Court cards are always ordered: first court=11, second=12, third=13, fourth=14
        regardless of their display names (Page, Knave, Princess, etc.)

        IMPORTANT: For filenames with numeric prefixes (e.g. "01_the_fool"), the number
        is extracted and used as the sort order directly."""
        # Check preset type
        preset = self.get_preset(preset_name) if preset_name else None
        preset_type = preset.get('type') if preset else None

        # I Ching trigrams: filenames like "t1", "t01" → sort order 65-72
        if preset_type == 'I Ching':
            trigram_match = re.match(r'^t(\d+)(?:[\s_\-\.]|$)', card_name.lower())
            if trigram_match:
                tri_num = int(trigram_match.group(1))
                if 1 <= tri_num <= 8:
                    return 64 + tri_num

        # First, try to extract a numeric prefix from the filename (before normalizing)
        # This handles filenames like "01_the_fool.png", "08-justice.png", "22 The World.png"
        # Also handles pure numeric filenames like "01", "64"
        numeric_prefix_match = re.match(r'^(\d+)(?:[\s_\-\.]|$)', card_name.lower())
        if numeric_prefix_match:
            extracted_num = int(numeric_prefix_match.group(1))
            # For I Ching, validate range 1-64 (hexagrams)
            if preset_type == 'I Ching':
                if 1 <= extracted_num <= 64:
                    return extracted_num
            # For Lenormand, validate range 1-36 (Petit) or 1-54 (Grand)
            elif preset_type == 'Petit Lenormand':
                is_grand = preset_name and 'grand' in preset_name.lower()
                max_card = 54 if is_grand else 36
                if 1 <= extracted_num <= max_card:
                    return extracted_num
            # For Kipper, validate range 1-36
            elif preset_type == 'Kipper':
                if 1 <= extracted_num <= 36:
                    return extracted_num
            # For Playing Cards, use a different scheme
            elif preset_type == 'Playing Cards':
                pass  # Fall through to playing card logic
            # For Tarot: check if Gnostic/Eternal first (uses 1-78 numbering)
            elif preset_type == 'Tarot':
                is_gnostic = preset_name and 'gnostic' in preset_name.lower()
                if is_gnostic:
                    # Gnostic/Eternal Tarot uses 1-78 numbering for all cards
                    if 1 <= extracted_num <= 78:
                        return extracted_num
                # Standard Tarot: only use numeric prefix for Major Arcana (0-21)
                # Minor Arcana should fall through to name-based matching for 1xx-4xx sort order
                elif 0 <= extracted_num <= 21:
                    return extracted_num
                # For 22+, fall through to name-based matching below
            # For Oracle/other, use the number directly
            else:
                if extracted_num >= 0:
                    return extracted_num

        # Normalize the name: replace underscores/hyphens with spaces for matching
        # Also strip leading numbers (e.g., "22_ace_of_wands" -> "ace of wands")
        name_lower = card_name.lower().replace('_', ' ').replace('-', ' ')
        name_lower = re.sub(r'^\d+\s*', '', name_lower).strip()

        # I Ching: extract hexagram number from filename/name (fallback)
        if preset_type == 'I Ching':
            # Try to find any number in the name
            all_numbers = re.findall(r'(\d+)', name_lower)
            for num_str in all_numbers:
                hex_num = int(num_str)
                if 1 <= hex_num <= 64:
                    return hex_num
            return 999  # Unknown

        is_playing_cards = preset_type == 'Playing Cards'

        if is_playing_cards:
            return self._get_playing_card_sort_order(name_lower)

        # Determine ordering based on preset
        # RWS ordering: Strength=8, Justice=11
        # Pre-Golden Dawn / Thoth ordering: Justice/Adjustment=8, Strength/Lust=11
        is_thoth = preset_name and 'thoth' in preset_name.lower()
        is_pre_golden_dawn = preset_name and 'pre-golden' in preset_name.lower()
        use_thoth_ordering = is_thoth or is_pre_golden_dawn

        if use_thoth_ordering:
            strength_order = 11
            justice_order = 8
        else:
            strength_order = 8
            justice_order = 11

        # Major arcana order
        major_arcana = {
            'the fool': 0, 'fool': 0,
            'the magician': 1, 'magician': 1, 'the magus': 1, 'magus': 1,
            'the high priestess': 2, 'high priestess': 2, 'the priestess': 2, 'priestess': 2,
            'the empress': 3, 'empress': 3,
            'the emperor': 4, 'emperor': 4,
            'the hierophant': 5, 'hierophant': 5,
            'the lovers': 6, 'lovers': 6,
            'the chariot': 7, 'chariot': 7,
            'strength': strength_order, 'lust': strength_order,
            'the hermit': 9, 'hermit': 9,
            'wheel of fortune': 10, 'fortune': 10, 'the wheel': 10, 'wheel': 10,
            'justice': justice_order, 'adjustment': justice_order,
            'the hanged man': 12, 'hanged man': 12,
            'death': 13,
            'temperance': 14, 'art': 14,
            'the devil': 15, 'devil': 15,
            'the tower': 16, 'tower': 16,
            'the star': 17, 'star': 17,
            'the moon': 18, 'moon': 18,
            'the sun': 19, 'sun': 19,
            'judgement': 20, 'judgment': 20, 'the aeon': 20, 'aeon': 20,
            'the world': 21, 'world': 21, 'the universe': 21, 'universe': 21,
        }

        if name_lower in major_arcana:
            return major_arcana[name_lower]

        # Pip card rank order within suits (Ace-Ten = 1-10 for sort order calculation)
        pip_rank_order = {
            'ace': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        }

        # Court card positions - map to fixed sort offsets (11, 12, 13, 14)
        # For Thoth: Princess=11, Prince=12, Queen=13, Knight=14
        # For RWS/standard: Page=11, Knight=12, Queen=13, King=14
        is_thoth = preset_name and 'thoth' in preset_name.lower()

        if is_thoth:
            court_positions = {
                'princess': 11,
                'prince': 12,
                'queen': 13,
                'knight': 14,  # Thoth Knight = King position
            }
        else:
            court_positions = {
                'page': 11, 'princess': 11, 'jack': 11, 'knave': 11, 'valet': 11,
                'knight': 12, 'prince': 12, 'cavalier': 12,
                'queen': 13,
                'king': 14,
            }

        # Add custom court names if provided - they map to their position's sort order
        if custom_court_names:
            if custom_court_names.get('page'):
                court_positions[custom_court_names['page'].lower()] = 11
            if custom_court_names.get('knight'):
                court_positions[custom_court_names['knight'].lower()] = 12
            if custom_court_names.get('queen'):
                court_positions[custom_court_names['queen'].lower()] = 13
            if custom_court_names.get('king'):
                court_positions[custom_court_names['king'].lower()] = 14

        # Get suit names (custom or default)
        suit_names = custom_suit_names or {}
        wands_name = suit_names.get('wands', 'Wands').lower()
        cups_name = suit_names.get('cups', 'Cups').lower()
        swords_name = suit_names.get('swords', 'Swords').lower()
        pentacles_name = suit_names.get('pentacles', 'Pentacles').lower()

        # Suit base values for Minor Arcana
        # Wands: 100-114, Cups: 200-214, Swords: 300-314, Pentacles: 400-414
        suit_bases = {
            wands_name: 100,
            cups_name: 200,
            swords_name: 300,
            pentacles_name: 400,
            # Also include defaults in case mixed
            'wands': 100, 'cups': 200, 'swords': 300, 'pentacles': 400,
            'coins': 400, 'disks': 400,
        }

        # Find suit
        for suit_name, base in suit_bases.items():
            if f'of {suit_name}' in name_lower:
                # Check court cards first (sort by length to match longer names first)
                for court_name in sorted(court_positions.keys(), key=len, reverse=True):
                    if name_lower.startswith(court_name):
                        return base + court_positions[court_name]
                # Check pip cards
                for rank, rank_val in pip_rank_order.items():
                    if name_lower.startswith(rank):
                        return base + rank_val
                return base + 50  # Unknown rank

        return 999  # Unknown cards at end

    def _get_playing_card_sort_order(self, name_lower: str) -> int:
        """Get sort order for playing cards.
        Jokers: 1 (Red), 2 (Black)
        Suits: Spades=1xx, Hearts=2xx, Clubs=3xx, Diamonds=4xx
        Ranks: Ace=01, Two=02, Three=03, ... Ten=10, Jack=11, Queen=12, King=13
        Order within suit: A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K
        Examples: Ace of Spades=101, Two of Spades=102, King of Spades=113, Ace of Hearts=201
        """
        # Jokers first
        if 'joker' in name_lower:
            if 'red' in name_lower:
                return 1
            elif 'black' in name_lower:
                return 2
            else:
                return 1  # Default joker to 1

        # Suit base values
        suit_bases = {
            'spades': 100,
            'hearts': 200,
            'clubs': 300,
            'diamonds': 400,
        }

        # Rank values (A=1, 2=2, 3=3, ..., K=13)
        # Include both word and numeric forms
        rank_values = {
            'ace': 1, 'a': 1,
            'two': 2, '2': 2,
            'three': 3, '3': 3,
            'four': 4, '4': 4,
            'five': 5, '5': 5,
            'six': 6, '6': 6,
            'seven': 7, '7': 7,
            'eight': 8, '8': 8,
            'nine': 9, '9': 9,
            'ten': 10, '10': 10,
            'jack': 11, 'j': 11,
            'queen': 12, 'q': 12,
            'king': 13, 'k': 13,
        }

        # Find suit and rank
        for suit_name, base in suit_bases.items():
            if f'of {suit_name}' in name_lower:
                for rank, rank_val in rank_values.items():
                    if name_lower.startswith(rank):
                        return base + rank_val
                return base + 50  # Unknown rank

        return 999  # Unknown cards at end


# Global instance
_presets_instance = None


def get_presets() -> ImportPresets:
    """Get the global import presets instance"""
    global _presets_instance
    if _presets_instance is None:
        _presets_instance = ImportPresets()
    return _presets_instance
