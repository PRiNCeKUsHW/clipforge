import uuid

from clipforge_worker.context import orphan_work_dirs


def test_only_folders_of_missing_projects_are_orphans(tmp_path):
    kept, gone = str(uuid.uuid4()), str(uuid.uuid4())
    for name in (kept, gone, "layouttest"):
        (tmp_path / name).mkdir()
    (tmp_path / str(uuid.uuid4())).write_text("a stray file, not a project folder")

    assert orphan_work_dirs(tmp_path, {kept}) == [tmp_path / gone]


def test_missing_work_dir_is_fine(tmp_path):
    assert orphan_work_dirs(tmp_path / "nope", set()) == []
