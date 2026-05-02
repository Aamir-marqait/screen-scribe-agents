from app.crews.assignment_crew.crew import lookup_evaluation_document
from app.crews.notes_crew.crew import lookup_reading_materials as notes_materials
from app.crews.quiz_crew.crew import lookup_reading_materials as quiz_materials


def test_assignment_evaluation_doc_known():
    assert lookup_evaluation_document("Film Analysis") == "IDS SEM I-Film diary"


def test_assignment_evaluation_doc_unknown():
    assert lookup_evaluation_document("nonexistent") == "(none assigned)"


def test_notes_and_quiz_materials_differ_for_same_subtopic():
    """Sanity: the n8n workflows had two distinct lookup tables (notes uses
    pretty titles, quiz uses raw .pdf filenames). We preserve both so each
    crew receives exactly what its original prompt expected."""

    n = notes_materials("film analysis")
    q = quiz_materials("film analysis")
    assert n and q
    assert any(item.endswith(".pdf") for item in q)
    assert not any(item.endswith(".pdf") for item in n)
