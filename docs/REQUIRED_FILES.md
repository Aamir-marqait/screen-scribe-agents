# Required Files for Existing Crews

The list of source documents the current `notes_crew`, `quiz_crew`, and `assignment_crew` reference by name. Until these files actually exist on disk (or in a vector store / RAG layer), the crews are passing the lead just the *titles* into the prompt — the LLM never sees the underlying content.

All 34 files are linked from `docs/FOR DEVELOPER - AI INPUT SHEET 17062025 - B.A., (H) FILMMAKING.xlsx` (curriculum sheet, 100% coverage confirmed). The `scripts/download_curriculum.py` script pulls them into `docs/curriculum-pull/<sheet>/...`.

## Books / PDFs (20 — used by `notes_crew` & `quiz_crew`)

Filenames as `quiz_crew/data/reading_materials.yaml` expects them (with extensions):

| # | Filename |
|---|---|
| 1 | `How to Read a Film_ Movies, Media, and Beyond.pdf` |
| 2 | `Film Art_ An Introduction 10th Edition ( PDFDrive ).pdf` |
| 3 | `Ways of Seeing .pdf` |
| 4 | `The Five C's of Cinematography_ Motion Picture Filming Techniques(1).pdf` |
| 5 | `Screenplay; The Foundations of Screenwriting, revised & updated - Syd Field.pdf` |
| 6 | `Film editing karel reiz.pdf` |
| 7 | `Bruce-Block-The-Visual-Story-Creating-the-Visual-Structure-of-Film-TV-And-Digital-Media-2021.pdf` |
| 8 | `On Writing_ A Memoir of the Craft - Stephen King.pdf` |
| 9 | `Short stories by Guy de Maupassant.pdf` |
| 10 | `The Stories of Anton Chekhov (Anton Chekhov).pdf` |
| 11 | `the-anatomy-of-story-22-steps-to-becoming-a-master-storyteller_compress.pdf` |
| 12 | `Art of Dramatic Writing - Lajos Egri.pdf` |
| 13 | `toaz.info-save-the-cat-by-blake-snyder-pr_8defda23000f86ee7b077787303fa715.pdf` |
| 14 | `Aristotle_Poetics_Lucas_Kassel_1968_1980.pdf` |
| 15 | `Film Directing Shot by shot .pdf` |
| 16 | `ilide.info-becoming-an-actorx27s-director-directing-actors-for-film-and-television-regg-pr_2c3d1d2c691c8c718bed0ca1c547c1e1.pdf` |
| 17 | `Directing Actors_ Creating Memorable Performances for Film & Television.pdf` |
| 18 | `Dialogue_-_Robert_McKee.pdf` |
| 19 | `On Dialogue.pdf` |
| 20 | `The Writer's Journey.pdf` |

> One non-file entry exists: `https://www.celtx.com/` and `https://www.studiovity.com/` are mapped to subtopic "screenwriting softwares". No download needed — they're literal URLs passed through to the prompt.

## Institutional / Parameter docs (13 — used by `assignment_crew`)

Unique `.docx` / Google Doc parameter files from `assignment_crew/data/evaluation_documents.yaml`:

| # | Filename | Type |
|---|---|---|
| 1 | `IDS SEM I-Film diary   Assignment - Parameters.docx` | docx |
| 2 | `IDS SEM I-Actuality  Assignment - Parameters.docx` | docx |
| 3 | `IDS SEM I-Film diary A2.docx` | docx |
| 4 | `A1.docx` | docx |
| 5 | `A3.docx` | docx |
| 6 | `A4.docx` | docx |
| 7 | `A5.docx` | docx |
| 8 | `A6.docx` | docx |
| 9 | `Assignment - Parameters.docx` | docx |
| 10 | `SEMESTER I - IDS I - RESEARCH` | Google Doc |
| 11 | `IDS SEM I-SPW` | Google Doc (also used by quiz/notes crews) |
| 12 | `IDS SEM II - parameters_dialogue` | Google Doc (also used by quiz/notes crews) |
| 13 | `IDS SEM II-Blocking and Staging` | Google Doc |

## Activity-flag values (NOT files — no download needed)

`assignment_crew` treats these strings as activity flags that trigger the default rubric path (see `app/crews/assignment_crew/config/tasks.yaml:19-31`). They are not document references:

- `Shoot` / `shoot`
- `theory`
- `Practical class with acting dept`
- `in class exercise`
- `group discussion - culminated three modules above`

## Totals

- **20 PDFs** (books)
- **13 institutional docs** (9 `.docx` + 4 Google Docs)
- **= 33 unique files**
