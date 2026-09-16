"""Forms for the in-app admin panel.

Labels are intentionally plain — templates render their own localized
labels via the {% t %} system so every field is UZ/RU/EN aware.
"""
from django import forms

from apps.essays.models import EssayTopic
from apps.tests.models import Choice, Question, Test


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
class TestForm(forms.ModelForm):
    class Meta:
        model = Test
        fields = [
            "title",
            "description",
            "course",
            "module",
            "time_limit_minutes",
            "max_attempts",
            "pass_percentage",
            "difficulty",
            "status",
            "show_results_immediately",
            "shuffle_questions",
            "shuffle_choices",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


# ---------------------------------------------------------------------------
# Question + choices
# ---------------------------------------------------------------------------
class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            "question_type",
            "passage",
            "text",
            "correct_text",
            "points",
            "explanation",
            "position",
        ]
        widgets = {
            "passage": forms.Textarea(attrs={"rows": 4}),
            "text": forms.Textarea(attrs={"rows": 3}),
            "explanation": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        qtype = cleaned.get("question_type")
        if qtype == Question.QuestionType.TEXT_MATCH:
            if not (cleaned.get("correct_text") or "").strip():
                self.add_error(
                    "correct_text",
                    "Matnli javob savolida to'g'ri javob matni kiritilishi shart.",
                )
        return cleaned


class ChoiceForm(forms.ModelForm):
    # position is managed implicitly (order of entry); model default 0 applies
    position = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Choice
        fields = ["text", "is_correct", "position"]
        widgets = {
            "text": forms.TextInput(attrs={"placeholder": "Variant matni"}),
        }


ChoiceFormSet = forms.inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    extra=4,
    max_num=6,
    min_num=2,
    can_delete=True,
)


# ---------------------------------------------------------------------------
# Essay Topic
# ---------------------------------------------------------------------------
class EssayTopicForm(forms.ModelForm):
    # Empty = keep the existing password (write-only, never shown).
    # Non-empty = set a new one (hashed by EssayTopic.save()).
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Bo'sh qoldirilsa — joriy parol saqlanadi.",
    )

    class Meta:
        model = EssayTopic
        fields = [
            "title",
            "description",
            "category",
            "word_limit_min",
            "word_limit_max",
            "time_limit_minutes",
            "sample_outline",
            "grammar_strictness",
            "national_cert_scale",
            "password",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "sample_outline": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        wmin = cleaned.get("word_limit_min")
        wmax = cleaned.get("word_limit_max")
        if wmin is not None and wmax is not None and wmin > wmax:
            self.add_error(
                "word_limit_max",
                "Maksimal so'zlar soni minimaldan katta bo'lishi kerak.",
            )
        return cleaned

    def save(self, commit=True):
        # Empty password field = keep the stored hash (ModelForm would
        # otherwise overwrite it with ""). A typed value is hashed by
        # EssayTopic.save().
        if not (self.cleaned_data.get("password") or "").strip():
            if self.instance.pk:
                self.instance.password = EssayTopic.objects.values_list(
                    "password", flat=True
                ).get(pk=self.instance.pk)
            else:
                self.instance.password = ""
        return super().save(commit)