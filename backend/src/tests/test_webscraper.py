from src.server.loader.webscraper import get_hotfix_list, datetime




def test_get_hotfix_list():
    with open("src/tests/files/Patch1321.html", encoding="UTF-8") as patch1321:
        result = get_hotfix_list(patch1321)
        assert result == [datetime(2023, 10, 26), datetime(2023, 10, 27)]
