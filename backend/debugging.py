import json


class A:
    def __init__(self, a, b):
        self.a = a
        self.b = b


def test():
    with open("src/tests/files/aatrox_data.json", encoding='UTF-8') as champion:
        champion = json.load(champion)
    print(champion)

def main():
    test()



if __name__ == "__main__":
    main()