import pytest

from src.server.loader.helper import info_loader






def test_info_loader():
    urls = info_loader().urls
    assert urls.patches == "https://ddragon.leagueoflegends.com/api/versions.json"


