"""Create, update, and delete saved task templates."""

from __future__ import annotations

import streamlit as st

from src.config.samples import OUTPUT_FORMATS
from src.config.settings import get_settings
from src.ui.components import inject_styles

st.set_page_config(page_title="Task Manager", page_icon="🗂️", layout="wide")
inject_styles()
settings = get_settings()

st.title("Task Manager")
st.write(
    "Save reusable task templates, then load them from Workforce Studio. "
    "Built-in sample tasks are separate and cannot be edited here."
)

if not settings.persistence_enabled:
    st.warning("Persistence is disabled (`WORKFORCE_PERSISTENCE_ENABLED=false`). Enable it to manage tasks.")
    st.stop()

try:
    from src.persistence.task_repository import TaskRepository

    repo = TaskRepository()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not open task database: {exc}")
    st.stop()

tasks = repo.list_tasks()

st.subheader("Saved tasks")
if not tasks:
    st.info("No saved tasks yet. Use the form below to create one.")
else:
    for item in tasks:
        objective = (item.get("task") or "")[:90]
        st.markdown(f"**{item['title']}**  \n{objective}{'…' if len(item.get('task') or '') > 90 else ''}")
        st.caption(f"Updated {item.get('updated_at', '')} · format: {item.get('output_format')}")
        st.divider()

st.subheader("Add or edit a task")
options = {"(create new)": None}
for item in tasks:
    options[f"{item['title']} ({item['id'][:8]})"] = item["id"]

choice_label = st.selectbox("Select task to edit", options=list(options.keys()), key="tm_select")
selected_id = options[choice_label]
selected = repo.get_task(selected_id) if selected_id else None

default_title = selected["title"] if selected else ""
default_task = selected["task"] if selected else ""
default_background = selected["background"] if selected else ""
default_constraints = selected["constraints"] if selected else ""
default_horizon = selected["time_horizon"] if selected else ""
default_format = selected["output_format"] if selected else "Briefing"
if default_format not in OUTPUT_FORMATS:
    default_format = "Briefing"

# Use non-widget-bound keys for form defaults via value= to avoid cross-select stale state.
form_key = selected_id or "new"
with st.form(f"task_form_{form_key}", clear_on_submit=False):
    title = st.text_input("Title (required)", value=default_title)
    task = st.text_area("Task / objective (required)", value=default_task, height=100)
    background = st.text_area("Background / context", value=default_background, height=80)
    constraints = st.text_area("Constraints", value=default_constraints, height=80)
    time_horizon = st.text_input("Time horizon", value=default_horizon)
    output_format = st.selectbox(
        "Output format",
        options=OUTPUT_FORMATS,
        index=OUTPUT_FORMATS.index(default_format),
    )
    save_clicked = st.form_submit_button("Save task", type="primary")

if save_clicked:
    try:
        if selected_id:
            repo.update_task(
                selected_id,
                title=title,
                task=task,
                background=background,
                constraints=constraints,
                time_horizon=time_horizon,
                output_format=output_format,
            )
            st.success("Task updated.")
        else:
            repo.create_task(
                title=title,
                task=task,
                background=background,
                constraints=constraints,
                time_horizon=time_horizon,
                output_format=output_format,
            )
            st.success("Task created.")
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not save task: {exc}")

if selected_id:
    st.subheader("Delete task")
    confirm = st.checkbox("I understand this permanently deletes the selected saved task")
    if st.button("Delete selected task", type="primary", disabled=not confirm):
        if repo.delete_task(selected_id):
            st.success("Task deleted.")
            st.rerun()
        else:
            st.error("Task was not found or already deleted.")
