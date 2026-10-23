"""Validated server-rendered forms."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    Regexp,
)


EMAIL_VALIDATOR = Regexp(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    message="Enter a valid email address.",
)


class RegistrationForm(FlaskForm):
    """New-account form."""

    name = StringField("Full name", filters=[str.strip], validators=[DataRequired(), Length(max=120)])
    email = StringField(
        "Email", filters=[str.strip], validators=[DataRequired(), Length(max=254), EMAIL_VALIDATOR]
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    """Account login form."""

    email = StringField("Email", filters=[str.strip], validators=[DataRequired(), EMAIL_VALIDATOR])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class ProfileForm(FlaskForm):
    """Basic student profile and internship preferences form."""

    name = StringField("Full name", filters=[str.strip], validators=[DataRequired(), Length(max=120)])
    college = StringField("College", validators=[Optional(), Length(max=160)])
    degree = StringField("Degree", validators=[Optional(), Length(max=120)])
    branch = StringField("Branch", validators=[Optional(), Length(max=120)])
    graduation_year = IntegerField(
        "Graduation year", validators=[Optional(), NumberRange(min=2000, max=2100)]
    )
    preferred_locations = StringField("Preferred locations (comma-separated)")
    preferred_domains = StringField("Preferred domains (comma-separated)")
    internship_type = SelectField(
        "Preferred work mode",
        choices=[("", "No preference"), ("remote", "Remote"), ("onsite", "On-site"), ("hybrid", "Hybrid")],
        validators=[Optional()],
    )
    minimum_stipend = IntegerField(
        "Minimum stipend (INR/month)", validators=[Optional(), NumberRange(min=0)]
    )
    submit = SubmitField("Save profile")
