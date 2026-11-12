import io
import json
import zipfile

from src.services.export_service import ExportService
from src.services.run_service import RunService


def test_exports_match_and_strip_secrets():
    service = RunService()
    state = service.start_run(task="Plan my next productive week.", mode="demo")
    state["events"].append(
        {
            "event_id": "e",
            "run_id": state["run_id"],
            "timestamp": state["created_at"],
            "stage": "system",
            "event_type": "note",
            "status": "ok",
            "message": "api_key=sk-abcdefghijk",
            "metadata": {"OPENAI_API_KEY": "sk-secret", "ok": True},
        }
    )
    exporter = ExportService()
    md_name, md = exporter.markdown_briefing(state)
    assert md_name.startswith("briefing_")
    assert "Executive summary" in md or "Demo Mode" in md

    json_name, js = exporter.json_bundle(state)
    assert json_name.startswith("run_bundle_")
    data = json.loads(js)
    blob = json.dumps(data)
    assert "sk-abcdefghijk" not in blob
    assert "sk-secret" not in blob
    assert "OPENAI_API_KEY" not in blob

    docx_name, docx_bytes = exporter.research_docx(state)
    assert docx_name.startswith("research_")
    assert docx_name.endswith(".docx")
    assert isinstance(docx_bytes, (bytes, bytearray))
    assert len(docx_bytes) > 100
    # DOCX files are ZIP containers starting with PK
    assert docx_bytes[:2] == b"PK"

    zip_name, zbytes = exporter.zip_bundle(state)
    assert zip_name.startswith("workforce_export_")
    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        names = zf.namelist()
        assert any(n.endswith(".md") for n in names)
        assert any(n.endswith(".json") for n in names)
        assert any(n.endswith(".docx") for n in names)
