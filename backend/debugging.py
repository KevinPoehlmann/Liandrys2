from aenum import MultiValueEnum

# Define an Enum for stats
class Stat(str, MultiValueEnum):
    HP = "hp", "hitpoints"
    AD = "ad", "attack damage"
    AP = "ap"
    ARMOR = "armor"
    MR = "mr"
    ABILITY_HASTE="ability_haste"

class Unit:
    def __init__(self, hp: int, ad: int, ap: int, armor: int, mr: int,
                 ad_per_lvl: int, ap_per_lvl: int, armor_per_lvl: int, mr_per_lvl: int):
        self.hp = hp
        self.ad = ad
        self.ap = ap
        self.armor = armor
        self.mr = mr  # Magic Resist
        
        self.ad_per_lvl = ad_per_lvl
        self.ap_per_lvl = ap_per_lvl
        self.armor_per_lvl = armor_per_lvl
        self.mr_per_lvl = mr_per_lvl


class Character:
    def __init__(self, unit: Unit, level: int, ability: str):
        
        self.unit = unit
        self.level = level
        self.ability = ability

    def get_stat(self, stat: Stat):
        """Returns the total value of a stat dynamically based on level scaling."""
        stat_name = stat.value  # Convert Enum to string, e.g., "ad"

        # Base stat
        base_value = getattr(self.unit, stat_name, None)

        # If the stat doesn't exist (shouldn't happen with an enum), return None
        if base_value is None:
            return None

        # Check if the stat has a corresponding level-scaling attribute
        scaling_attr = f"{stat_name}_per_lvl"
        scaling_value = getattr(self.unit, scaling_attr, 0)  # Default to 0 if no scaling exists

        return base_value + scaling_value * self.level

    def use_ability(self):
        """Calculates the ability value using the dynamically updated stats."""
        variables = {
            stat.value: self.get_stat(stat) for stat in Stat
        }
        print(variables)
        return eval(self.ability, {}, variables)


# **Example Usage:**




if __name__ == "__main__":
    unit = Unit(
        hp=100, ad=10, ap=5, armor=20, mr=15, 
        ad_per_lvl=2, ap_per_lvl=1, armor_per_lvl=1, mr_per_lvl=1
    )
    char = Character(
        unit=unit, level=3, ability="3 * ad + 5 * ap + armor"
    )

    print(char.get_stat(Stat.HP))     # Output: 100 (no scaling)
    print(char.get_stat(Stat.AD))     # Output: 10 + (2 * 3) = 16
    print(char.get_stat(Stat.AP))     # Output: 5 + (1 * 3) = 8
    print(char.get_stat(Stat.ARMOR))  # Output: 20 + (1 * 3) = 23
    print(char.get_stat(Stat.MR))     # Output: 15 + (1 * 3) = 18

    # Using the ability method
    print(char.use_ability())  # Output: 3 * 16 + 5 * 8 + 23 = 48 + 40 + 23 = 111
