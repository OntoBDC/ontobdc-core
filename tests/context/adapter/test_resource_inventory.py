import json

from ontobdc.context.adapter.resource_inventory import ContainerResourceInventory


def test_inventory_reads_manifest_and_does_not_scan_unlisted_files(tmp_path):
    marker = tmp_path / ".__ontobdc__"
    marker.mkdir()
    (tmp_path / "listed.pdf").write_bytes(b"pdf")
    (tmp_path / "not-listed.txt").write_text("hidden from inventory")
    (marker / "datapackage.json").write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "name": "listed",
                        "path": "../listed.pdf",
                        "mediatype": "application/pdf",
                    }
                ]
            }
        )
    )

    resources = ContainerResourceInventory(tmp_path).list_resources()

    assert len(resources) == 1
    assert resources[0]["path"] == "listed.pdf"
    assert resources[0]["uri"] == (tmp_path / "listed.pdf").as_uri()
