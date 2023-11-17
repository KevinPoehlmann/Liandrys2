import json
import requests



def debug1():
    datalink = "http://ddragon.leagueoflegends.com/cdn/13.22.1/data/en_GB/"
    champions = requests.get(datalink + "champion.json").json()
    items = requests.get(datalink + "item.json").json()
    runes = requests.get(datalink + "runesReforged.json").json()
    summoners = requests.get(datalink + "summoner.json").json()

    champion_names = [champ["name"] for champ in requests.get("http://localhost:5001/champion/13.22.1").json()]
    item_names = [item["name"] for item in requests.get("http://localhost:5001/item/13.22.1").json()]
    rune_names = [rune["name"] for rune in requests.get("http://localhost:5001/rune/13.22.1").json()]
    summoner_names = [summoner["name"] for summoner in requests.get("http://localhost:5001/summonerspell/13.22.1").json()]

    missing_c = [v["name"] for v in champions["data"].values() if v["name"] not in champion_names]
    missing_i = [v["name"] for v in items["data"].values() if v["name"] not in item_names]
    missing_r = []
    for tree in runes:
        for row in tree["slots"]:
            for rune in row["runes"]:
                if rune["name"] not in rune_names:
                    missing_r.append(rune["name"])
    missing_s = [v["name"] for v in summoners["data"].values() if v["name"] not in summoner_names]

    result = {
        "champions": {
            "number": len(missing_c),
            "names": missing_c
        },
        "items": {
            "number": len(missing_i),
            "names": missing_i
        },
        "runes": {
            "number": len(missing_r),
            "names": missing_r
        },
        "summoners": {
            "number": len(missing_s),
            "names": missing_s
        },
    }

    with open("debug.json", "w") as json_file:
        json.dump(result, json_file)



def main():
    debug1()



if __name__ == "__main__":
    main()