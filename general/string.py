from fuzzywuzzy import fuzz
from unidecode import unidecode #UTF-8 to ASCII converter

def closest_string(choice, options):
    """
    Find closest option to `choice` in `options` using fuzzywuzzy string matching
    * choice : string
    * options : list of strings
    Usage: 
    closest_string("gato correu", ["cachorro comeu bolo", "gato bebeu cafe e correu", "elefante comeu bolo"])
    returns "gato bebeu cafe e correu"
    """
    choice = unidecode(choice).lower()
    max_ratio = 0
    closest_match = None        
    for option in options: # get the closest (order matters)
        ratio = fuzz.token_sort_ratio(choice, unidecode(option).lower())
        if ratio > max_ratio:
            max_ratio = ratio
            closest_match = option    
    return closest_match


def closest_enum(choice, enum_class):    
    """
    Finds the closest option to `choice` in `enum_class` by comparing fuzzy ratios of the choices.
    * choice : string - The target string to find the closest match for.
    * enum_class : Enum to compare against.
    Returns the enum member with the closest fuzzy ratio match to the choice.
    """
    choice = unidecode(choice)
    max_ratio = 0
    closest_match = None    
    for enum_member in enum_class:
        enum_name = enum_member.name.replace('_', ' ')  # Remove underscores
        # get the closest string (order matters)
        ratio = fuzz.token_sort_ratio(choice, enum_name)
        if ratio > max_ratio:
            max_ratio = ratio
            closest_match = enum_member
    return closest_match