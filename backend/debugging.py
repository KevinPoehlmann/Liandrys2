from collections import defaultdict



def main():
    dots: dict[int, tuple[str, int]] = defaultdict(list)
    dots[1].append(("a", 1))
    dots[1].append(("c", 2))
    dots[2].append(("e", 3))
    dots[2].append(("a", 1))
    dots[3].append(("b", 2))
    dots[3].append(("c", 3))

    print(dots)
    print(dots[1])
    for dot in dots.items():
        print(dot)
    ed = [dl for dl in dots.items() for d in dl[1] if d[0] == "a"]
    print(ed)
    ed.sort(reverse=True)
    print(ed)


if __name__ == "__main__":
    main()
