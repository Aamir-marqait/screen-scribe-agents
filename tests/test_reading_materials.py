from app.crews.notes_crew.crew import lookup_reading_materials


def test_known_subtopic_returns_materials():
    materials = lookup_reading_materials("Film Analysis")
    assert "How to Read a Film_ Movies, Media, and Beyond" in materials
    assert "Film Art_ An Introduction 10th Edition (PDFDrive)" in materials


def test_unknown_subtopic_returns_empty():
    assert lookup_reading_materials("nonexistent topic") == []
