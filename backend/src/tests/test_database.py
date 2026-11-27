from src.server.database import patch_document
from src.server.models.image import Image
from src.server.models.patch import NewPatch, Patch, RuneTree


def test_patch_document_has_string_tree_ids_and_reads_back():
    tree = RuneTree(name="Domination", image=Image(full="7200_domination.1a2b3c4d.png", group="rune"))
    patch = NewPatch(patch="16.23.1", rune_trees={8100: tree})

    document = patch_document(patch)

    assert list(document["rune_trees"]) == ["8100"]
    assert Patch(_id="0123456789abcdef01234567", **document).rune_trees == {8100: tree}
