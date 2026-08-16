"""Golden project-review deliveries (E18.1) — pass / borderline / fail per locale."""

from __future__ import annotations

from typing import Literal

from mcp_server.domain.project_review import validate_review_comment
from mcp_server.domain.socratic import SUPPORTED_LOCALES, normalize_locale

GoldenLabel = Literal["pass", "borderline", "fail"]
GOLDEN_LABELS: tuple[GoldenLabel, ...] = ("pass", "borderline", "fail")

PASS_SCORE_MIN = 81
PASS_SCORE_MAX = 100
FAIL_SCORE_MIN = 0
FAIL_SCORE_MAX = 80
BORDERLINE_SCORE_MIN = 78
BORDERLINE_SCORE_MAX = 82


class GoldenCorpusError(ValueError):
    """Missing or invalid golden fixture key."""


class GoldenDelivery:
    __slots__ = (
        "locale",
        "label",
        "content",
        "expected_comment",
        "expected_score",
        "expected_score_min",
        "expected_score_max",
    )

    def __init__(
        self,
        *,
        locale: str,
        label: GoldenLabel,
        content: str,
        expected_comment: str,
        expected_score: int,
        expected_score_min: int,
        expected_score_max: int,
    ) -> None:
        self.locale = locale
        self.label = label
        self.content = content
        self.expected_comment = expected_comment
        self.expected_score = expected_score
        self.expected_score_min = expected_score_min
        self.expected_score_max = expected_score_max

    @property
    def expect_passed(self) -> bool:
        return passes_delivery_review(self.expected_score)

    @property
    def key(self) -> str:
        return golden_key(self.locale, self.label)


def passes_delivery_review(score: int) -> bool:
    """Same exclusive threshold as backend `passes_delivery_review`."""
    return score > 80


def golden_key(locale: str, label: str) -> str:
    return f"{locale}/{label}"


REQUIRED_GOLDEN_KEYS: tuple[str, ...] = tuple(
    golden_key(locale, label)
    for locale in SUPPORTED_LOCALES
    for label in GOLDEN_LABELS
)


def require_complete_corpus(corpus: dict[str, GoldenDelivery]) -> None:
    for key in REQUIRED_GOLDEN_KEYS:
        if key not in corpus:
            raise GoldenCorpusError(f"missing golden key: {key}")


def _bands(label: GoldenLabel) -> tuple[int, int, int]:
    if label == "pass":
        return 88, PASS_SCORE_MIN, PASS_SCORE_MAX
    if label == "fail":
        return 42, FAIL_SCORE_MIN, FAIL_SCORE_MAX
    return 80, BORDERLINE_SCORE_MIN, BORDERLINE_SCORE_MAX


def _entry(
    locale: str,
    label: GoldenLabel,
    content: str,
    expected_comment: str,
) -> GoldenDelivery:
    score, lo, hi = _bands(label)
    return GoldenDelivery(
        locale=locale,
        label=label,
        content=content,
        expected_comment=expected_comment,
        expected_score=score,
        expected_score_min=lo,
        expected_score_max=hi,
    )


def empty_content_fail(*, locale: str = "en") -> GoldenDelivery:
    """EDGE: empty learner source must not be treated as a pass golden."""
    loc = normalize_locale(locale)
    return _entry(
        loc,
        "fail",
        "",
        "No source submitted. The learner still needs a working solution.",
    )


_PASS_JS = (
    "function parseAge(raw) {\n"
    "  const n = Number(raw);\n"
    "  if (!Number.isFinite(n) || n < 0) return null;\n"
    "  return Math.trunc(n);\n"
    "}\n"
)
_NUMBER_ONLY_JS = "function parseAge(raw) {\n  return Number(raw);\n}\n"


def _build_corpus() -> dict[str, GoldenDelivery]:
    rows = (
        _entry(
            "en",
            "pass",
            _PASS_JS,
            "Parses age with Number.isFinite and rejects negatives. "
            "Next: cover non-integer strings.",
        ),
        _entry(
            "en",
            "borderline",
            _NUMBER_ONLY_JS,
            "Converts with Number but skips finite checks. "
            "Close to a pass if edge cases were handled.",
        ),
        _entry(
            "en",
            "fail",
            "function parseAge(raw) {\n  return raw;\n}\n",
            "Returns the raw string. Age is not parsed. "
            "Next: coerce and validate a number.",
        ),
        _entry(
            "pt",
            "pass",
            "// idade a partir do texto\n" + _PASS_JS,
            "Converte idade com Number.isFinite e recusa negativos. "
            "Proximo: cobrir texto nao numerico.",
        ),
        _entry(
            "pt",
            "borderline",
            _NUMBER_ONLY_JS,
            "Usa Number mas nao valida finitude. "
            "Quase passa se os casos-limite fossem tratados.",
        ),
        _entry(
            "pt",
            "fail",
            "function parseAge() {\n  return 0;\n}\n",
            "Ignora a entrada e devolve zero. Ainda nao ha solucao. "
            "Proximo: ler o argumento.",
        ),
        _entry(
            "es",
            "pass",
            "// edad desde texto\n" + _PASS_JS,
            "Parsea edad con Number.isFinite y rechaza negativos. "
            "Siguiente: cubrir cadenas no numericas.",
        ),
        _entry(
            "es",
            "borderline",
            _NUMBER_ONLY_JS,
            "Convierte con Number pero no comprueba finitud. "
            "Cerca del aprobado si cubriera bordes.",
        ),
        _entry(
            "es",
            "fail",
            "function parseAge(raw) {\n  throw new Error('todo');\n}\n",
            "Lanza siempre. No hay solucion. "
            "Siguiente: devolver un numero validado.",
        ),
        _entry(
            "zh",
            "pass",
            "// nianling\n" + _PASS_JS,
            "Parses age with Number.isFinite and rejects negatives.",
        ),
        _entry(
            "zh",
            "borderline",
            _NUMBER_ONLY_JS,
            "Converts with Number but skips finite checks.",
        ),
        _entry(
            "zh",
            "fail",
            "function parseAge(raw) {\n  return NaN;\n}\n",
            "Always returns NaN. Parsing is not implemented. "
            "Next: validate and truncate the input.",
        ),
    )
    corpus = {row.key: row for row in rows}
    if len(corpus) != len(SUPPORTED_LOCALES) * len(GOLDEN_LABELS):
        raise GoldenCorpusError("golden corpus size mismatch")
    return corpus


_CORPUS: dict[str, GoldenDelivery] | None = None


def load_golden_corpus() -> dict[str, GoldenDelivery]:
    """Return the immutable golden index (cached). Safe for concurrent readers."""
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = _build_corpus()
    return _CORPUS


def get_golden(locale: str, label: str) -> GoldenDelivery:
    loc = normalize_locale(locale)
    lab = label.strip().lower()
    if lab not in GOLDEN_LABELS:
        raise GoldenCorpusError(f"unknown golden label: {label!r}")
    key = golden_key(loc, lab)
    corpus = load_golden_corpus()
    row = corpus.get(key)
    if row is None:
        raise GoldenCorpusError(f"missing golden key: {key}")
    return row


def assert_expected_comments_valid(corpus: dict[str, GoldenDelivery] | None = None) -> None:
    data = corpus if corpus is not None else load_golden_corpus()
    errors: list[str] = []
    for key, row in data.items():
        check = validate_review_comment(row.expected_comment)
        if not check["ok"]:
            errors.append(f"{key}: {check['errors']}")
    if errors:
        raise GoldenCorpusError("; ".join(errors))
