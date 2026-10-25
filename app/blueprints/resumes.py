"""Private resume upload, analysis, and active-resume routes."""

from __future__ import annotations

import os
import uuid
import zipfile
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select, update
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.forms import ResumeUploadForm
from app.models import Internship, Resume
from app.services.ats_scorer import score_resume
from app.services.resume_parser import ResumeParseError, parse_resume_file

resumes_bp = Blueprint("resumes", __name__, url_prefix="/resumes")
PDF_MIME_TYPES = {"application/pdf", "application/x-pdf"}
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@resumes_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """List the current user's resumes and accept new resume uploads."""
    form = ResumeUploadForm()
    if form.validate_on_submit():
        upload = form.resume_file.data
        try:
            safe_filename, extension = _validate_upload(upload)
        except ValueError as error:
            flash(str(error), "error")
        else:
            upload_directory = Path(
                current_app.config["UPLOAD_FOLDER"]
                or Path(current_app.instance_path) / "uploads"
            )
            upload_directory.mkdir(parents=True, exist_ok=True)
            stored_path = upload_directory / f"{uuid.uuid4().hex}{extension}"
            saved_resume: Resume | None = None
            try:
                upload.save(stored_path)
                parsed = parse_resume_file(stored_path)
                db.session.execute(
                    update(Resume)
                    .where(Resume.user_id == current_user.id)
                    .values(is_active=False)
                )
                resume = Resume(
                    user_id=current_user.id,
                    original_filename=safe_filename[:255],
                    parsed_text=parsed.text,
                    profile_json=parsed.profile,
                    is_active=True,
                )
                db.session.add(resume)
                db.session.commit()
                saved_resume = resume
            except ResumeParseError as error:
                db.session.rollback()
                flash(str(error), "error")
            finally:
                stored_path.unlink(missing_ok=True)
            if saved_resume is not None:
                flash("Resume uploaded and analyzed.", "success")
                return redirect(url_for("resumes.analysis", resume_id=saved_resume.id))

    resumes = db.session.scalars(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc(), Resume.id.desc())
    ).all()
    return render_template("resumes/index.html", form=form, resumes=resumes)


@resumes_bp.get("/<int:resume_id>")
@login_required
def analysis(resume_id: int):
    """Show a structured analysis of a resume owned by the current user."""
    resume = _get_owned_resume(resume_id)
    internships = db.session.scalars(
        select(Internship).order_by(Internship.title.asc())
    ).all()
    selected_internship = db.session.get(Internship, request.args.get("internship_id", ""))
    target_skills = (
        selected_internship.required_skills + selected_internship.preferred_skills
        if selected_internship
        else None
    )
    ats_report = score_resume(
        resume,
        target_skills=target_skills,
        target_title=selected_internship.title if selected_internship else None,
    )
    return render_template(
        "resumes/analysis.html",
        resume=resume,
        ats_report=ats_report,
        internships=internships,
        selected_internship=selected_internship,
    )


@resumes_bp.post("/<int:resume_id>/activate")
@login_required
def activate(resume_id: int):
    """Set one of the current user's resumes as the active resume."""
    resume = _get_owned_resume(resume_id)
    db.session.execute(
        update(Resume).where(Resume.user_id == current_user.id).values(is_active=False)
    )
    resume.is_active = True
    db.session.commit()
    flash("Active resume updated.", "success")
    return redirect(url_for("resumes.index"))


def _get_owned_resume(resume_id: int) -> Resume:
    """Return a resume only when it belongs to the signed-in user."""
    resume = db.session.scalar(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id,
        )
    )
    if resume is None:
        abort(404)
    return resume


def _validate_upload(upload: FileStorage) -> tuple[str, str]:
    """Validate a supported resume's filename, content type, size, and signature."""
    safe_filename = secure_filename(upload.filename or "")
    if not safe_filename:
        raise ValueError("Choose a PDF or DOCX resume file.")

    extension = Path(safe_filename).suffix.casefold()
    mime_type = (upload.mimetype or "").casefold()
    if extension not in {".pdf", ".docx"}:
        raise ValueError("Unsupported file type. Upload a PDF or DOCX resume.")
    expected_mimes = PDF_MIME_TYPES if extension == ".pdf" else {DOCX_MIME_TYPE}
    if mime_type not in expected_mimes:
        raise ValueError("The file type does not match its extension. Please choose a valid resume.")

    stream = upload.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size > current_app.config["MAX_RESUME_BYTES"]:
        raise ValueError("Resume must be 5 MB or smaller.")

    signature = stream.read(8)
    stream.seek(0)
    if extension == ".pdf":
        valid_signature = signature.startswith(b"%PDF-")
    else:
        valid_signature = signature.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
        if valid_signature:
            try:
                with zipfile.ZipFile(stream) as archive:
                    files = set(archive.namelist())
                    valid_signature = (
                        "[Content_Types].xml" in files and "word/document.xml" in files
                    )
            except zipfile.BadZipFile:
                valid_signature = False
        stream.seek(0)
    if not valid_signature:
        raise ValueError("The file contents do not match a valid PDF or DOCX resume.")

    return safe_filename, extension
