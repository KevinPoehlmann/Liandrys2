import json
import requests
import re



def test():
    input_string = "2.4 / 2.6 / 2.8 / 3 / 3.2% of target's maximum health"
    regex1 = r"(?P<flats>[\d/ \.]+)(?P<perc>%)?( ?\(\+ (?P<scalings>.*)\))*(?P<stat>[\w' ]*)"
    result = re.fullmatch(regex1, input_string)
    print(result["flats"])
    print(result["stat"])
    if result["scalings"]:
        scals = result["scalings"].split(") (+ ")
        print(scals)



def main():
    test()



if __name__ == "__main__":
    main()